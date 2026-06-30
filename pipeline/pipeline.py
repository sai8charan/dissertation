"""
pipeline/pipeline.py
--------------------
Full pipeline: chains Stages 1–4 into a single summarise() call.

    retrieval → generation → verification → reranking → output

This is the primary interface used by:
  - experiments/run_pipeline.py   (batch evaluation on test set)
  - experiments/run_ablations.py  (ablation experiments)
  - app/app.py                    (Streamlit demo)
  - multilingual/multilingual_study.py

Usage:
    from pipeline.pipeline import SummarizationPipeline
    pipe   = SummarizationPipeline()
    result = pipe.summarise(article_text)
    print(result["summary"])
    print(result["fcs"])
    print(result["fallback"])
"""

from pathlib import Path
import sys
import logging
import time
from typing import Optional, Dict

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    RETRIEVAL_K,
    NUM_CANDIDATES,
    FCS_THRESHOLD,
    USE_SELF_TRAINED_BART,
    USE_SELF_TRAINED_MBART,
)

from pipeline.retrieval import EvidenceRetriever
from pipeline.generator import Generator
from pipeline.verifier  import EvidenceVerifier
from pipeline.reranker  import PreferenceReranker

log = logging.getLogger(__name__)


class SummarizationPipeline:
    """
    End-to-end grounded, verifiable summarisation pipeline.

    Stages:
      1. EvidenceRetriever  — hybrid BM25 + embedding retrieval
      2. Generator          — Best-of-N nucleus sampling (fine-tuned BART)
      3. EvidenceVerifier   — NLI-based factual consistency scoring
      4. PreferenceReranker — selects best candidate or falls back

    All stage configs are read from config.py but can be overridden
    per-experiment via constructor arguments.
    """

    def __init__(
        self,
        model_key: str      = "bart",
        use_finetuned: Optional[bool] = None,
        retrieval_method: str = "hybrid",
        n_candidates: int   = NUM_CANDIDATES,
        retrieval_k: int    = RETRIEVAL_K,
        fcs_threshold: float = FCS_THRESHOLD,
        device: Optional[str] = None,
    ):
        self.retrieval_method = retrieval_method
        log.info("Initialising SummarizationPipeline …")

        if use_finetuned is None:
            use_finetuned = USE_SELF_TRAINED_BART if model_key == "bart" else USE_SELF_TRAINED_MBART

        self.retriever = EvidenceRetriever(top_k=retrieval_k)
        self.generator = Generator(
            model_key=model_key,
            use_finetuned=use_finetuned,
            n_candidates=n_candidates,
            device=device,
        )
        self.verifier  = EvidenceVerifier(fcs_threshold=fcs_threshold)
        self.reranker  = PreferenceReranker(fcs_threshold=fcs_threshold)

        log.info("Pipeline ready. model=%s finetuned=%s retrieval=%s n=%d",
                 model_key, use_finetuned, retrieval_method, n_candidates)

    def summarise(self, article: str) -> Dict:
        """
        Summarise a single news article.

        Args:
            article : raw news article text

        Returns:
            {
              "summary"         : str    — final summary (abstractive or extractive)
              "fallback"        : bool   — True if extractive fallback was triggered
              "fcs"             : float  — factual consistency score of chosen summary
              "bertscore"       : float  — BERTScore F1 of chosen summary
              "final_score"     : float  — combined ranking score
              "selected_context": str    — evidence context fed to generator
              "evidence_pool"   : list   — all sentences with scores
              "evidence_trace"  : list   — sentence-level verification trace
              "n_candidates"    : int    — number of candidates generated
              "latency_s"       : float  — total wall-clock seconds
            }
        """
        t0 = time.time()

        # ── Stage 1: Evidence retrieval ───────────────────────────────────────
        retrieval = self.retriever.get_evidence(
            article, method=self.retrieval_method
        )
        selected_context = retrieval["selected_context"]
        evidence_pool    = retrieval["evidence_pool"]

        if not selected_context.strip():
            log.warning("Empty selected context; returning empty summary.")
            return {
                "summary": "", "fallback": True, "fcs": 0.0,
                "bertscore": 0.0, "final_score": 0.0,
                "selected_context": "", "evidence_pool": [],
                "evidence_trace": [], "n_candidates": 0,
                "latency_s": time.time() - t0,
            }

        # ── Stage 2: Abstractive generation ───────────────────────────────────
        candidates = self.generator.generate_candidates(selected_context)

        # ── Stage 3: Verification ─────────────────────────────────────────────
        verifications = self.verifier.verify_all(candidates, evidence_pool)

        # ── Stage 4: Reranking + fallback ─────────────────────────────────────
        result = self.reranker.rank(candidates, verifications, selected_context)

        latency = round(time.time() - t0, 2)

        return {
            "summary":          result["summary"],
            "fallback":         result["fallback"],
            "fcs":              result["best_fcs"],
            "bertscore":        result["best_bertscore"],
            "final_score":      result["final_score"],
            "selected_context": selected_context,
            "evidence_pool":    evidence_pool,
            "evidence_trace":   result["evidence_trace"],
            "n_candidates":     len(candidates),
            "latency_s":        latency,
        }

    def __call__(self, article: str) -> Dict:
        return self.summarise(article)


# ── CLI smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    article = (
        "NASA announced on Thursday that its Artemis programme will send "
        "astronauts back to the Moon in 2026. The mission will include "
        "the first woman and first person of colour to walk on the lunar surface. "
        "The agency has been developing the Space Launch System rocket for over "
        "a decade at a cost of more than 20 billion dollars. "
        "Critics have questioned whether the timeline is achievable given "
        "recent technical setbacks with the Orion capsule heat shield. "
        "NASA administrator Bill Nelson expressed confidence that the programme "
        "remains on track and that the agency has resolved all major issues."
    )
    pipe   = SummarizationPipeline(use_finetuned=False)  # zero-shot for smoke test
    result = pipe.summarise(article)

    print("\n-- Pipeline result ------------------------------------------")
    print(f"Summary    : {result['summary']}")
    print(f"Fallback?  : {result['fallback']}")
    print(f"FCS        : {result['fcs']:.3f}")
    print(f"BERTScore  : {result['bertscore']:.3f}")
    print(f"Latency    : {result['latency_s']}s")
    print(f"Candidates : {result['n_candidates']}")
    if result["evidence_trace"]:
        print("\nEvidence trace:")
        for t in result["evidence_trace"]:
            print(f"  [{t['entail_prob']:.3f}] {t['summary_sent'][:60]}")
            print(f"    ← {t['best_evidence'][:70]}")
