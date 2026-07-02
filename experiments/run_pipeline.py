"""
experiments/run_pipeline.py
---------------------------
Evaluates the full proposed pipeline against all baselines.
Also runs the direct PEGASUS and mBART comparison study for the
model-justification section of the dissertation.

Run:
    python experiments/run_pipeline.py --max_samples 500

    # Re-run only the pipeline (e.g. after an interruption):
    python experiments/run_pipeline.py --max_samples 300 --systems pipeline

    # Re-run pipeline + PEGASUS only:
    python experiments/run_pipeline.py --max_samples 300 --systems pipeline pegasus

Output:
    results/full_comparison_table.csv   — all systems side-by-side
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from evaluation.eval_metrics import evaluate_system
from config import RESULTS_DIR, BART_CKPT, USE_SELF_TRAINED_BART, USE_SELF_TRAINED_MBART

log = logging.getLogger(__name__)


def run_full_comparison(
    max_samples: int = 100,
    compute_fcs: bool = True,
    only_systems: list = None,
    safety_mode: str = "dynamic",
):

    from baselines.lead3 import Lead3Summarizer
    from baselines.textrank import TextRankSummarizer
    from baselines.bart_baseline import BartBaseline
    from baselines.pegasus_baseline import PegasusBaseline
    from pipeline.pipeline import SummarizationPipeline

    # ── Build all systems ─────────────────────────────────────────────────────
    systems = {}

    # Baselines (should already exist from run_baselines.py, but run anyway)
    systems["Lead-3"]          = Lead3Summarizer()
    systems["TextRank"]        = TextRankSummarizer()
    systems["BART-zero-shot"]  = BartBaseline(mode="zeroshot")

    if USE_SELF_TRAINED_BART and BART_CKPT.exists() and any(BART_CKPT.iterdir()):
        try:
            systems["BART-fine-tuned"] = BartBaseline(mode="finetuned")
        except FileNotFoundError as e:
            log.warning("%s. Skipping BART-fine-tuned.", e)
    else:
        systems["BART-pretrained"] = BartBaseline(mode="finetuned")

    # Proposed pipeline
    systems["Pipeline (hybrid+verify+rerank)"] = SummarizationPipeline(
        model_key="bart",
        use_finetuned=USE_SELF_TRAINED_BART,
        retrieval_method="hybrid",
        safety_mode=safety_mode,
    )

    # ── PEGASUS comparison ────────────────────────────────────────────────────
    systems["PEGASUS-pretrained"] = PegasusBaseline()

    # ── mBART comparison ──────────────────────────────────────────────────────
    from pipeline.generator import Generator
    mbart_gen = Generator(model_key="mbart", use_finetuned=USE_SELF_TRAINED_MBART, n_candidates=1)

    def mbart_summarise(article):
        summary = mbart_gen.generate_beam(article)
        return {"summary": summary, "fallback": False}

    systems["mBART-pretrained" if not USE_SELF_TRAINED_MBART else "mBART-fine-tuned"] = mbart_summarise

    # ── Filter to requested systems ───────────────────────────────────────────
    _ALIASES = {
        "pipeline": "Pipeline (hybrid+verify+rerank)",
        "pegasus":  "PEGASUS-pretrained",
        "mbart":    "mBART-pretrained",
        "bart":     "BART-zero-shot",
        "lead3":    "Lead-3",
        "textrank": "TextRank",
    }
    if only_systems:
        resolved = {_ALIASES.get(s, s) for s in only_systems}
        systems = {k: v for k, v in systems.items() if k in resolved}
        log.info("Running only: %s", list(systems.keys()))

    # ── Evaluate all ──────────────────────────────────────────────────────────
    all_metrics = []
    for name, model in systems.items():
        log.info("Evaluating: %s", name)
        metrics = evaluate_system(
            summarise_fn=model,
            system_name=name,
            max_samples=max_samples,
            compute_fcs=compute_fcs,
            save_results=True,
        )
        all_metrics.append(metrics)

    df = pd.DataFrame(all_metrics).set_index("system")
    out = RESULTS_DIR / "full_comparison_table.csv"
    df.to_csv(out)

    print("\n-- Full Comparison Table -------------------------------------")
    display_cols = ["rouge1", "rouge2", "rougeL", "bertscore_f1", "nli_fcs", "fallback_rate"]
    present = [c for c in display_cols if c in df.columns]
    print(df[present].to_string())
    print(f"\nSaved to {out}")
    return df


def run_with_target_check(
    max_samples: int = 100,
    compute_fcs: bool = True,
    only_systems: list = None,
    safety_mode: str = "dynamic",
):
    df = run_full_comparison(
        max_samples=max_samples,
        compute_fcs=compute_fcs,
        only_systems=only_systems,
        safety_mode=safety_mode,
    )
    from evaluation.check_targets import main as check_main
    check_main(RESULTS_DIR / "full_comparison_table.csv")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_samples", type=int, default=100)
    parser.add_argument("--no_fcs", action="store_true")
    parser.add_argument(
        "--check_targets",
        action="store_true",
        help="After evaluation, compare metrics against EXPECTED_TARGETS",
    )
    parser.add_argument(
        "--systems",
        nargs="+",
        default=None,
        metavar="SYS",
        help=(
            "Run only these systems. Choices: pipeline, pegasus, mbart, "
            "bart, lead3, textrank. E.g. --systems pipeline pegasus"
        ),
    )
    parser.add_argument(
        "--safety_mode",
        choices=["fixed", "dynamic"],
        default="dynamic",
        help="Safety switch mode for pipeline system.",
    )
    args = parser.parse_args()
    if args.check_targets:
        run_with_target_check(
            max_samples=args.max_samples,
            compute_fcs=not args.no_fcs,
            only_systems=args.systems,
            safety_mode=args.safety_mode,
        )
    else:
        run_full_comparison(
            max_samples=args.max_samples,
            compute_fcs=not args.no_fcs,
            only_systems=args.systems,
            safety_mode=args.safety_mode,
        )
