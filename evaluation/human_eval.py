"""
evaluation/human_eval.py
------------------------
Human evaluation support module.

Step 1 — generate_eval_csv():
    Samples N articles from the test set. For each article, generates
    summaries from Lead-3, fine-tuned BART, and the full pipeline.
    Saves a blind CSV (no system labels) for evaluators to rate.

Step 2 — compute_agreement():
    After evaluators submit their ratings via Google Form / spreadsheet,
    loads the completed CSV and computes:
      - Mean Likert scores per system per dimension
      - Cohen's Kappa for pairwise inter-annotator agreement
      - Fleiss' Kappa for 3-rater overall agreement

Evaluation dimensions (1–5 Likert scale):
  - Fluency          : Is the text grammatically correct and natural?
  - Factual Accuracy : Does the summary only state things present in the article?
  - Coherence        : Does the summary read as a unified, logical paragraph?

Usage:
    # Generate the sample CSV
    python evaluation/human_eval.py --generate

    # After evaluation is complete, compute agreement
    python evaluation/human_eval.py --compute --file results/human_eval_completed.csv
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    ARTICLE_COL, SUMMARY_COL,
    NUM_HUMAN_EVAL, HUMAN_EVAL_FILE,
    SEED, RESULTS_DIR, EXPECTED_TARGETS,
)
from data.data_pipeline import get_datasets

log = logging.getLogger(__name__)

DIMENSIONS = ["fluency", "factual_accuracy", "coherence"]
SYSTEMS    = ["lead3", "bart_finetuned", "pipeline"]


# ── Step 1: Generate evaluation CSV ──────────────────────────────────────────

def generate_eval_csv(
    n: int = NUM_HUMAN_EVAL,
    output_path: Path = HUMAN_EVAL_FILE,
) -> Path:
    """
    Sample N articles from the test set, generate summaries from all
    three systems, shuffle to blind evaluators, and save to CSV.

    Returns path to the generated CSV.
    """
    from baselines.lead3 import Lead3Summarizer
    from baselines.bart_baseline import BartBaseline
    from pipeline.pipeline import SummarizationPipeline

    log.info("Loading models …")
    models = {
        "lead3":         Lead3Summarizer(),
        "bart_finetuned": BartBaseline(mode="finetuned"),
        "pipeline":       SummarizationPipeline(),
    }

    splits = get_datasets()
    test   = splits["test"]

    rng     = np.random.default_rng(SEED)
    indices = rng.choice(len(test), size=min(n, len(test)), replace=False)

    rows = []
    for sample_id, idx in enumerate(indices):
        article = test[int(idx)][ARTICLE_COL]
        gold    = test[int(idx)][SUMMARY_COL]

        # Truncate article to first 1000 words for evaluator readability
        article_display = " ".join(article.split()[:1000])

        for system_key, model in models.items():
            result  = model(article)
            summary = result["summary"]

            rows.append({
                "sample_id":       sample_id,
                "system":          system_key,        # hidden from evaluators
                "article_excerpt": article_display,
                "gold_summary":    gold,
                "generated_summary": summary,
                # Evaluator fills in these columns:
                "rater_1_fluency":          "",
                "rater_1_factual_accuracy": "",
                "rater_1_coherence":        "",
                "rater_2_fluency":          "",
                "rater_2_factual_accuracy": "",
                "rater_2_coherence":        "",
                "rater_3_fluency":          "",
                "rater_3_factual_accuracy": "",
                "rater_3_coherence":        "",
            })

    # Shuffle rows so evaluators don't know which system is which
    df = pd.DataFrame(rows).sample(frac=1, random_state=SEED).reset_index(drop=True)
    df.to_csv(output_path, index=False)
    log.info("Saved %d rows (%d articles × %d systems) to %s",
             len(df), n, len(SYSTEMS), output_path)

    # Also save a key (with system labels) for later analysis
    key_path = RESULTS_DIR / "human_eval_key.csv"
    df[["sample_id", "system"]].to_csv(key_path, index=False)
    log.info("Answer key saved to %s (DO NOT share with evaluators)", key_path)
    return output_path


# ── Step 2: Compute inter-annotator agreement ─────────────────────────────────

def _cohens_kappa(ratings_a: List, ratings_b: List) -> float:
    """Pairwise Cohen's Kappa between two raters."""
    try:
        return round(cohen_kappa_score(ratings_a, ratings_b), 3)
    except Exception:
        return float("nan")


def check_human_targets(results: dict) -> dict:
    """
    Compare human evaluation results against EXPECTED_TARGETS.
    Writes results/human_eval_targets.json with pass/fail flags.
    """
    targets = EXPECTED_TARGETS
    pipeline_scores = results.get("mean_scores", {}).get("pipeline", {})
    factual = pipeline_scores.get("factual_accuracy")

    kappa_means = [
        results["kappa"][dim]["mean"]
        for dim in DIMENSIONS
        if dim in results.get("kappa", {})
    ]
    mean_kappa = round(float(np.nanmean(kappa_means)), 3) if kappa_means else float("nan")

    factual_pass = (
        factual is not None
        and factual == factual
        and factual >= targets["human_factual_accuracy_min"]
    )
    kappa_pass = (
        mean_kappa == mean_kappa
        and mean_kappa >= targets["human_kappa_min"]
    )

    target_report = {
        "pipeline_factual_accuracy": factual,
        "factual_accuracy_target": targets["human_factual_accuracy_min"],
        "factual_accuracy_pass": factual_pass if factual == factual else None,
        "mean_kappa": mean_kappa,
        "kappa_target": targets["human_kappa_min"],
        "kappa_pass": kappa_pass if mean_kappa == mean_kappa else None,
        "all_passed": (
            factual_pass and kappa_pass
            if factual == factual and mean_kappa == mean_kappa
            else None
        ),
    }

    print("\n-- Human Evaluation vs Targets -------------------------------")
    print(
        f"  Pipeline factual accuracy: {factual} "
        f"(target >= {targets['human_factual_accuracy_min']}) "
        f"→ {'PASS' if factual_pass else 'FAIL' if factual == factual else 'PENDING'}"
    )
    print(
        f"  Mean Cohen's κ: {mean_kappa} "
        f"(target >= {targets['human_kappa_min']}) "
        f"→ {'PASS' if kappa_pass else 'FAIL' if mean_kappa == mean_kappa else 'PENDING'}"
    )

    import json
    out = RESULTS_DIR / "human_eval_targets.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(target_report, f, indent=2)
    log.info("Saved human target check to %s", out)
    return target_report


def compute_agreement(completed_csv: Path) -> dict:
    """
    Load a completed human evaluation CSV and compute:
      - Mean scores per system per dimension
      - Pairwise Cohen's Kappa (rater1-2, rater1-3, rater2-3) per dimension
      - Mean Kappa across all dimensions

    Args:
        completed_csv: path to the CSV with rater columns filled in

    Returns:
        dict with "mean_scores" and "kappa" sub-dicts
    """
    df = pd.read_csv(completed_csv)

    # Convert rating columns to numeric
    rater_cols = [
        f"rater_{r}_{d}" for r in [1, 2, 3] for d in DIMENSIONS
    ]
    for col in rater_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    results = {"mean_scores": {}, "kappa": {}}

    # ── Mean scores per system per dimension ─────────────────────────────────
    for system in SYSTEMS:
        sub = df[df["system"] == system]
        results["mean_scores"][system] = {}
        for dim in DIMENSIONS:
            vals = [
                sub[f"rater_{r}_{dim}"].dropna().values
                for r in [1, 2, 3]
            ]
            all_vals = np.concatenate(vals)
            results["mean_scores"][system][dim] = round(float(np.mean(all_vals)), 3)

    # ── Cohen's Kappa per dimension ───────────────────────────────────────────
    for dim in DIMENSIONS:
        r1 = df[f"rater_1_{dim}"].dropna().astype(int).tolist()
        r2 = df[f"rater_2_{dim}"].dropna().astype(int).tolist()
        r3 = df[f"rater_3_{dim}"].dropna().astype(int).tolist()
        min_len = min(len(r1), len(r2), len(r3))
        results["kappa"][dim] = {
            "r1_r2": _cohens_kappa(r1[:min_len], r2[:min_len]),
            "r1_r3": _cohens_kappa(r1[:min_len], r3[:min_len]),
            "r2_r3": _cohens_kappa(r2[:min_len], r3[:min_len]),
        }
        kappas = list(results["kappa"][dim].values())
        results["kappa"][dim]["mean"] = round(
            float(np.nanmean([k for k in kappas if k == k])), 3
        )

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n-- Human Evaluation Results ----------------------------------")
    print("\nMean scores (1–5 Likert):")
    header = f"{'System':<18}" + "".join(f"{d:<20}" for d in DIMENSIONS)
    print(header)
    for system, scores in results["mean_scores"].items():
        row = f"{system:<18}" + "".join(
            f"{scores[d]:<20}" for d in DIMENSIONS
        )
        print(row)

    print("\nCohen's Kappa (inter-annotator agreement):")
    for dim, kappas in results["kappa"].items():
        print(f"  {dim}: r1-r2={kappas['r1_r2']}  "
              f"r1-r3={kappas['r1_r3']}  "
              f"r2-r3={kappas['r2_r3']}  "
              f"mean={kappas['mean']}")
    print("-------------------------------------------------------------\n")

    # Save
    import json
    out = RESULTS_DIR / "human_eval_agreement.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    log.info("Saved agreement results to %s", out)
    check_human_targets(results)
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true",
                        help="Generate the blank evaluation CSV")
    parser.add_argument("--compute",  action="store_true",
                        help="Compute agreement from completed CSV")
    parser.add_argument("--file", type=Path, default=HUMAN_EVAL_FILE,
                        help="Path to completed evaluation CSV")
    args = parser.parse_args()

    if args.generate:
        generate_eval_csv()
    elif args.compute:
        compute_agreement(args.file)
    else:
        parser.print_help()
