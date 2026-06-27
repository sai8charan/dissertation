"""
evaluation/eval_metrics.py
--------------------------
Evaluation harness. Runs any summariser over the CNN/DailyMail test set
and computes all metrics reported in the dissertation Chapter 5.

Metrics:
  - ROUGE-1, ROUGE-2, ROUGE-L   (lexical overlap)
  - BERTScore F1                 (semantic similarity to gold summary)
  - NLI-FCS                      (factual consistency vs. source article, scale 0–1)
  - Hallucination rate           (% summary sentences with FCS < threshold)
  - Extractive fallback rate     (% documents that triggered fallback)
  - Latency                      (mean seconds per document)

Usage:
    python evaluation/eval_metrics.py --system pipeline
    python evaluation/eval_metrics.py --system lead3
    python evaluation/eval_metrics.py --system bart_zeroshot
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from tqdm import tqdm
from rouge_score import rouge_scorer
from bert_score import score as bert_score_fn

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    SUMMARY_COL, ARTICLE_COL,
    ROUGE_TYPES, BERTSCORE_LANG,
    FCS_THRESHOLD, RESULTS_DIR,
)
from data.data_pipeline import get_datasets
from pipeline.verifier import EvidenceVerifier

log = logging.getLogger(__name__)


# ── ROUGE ─────────────────────────────────────────────────────────────────────

def compute_rouge(
    predictions: List[str], references: List[str]
) -> Dict[str, float]:
    scorer = rouge_scorer.RougeScorer(ROUGE_TYPES, use_stemmer=True)
    agg    = {k: [] for k in ROUGE_TYPES}
    for pred, ref in zip(predictions, references):
        scores = scorer.score(ref, pred)
        for k in ROUGE_TYPES:
            agg[k].append(scores[k].fmeasure)
    return {k: round(float(np.mean(v)) * 100, 2) for k, v in agg.items()}


# ── BERTScore ─────────────────────────────────────────────────────────────────

def compute_bertscore(
    predictions: List[str], references: List[str]
) -> float:
    _, _, F1 = bert_score_fn(
        predictions, references,
        lang=BERTSCORE_LANG, verbose=False,
    )
    return round(float(F1.mean()) * 100, 2)


# ── NLI-FCS (source-grounded factuality) ─────────────────────────────────────

def compute_nli_fcs(
    predictions: List[str],
    articles: List[str],
    verifier: Optional[EvidenceVerifier] = None,
    sample_n: int = 200,           # expensive; sample for large test sets
) -> Dict[str, float]:
    """
    Computes mean FCS and hallucination rate over a sample of the test set.

    hallucination_rate = % summary sentences with entail_prob < FCS_THRESHOLD
    """
    if verifier is None:
        verifier = EvidenceVerifier()

    import nltk
    nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
    nltk.download("punkt", quiet=True)       # fallback for older NLTK
    from nltk.tokenize import sent_tokenize

    indices = np.random.choice(len(predictions), min(sample_n, len(predictions)), replace=False)
    fcs_scores = []
    halluc_counts, total_sents = 0, 0

    for i in tqdm(indices, desc="NLI-FCS"):
        # Build a minimal evidence pool from the article sentences
        art_sents = sent_tokenize(articles[i])
        pool = [{"index": j, "sentence": s, "hybrid_score": 1.0}
                for j, s in enumerate(art_sents)]
        result = verifier.verify_candidate(predictions[i], pool)
        fcs_scores.append(result["fcs"])
        for t in result["evidence_trace"]:
            total_sents  += 1
            if t["entail_prob"] < FCS_THRESHOLD:
                halluc_counts += 1

    mean_fcs    = round(float(np.mean(fcs_scores)), 4)
    halluc_rate = round(halluc_counts / max(total_sents, 1) * 100, 2)

    return {
        "nli_fcs":           mean_fcs,
        "nli_fcs_pct":       round(mean_fcs * 100, 2),
        "hallucination_rate": halluc_rate,
    }


# ── Batch evaluation ──────────────────────────────────────────────────────────

def evaluate_system(
    summarise_fn: Callable[[str], Dict],
    system_name: str,
    max_samples: int = 500,
    compute_fcs: bool = True,
    save_results: bool = True,
) -> Dict:
    """
    Run a summariser over the test set and compute all metrics.

    Args:
        summarise_fn   : callable that takes article str → dict with "summary" key
        system_name    : label for results file and table
        max_samples    : number of test articles to evaluate (None = all 11,490)
        compute_fcs    : whether to run the expensive NLI-FCS metric
        save_results   : save CSV + JSON to results/

    Returns:
        dict with all metric values
    """
    splits = get_datasets()
    test   = splits["test"]
    if max_samples:
        test = test.select(range(min(max_samples, len(test))))

    predictions, references, articles = [], [], []
    fallback_flags, latencies = [], []

    for example in tqdm(test, desc=f"Evaluating {system_name}"):
        article  = example[ARTICLE_COL]
        gold     = example[SUMMARY_COL]
        result   = summarise_fn(article)
        predictions.append(result.get("summary", ""))
        references.append(gold)
        articles.append(article)
        fallback_flags.append(result.get("fallback", False))
        latencies.append(result.get("latency_s", 0.0))

    # ── Compute all metrics ───────────────────────────────────────────────────
    log.info("Computing ROUGE …")
    rouge = compute_rouge(predictions, references)

    log.info("Computing BERTScore …")
    bs_f1 = compute_bertscore(predictions, references)

    fallback_rate = round(sum(fallback_flags) / len(fallback_flags) * 100, 2)
    mean_latency  = round(float(np.mean(latencies)), 3)

    metrics = {
        "system":          system_name,
        "n_samples":       len(predictions),
        **rouge,
        "bertscore_f1":    bs_f1,
        "fallback_rate":   fallback_rate,
        "mean_latency_s":  mean_latency,
    }

    if compute_fcs:
        log.info("Computing NLI-FCS (sampled) …")
        fcs_metrics = compute_nli_fcs(predictions, articles)
        metrics.update(fcs_metrics)
    else:
        metrics["nli_fcs"]             = None
        metrics["hallucination_rate"]  = None

    # ── Print table row ───────────────────────────────────────────────────────
    print(f"\n-- {system_name} ------------------------------------------")
    for k, v in metrics.items():
        print(f"  {k:<22}: {v}")

    # ── Save ─────────────────────────────────────────────────────────────────
    if save_results:
        out = RESULTS_DIR / f"eval_{system_name}.json"
        with open(out, "w") as f:
            json.dump(metrics, f, indent=2)
        log.info("Saved metrics to %s", out)

        # Save per-sample predictions for error analysis
        df = pd.DataFrame({
            "article":    articles,
            "gold":       references,
            "prediction": predictions,
            "fallback":   fallback_flags,
        })
        df.to_csv(RESULTS_DIR / f"preds_{system_name}.csv", index=False)

    return metrics


def load_all_results() -> pd.DataFrame:
    """Collect all saved eval_*.json files into a comparison DataFrame."""
    rows = []
    for f in RESULTS_DIR.glob("eval_*.json"):
        with open(f) as fp:
            rows.append(json.load(fp))
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("system")
    return df


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", default="lead3",
                        choices=["lead3", "textrank", "bart_zeroshot",
                                 "bart_finetuned", "pipeline"])
    parser.add_argument("--max_samples", type=int, default=200)
    parser.add_argument("--no_fcs", action="store_true")
    args = parser.parse_args()

    if args.system == "lead3":
        from baselines.lead3 import Lead3Summarizer
        fn = Lead3Summarizer()
    elif args.system == "textrank":
        from baselines.textrank import TextRankSummarizer
        fn = TextRankSummarizer()
    elif args.system == "bart_zeroshot":
        from baselines.bart_baseline import BartBaseline
        fn = BartBaseline(mode="zeroshot")
    elif args.system == "bart_finetuned":
        from baselines.bart_baseline import BartBaseline
        fn = BartBaseline(mode="finetuned")
    elif args.system == "pipeline":
        from pipeline.pipeline import SummarizationPipeline
        fn = SummarizationPipeline()

    evaluate_system(
        summarise_fn=fn,
        system_name=args.system,
        max_samples=args.max_samples,
        compute_fcs=not args.no_fcs,
    )
