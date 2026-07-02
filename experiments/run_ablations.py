"""
experiments/run_ablations.py
----------------------------
Three ablation studies for the dissertation Chapter 5:

A. Retrieval method
   Compare: TextRank vs BM25-only vs Embedding-only vs Hybrid (BM25+Embed)

B. Best-of-N candidate count
   Compare: N = 1 (greedy/beam) vs 2 vs 3 vs 5 vs 8

C. Verifier + fallback on vs off
   Compare: pipeline WITH verifier+reranker vs WITHOUT (greedy BART output)

Run:
    python experiments/run_ablations.py --ablation A
    python experiments/run_ablations.py --ablation B
    python experiments/run_ablations.py --ablation C
    python experiments/run_ablations.py --ablation all
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from evaluation.eval_metrics import evaluate_system
from config import RESULTS_DIR, USE_SELF_TRAINED_BART

log = logging.getLogger(__name__)


# ── Ablation A: Retrieval method ──────────────────────────────────────────────

def ablation_retrieval_method(max_samples: int = 100):
    from pipeline.pipeline import SummarizationPipeline

    methods = ["textrank", "bm25", "embedding", "hybrid"]
    results = []
    for method in methods:
        log.info("Ablation A — retrieval method: %s", method)
        pipe = SummarizationPipeline(
            use_finetuned=USE_SELF_TRAINED_BART,
            retrieval_method=method,
        )
        m = evaluate_system(
            summarise_fn=pipe,
            system_name=f"retrieval-{method}",
            max_samples=max_samples,
            compute_fcs=True,
            save_results=True,
        )
        results.append(m)

    df = pd.DataFrame(results).set_index("system")
    out = RESULTS_DIR / "ablation_A_retrieval.csv"
    df.to_csv(out)
    print("\n-- Ablation A: Retrieval method ----------------------------")
    print(df[["rouge2", "bertscore_f1", "nli_fcs"]].to_string())
    return df


# ── Ablation B: Best-of-N candidate count ─────────────────────────────────────

def ablation_n_candidates(max_samples: int = 100):
    from pipeline.pipeline import SummarizationPipeline

    n_values = [1, 2, 3, 5, 8]
    results  = []
    for n in n_values:
        log.info("Ablation B — N candidates: %d", n)
        pipe = SummarizationPipeline(
            use_finetuned=USE_SELF_TRAINED_BART,
            n_candidates=n,
        )
        m = evaluate_system(
            summarise_fn=pipe,
            system_name=f"best-of-{n}",
            max_samples=max_samples,
            compute_fcs=True,
            save_results=True,
        )
        results.append(m)

    df = pd.DataFrame(results).set_index("system")
    out = RESULTS_DIR / "ablation_B_n_candidates.csv"
    df.to_csv(out)
    print("\n-- Ablation B: Best-of-N ------------------------------------")
    print(df[["rouge2", "bertscore_f1", "nli_fcs", "mean_latency_s"]].to_string())
    return df


# ── Ablation C: Verifier + fallback on vs off ─────────────────────────────────

def ablation_verifier_onoff(max_samples: int = 100):
    from pipeline.pipeline import SummarizationPipeline
    from pipeline.generator import Generator

    results = []

    # WITH verifier + reranker (full pipeline)
    log.info("Ablation C — WITH verifier+reranker")
    pipe_on = SummarizationPipeline(use_finetuned=USE_SELF_TRAINED_BART)
    m_on = evaluate_system(
        summarise_fn=pipe_on,
        system_name="pipeline-verifier-ON",
        max_samples=max_samples,
        compute_fcs=True,
        save_results=True,
    )
    results.append(m_on)

    # WITHOUT verifier: just take first candidate (greedy BART with retrieval)
    log.info("Ablation C — WITHOUT verifier+reranker")
    from pipeline.retrieval import EvidenceRetriever
    retriever = EvidenceRetriever()
    gen       = Generator(model_key="bart", use_finetuned=USE_SELF_TRAINED_BART, n_candidates=1)

    def pipeline_no_verifier(article: str):
        ret  = retriever.get_evidence(article, method="hybrid")
        ctx  = ret["selected_context"]
        cand = gen.generate_candidates(ctx)
        return {
            "summary":    cand[0] if cand else ctx,
            "fallback":   False,
            "latency_s":  0.0,
        }

    m_off = evaluate_system(
        summarise_fn=pipeline_no_verifier,
        system_name="pipeline-verifier-OFF",
        max_samples=max_samples,
        compute_fcs=True,
        save_results=True,
    )
    results.append(m_off)

    df = pd.DataFrame(results).set_index("system")
    out = RESULTS_DIR / "ablation_C_verifier.csv"
    df.to_csv(out)
    print("\n-- Ablation C: Verifier on vs off ---------------------------")
    print(df[["rouge2", "bertscore_f1", "nli_fcs",
               "hallucination_rate", "fallback_rate"]].to_string())
    return df


# ── Master runner ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--ablation",   choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--max_samples", type=int, default=100)
    args = parser.parse_args()

    if args.ablation in ("A", "all"):
        ablation_retrieval_method(args.max_samples)
    if args.ablation in ("B", "all"):
        ablation_n_candidates(args.max_samples)
    if args.ablation in ("C", "all"):
        ablation_verifier_onoff(args.max_samples)

    # Print combined ablation summary
    print("\n-- All ablation results saved to results/ --------------------")
