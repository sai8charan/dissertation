"""
pipeline/reranker.py
--------------------
Stage 4: Preference reranking and extractive fallback.

Takes N verified candidates and:
  1. Scores each by: final_score = FCS_WEIGHT * fcs + BERTSCORE_WEIGHT * bertscore_f1
  2. Selects the highest-scoring candidate.
  3. If even the best candidate's FCS < FCS_THRESHOLD, falls back to the
     extractive summary produced by Stage 1 (the selected_context).

This Best-of-N reranking is a training-free, inference-time approximation
of RLHF — it optimises for the same objectives (factual consistency +
fluency) that a reward model would be trained on, without the annotation
overhead of full RLHF.

The fallback rate (% of documents that trigger extractive fallback) is
tracked as a system-health metric in the evaluation harness.
"""

from pathlib import Path
import sys
import logging
from typing import List, Dict, Optional

import numpy as np
from bert_score import BERTScorer

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    FCS_WEIGHT, BERTSCORE_WEIGHT,
    BERTSCORE_LANG, FCS_THRESHOLD,
)

log = logging.getLogger(__name__)


class PreferenceReranker:
    """
    Ranks N verified candidates by a weighted combination of:
      - Factual Consistency Score (FCS) from the NLI verifier
      - BERTScore F1 against the retrieved evidence context

    The ranking formula:
        final_score = FCS_WEIGHT * fcs + BERTSCORE_WEIGHT * bertscore_f1

    Weights are set in config.py (default: 0.60 / 0.40).

    An ablation study in experiments/run_ablations.py compares:
      - FCS only (BERTSCORE_WEIGHT=0)
      - BERTScore only (FCS_WEIGHT=0)
      - Current balanced weighting
    to choose the best configuration for the final results chapter.
    """

    def __init__(
        self,
        fcs_weight: float = FCS_WEIGHT,
        bertscore_weight: float = BERTSCORE_WEIGHT,
        fcs_threshold: float = FCS_THRESHOLD,
        bertscore_lang: str = BERTSCORE_LANG,
    ):
        self.fcs_weight       = fcs_weight
        self.bertscore_weight = bertscore_weight
        self.fcs_threshold    = fcs_threshold
        self.bertscore_lang   = bertscore_lang
        # Load roberta-large once at construction time; reused for every article
        # so we never re-download or re-initialise weights during evaluation.
        log.info("Loading BERTScorer (roberta-large) — loaded once, cached for all articles …")
        self._scorer = BERTScorer(lang=bertscore_lang, rescale_with_baseline=False)

    # ── BERTScore computation ─────────────────────────────────────────────────

    def _bertscore_f1s(
        self, candidates: List[str], reference: str
    ) -> List[float]:
        """
        Compute BERTScore F1 for each candidate against the reference context.
        Reference here is the selected_context from Stage 1 (not the gold
        summary — we're measuring relevance to the retrieved evidence).

        Args:
            candidates : list of N summary strings
            reference  : the retrieved evidence context string

        Returns:
            list of N F1 scores ∈ [0, 1]
        """
        references = [reference] * len(candidates)
        _, _, F1   = self._scorer.score(candidates, references)
        return F1.tolist()

    # ── Ranking ───────────────────────────────────────────────────────────────

    def rank(
        self,
        candidates: List[str],
        verifications: List[Dict],
        selected_context: str,
    ) -> Dict:
        """
        Rank candidates and select the best one (or fall back).

        Args:
            candidates       : list of N summary strings from Stage 2
            verifications    : list of N dicts from Stage 3 verifier
            selected_context : evidence context from Stage 1 (fallback text
                               and BERTScore reference)

        Returns:
            {
              "summary"         : str    — chosen summary
              "fallback"        : bool   — True if extractive fallback used
              "best_idx"        : int    — index of best candidate (or -1 if fallback)
              "best_fcs"        : float  — FCS of chosen candidate
              "best_bertscore"  : float  — BERTScore F1 of chosen candidate
              "final_score"     : float  — combined ranking score
              "all_scores"      : list   — scores for all N candidates
              "evidence_trace"  : list   — sentence-level trace of chosen summary
            }
        """
        if not candidates:
            return {
                "summary": selected_context,
                "fallback": True,
                "best_idx": -1,
                "best_fcs": 0.0,
                "best_bertscore": 0.0,
                "final_score": 0.0,
                "all_scores": [],
                "evidence_trace": [],
            }

        # ── BERTScore for all candidates ──────────────────────────────────────
        bs_f1s = self._bertscore_f1s(candidates, selected_context)

        # ── Combined scores ───────────────────────────────────────────────────
        fcs_scores = [v["fcs"] for v in verifications]
        combined   = [
            self.fcs_weight * fcs + self.bertscore_weight * bs
            for fcs, bs in zip(fcs_scores, bs_f1s)
        ]

        all_scores = [
            {
                "candidate_idx": i,
                "fcs":           fcs_scores[i],
                "bertscore_f1":  bs_f1s[i],
                "final_score":   combined[i],
            }
            for i in range(len(candidates))
        ]

        # ── Select best ───────────────────────────────────────────────────────
        best_idx   = int(np.argmax(combined))
        best_fcs   = fcs_scores[best_idx]
        best_bs    = bs_f1s[best_idx]
        best_score = combined[best_idx]

        # ── Extractive fallback check ─────────────────────────────────────────
        if best_fcs < self.fcs_threshold:
            log.debug(
                "FCS %.3f below threshold %.3f → extractive fallback",
                best_fcs, self.fcs_threshold
            )
            return {
                "summary":        selected_context,
                "fallback":       True,
                "best_idx":       -1,
                "best_fcs":       best_fcs,
                "best_bertscore": best_bs,
                "final_score":    best_score,
                "all_scores":     all_scores,
                "evidence_trace": [],
            }

        return {
            "summary":        candidates[best_idx],
            "fallback":       False,
            "best_idx":       best_idx,
            "best_fcs":       best_fcs,
            "best_bertscore": best_bs,
            "final_score":    best_score,
            "all_scores":     all_scores,
            "evidence_trace": verifications[best_idx]["evidence_trace"],
        }

    def __call__(
        self,
        candidates: List[str],
        verifications: List[Dict],
        selected_context: str,
    ) -> Dict:
        return self.rank(candidates, verifications, selected_context)


# ── CLI smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    candidates = [
        "NASA plans to send astronauts to the Moon in 2026.",
        "The Moon programme will cost 50 billion dollars according to NASA.",
        "NASA confirmed the Artemis Moon mission is on track for 2026.",
    ]
    verifications = [
        {"fcs": 0.85, "passes": True,  "evidence_trace": []},
        {"fcs": 0.32, "passes": False, "evidence_trace": []},
        {"fcs": 0.91, "passes": True,  "evidence_trace": []},
    ]
    context = (
        "NASA announced its Artemis programme will send astronauts back to "
        "the Moon in 2026. The agency spent 20 billion dollars on development."
    )
    reranker = PreferenceReranker()
    result   = reranker.rank(candidates, verifications, context)
    print(f"Chosen summary : {result['summary']}")
    print(f"Fallback?      : {result['fallback']}")
    print(f"FCS            : {result['best_fcs']:.3f}")
    print(f"BERTScore F1   : {result['best_bertscore']:.3f}")
    print(f"Final score    : {result['final_score']:.3f}")
