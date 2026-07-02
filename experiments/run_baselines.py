"""
experiments/run_baselines.py
----------------------------
Evaluates all four baselines on the CNN/DailyMail test set and
saves a unified comparison table to results/baselines_table.csv.

Baselines:
  1. Lead-3
  2. TextRank
  3. Zero-shot BART
  4. Fine-tuned BART (single-stage, no retrieval)

Run:
    python experiments/run_baselines.py --max_samples 500
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from evaluation.eval_metrics import evaluate_system
from config import RESULTS_DIR, BART_CKPT, USE_SELF_TRAINED_BART

log = logging.getLogger(__name__)


def run_all_baselines(max_samples: int = 100, compute_fcs: bool = True):
    from baselines.lead3 import Lead3Summarizer
    from baselines.textrank import TextRankSummarizer
    from baselines.bart_baseline import BartBaseline

    systems = {
        "Lead-3":           Lead3Summarizer(),
        "TextRank":         TextRankSummarizer(),
        "BART-zero-shot":   BartBaseline(mode="zeroshot"),
    }

    if USE_SELF_TRAINED_BART and BART_CKPT.exists() and any(BART_CKPT.iterdir()):
        try:
            systems["BART-fine-tuned"] = BartBaseline(mode="finetuned")
        except FileNotFoundError as e:
            log.warning("%s. Skipping BART-fine-tuned baseline.", e)
    else:
        systems["BART-pretrained"] = BartBaseline(mode="finetuned")

    all_metrics = []
    for name, model in systems.items():
        log.info("Running: %s", name)
        metrics = evaluate_system(
            summarise_fn=model,
            system_name=name,
            max_samples=max_samples,
            compute_fcs=compute_fcs,
            save_results=True,
        )
        all_metrics.append(metrics)

    df = pd.DataFrame(all_metrics).set_index("system")
    table_path = RESULTS_DIR / "baselines_table.csv"
    df.to_csv(table_path)
    print("\n-- Baseline Comparison --------------------------------------")
    print(df.to_string())
    print(f"\nSaved to {table_path}")
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--max_samples", type=int, default=100)
    parser.add_argument("--no_fcs", action="store_true")
    args = parser.parse_args()
    run_all_baselines(max_samples=args.max_samples, compute_fcs=not args.no_fcs)
