"""
pipeline/verifier.py
--------------------
Stage 3: Evidence verification.

For each candidate summary:
  1. Split the summary into sentences.
  2. For each summary sentence, find its best-matching evidence sentence
     from the evidence pool using the NLI model's entailment score.
  3. The Factual Consistency Score (FCS) for the candidate is the mean
     entailment probability across all summary sentences.
  4. Return the FCS and a sentence-level evidence trace (which source
     sentence best supports each summary sentence).

Model: cross-encoder/nli-deberta-v3-base
  — Compact, fast, strong NLI performance.
  — Returns logits for [contradiction, neutral, entailment].

Design note (from mid-sem report):
  Sentence-level NLI verification is a tractable approximation of
  full atomic-claim verification (FActScore-style). The ACL 2026
  stress-testing paper (Mujahid et al.) confirms that NLI-based metrics
  remain reliable for short-document settings like CNN/DailyMail,
  which is exactly where this verifier is applied.
"""

from pathlib import Path
import sys
import logging
from typing import List, Dict

import numpy as np
import torch
import nltk
nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
nltk.download("punkt", quiet=True)       # fallback for older NLTK
from nltk.tokenize import sent_tokenize
from sentence_transformers import CrossEncoder

sys.path.append(str(Path(__file__).parent.parent))
from config import NLI_MODEL, NLI_BATCH_SIZE, FCS_THRESHOLD
from utils.hf_local import configure_hf_offline, hf_from_pretrained_kwargs

log = logging.getLogger(__name__)


class EvidenceVerifier:
    """
    NLI-based factual consistency verifier.

    Computes a Factual Consistency Score (FCS) ∈ [0, 1] for each
    candidate summary, by checking entailment between each summary
    sentence and its best-matching evidence pool sentence.

    FCS = mean(max_entailment_prob per summary sentence)

    Additionally returns a sentence-level evidence trace showing
    which source sentence supports each generated sentence.
    """

    # DeBERTa NLI label order: [contradiction, neutral, entailment]
    _ENTAILMENT_IDX = 2

    def __init__(
        self,
        model_name: str = NLI_MODEL,
        batch_size: int = NLI_BATCH_SIZE,
        fcs_threshold: float = FCS_THRESHOLD,
    ):
        self.batch_size    = batch_size
        self.fcs_threshold = fcs_threshold
        log.info("Loading NLI model: %s", model_name)
        configure_hf_offline()
        kwargs = hf_from_pretrained_kwargs()
        self.model = CrossEncoder(model_name, max_length=512, **kwargs)
        self.name  = "NLI-DeBERTa"

    # ── Core scoring ──────────────────────────────────────────────────────────

    def _entailment_probs(
        self, premise: str, hypotheses: List[str]
    ) -> np.ndarray:
        """
        Score a single premise against a list of hypotheses.
        Returns entailment probabilities (softmaxed logits[:, 2]).
        """
        pairs  = [(premise, h) for h in hypotheses]
        logits = self.model.predict(
            pairs, apply_softmax=False, batch_size=self.batch_size
        )
        probs  = torch.softmax(torch.tensor(logits), dim=-1).numpy()
        return probs[:, self._ENTAILMENT_IDX]

    def _score_one_summary_sentence(
        self, summary_sent: str, evidence_pool: List[Dict]
    ) -> Dict:
        """
        Find the best-supporting evidence sentence for one summary sentence.

        Returns:
            {
              "summary_sent"   : str,
              "best_evidence"  : str,
              "evidence_index" : int,
              "entail_prob"    : float,
            }
        """
        evidence_sents = [e["sentence"] for e in evidence_pool]
        if not evidence_sents:
            return {
                "summary_sent":   summary_sent,
                "best_evidence":  "",
                "evidence_index": -1,
                "entail_prob":    0.0,
            }

        probs     = self._entailment_probs(
            premise=summary_sent, hypotheses=evidence_sents
        )
        best_idx  = int(np.argmax(probs))
        return {
            "summary_sent":   summary_sent,
            "best_evidence":  evidence_pool[best_idx]["sentence"],
            "evidence_index": evidence_pool[best_idx].get("index", best_idx),
            "entail_prob":    float(probs[best_idx]),
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def verify_candidate(
        self, candidate: str, evidence_pool: List[Dict]
    ) -> Dict:
        """
        Verify a single candidate summary against the evidence pool.

        Args:
            candidate    : generated summary string
            evidence_pool: list of dicts from retrieval stage, each with
                           at least {"sentence": str, "index": int}

        Returns:
            {
              "fcs"            : float  — mean entailment prob ∈ [0,1]
              "passes"         : bool   — True if fcs >= fcs_threshold
              "evidence_trace" : list   — per-sentence verification details
            }
        """
        summary_sents = sent_tokenize(candidate)
        if not summary_sents:
            return {"fcs": 0.0, "passes": False, "evidence_trace": []}

        trace = [
            self._score_one_summary_sentence(s, evidence_pool)
            for s in summary_sents
        ]
        fcs = float(np.mean([t["entail_prob"] for t in trace]))

        return {
            "fcs":            fcs,
            "passes":         fcs >= self.fcs_threshold,
            "evidence_trace": trace,
        }

    def verify_all(
        self, candidates: List[str], evidence_pool: List[Dict]
    ) -> List[Dict]:
        """
        Verify all N candidates and return their verification results.

        Args:
            candidates   : list of N summary strings
            evidence_pool: evidence pool from retrieval stage

        Returns:
            list of N verification dicts (same order as candidates)
        """
        return [
            self.verify_candidate(c, evidence_pool) for c in candidates
        ]

    def __call__(
        self, candidates: List[str], evidence_pool: List[Dict]
    ) -> List[Dict]:
        return self.verify_all(candidates, evidence_pool)


# ── CLI smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    candidates = [
        "NASA plans to send astronauts to the Moon in 2026.",
        "The Moon mission will cost over 50 billion dollars.",   # inflated → lower FCS
    ]
    pool = [
        {"index": 0, "sentence": "NASA announced its Artemis programme will send astronauts back to the Moon in 2026.", "hybrid_score": 0.9},
        {"index": 1, "sentence": "The agency has spent over 20 billion dollars on the Space Launch System rocket.", "hybrid_score": 0.8},
    ]
    verifier = EvidenceVerifier()
    results  = verifier.verify_all(candidates, pool)
    for i, (cand, res) in enumerate(zip(candidates, results)):
        print(f"\nCandidate {i+1}: {cand}")
        print(f"  FCS={res['fcs']:.3f}  passes={res['passes']}")
        for t in res["evidence_trace"]:
            print(f"  ↳ prob={t['entail_prob']:.3f} | best evidence: {t['best_evidence'][:70]}")
