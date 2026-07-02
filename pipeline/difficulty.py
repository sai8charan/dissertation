"""
pipeline/difficulty.py
----------------------
Difficulty estimation utilities for the Difficulty-Aware Safety Switch.

The difficulty score D is a weighted combination of three normalized signals:
  - length complexity
  - entity density
  - retrieval uncertainty

D is then mapped to a dynamic factuality threshold:
  threshold = base_threshold + alpha * D
"""

import re
from typing import Dict, List

from config import (
    DIFFICULTY_BASE_THRESHOLD,
    DIFFICULTY_ALPHA,
    DIFFICULTY_MAX_THRESHOLD,
    DIFF_WEIGHT_LENGTH,
    DIFF_WEIGHT_ENTITY,
    DIFF_WEIGHT_UNCERTAINTY,
    DIFF_LENGTH_MIN_WORDS,
    DIFF_LENGTH_MAX_WORDS,
    DIFF_ENTITY_MIN_PER_100W,
    DIFF_ENTITY_MAX_PER_100W,
)


class DifficultyAwareSafetySwitch:
    """Computes article difficulty and maps it to a dynamic threshold."""

    _MONTH_TOKENS = {
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
    }

    _COMMON_NON_ENTITY_CAPS = {
        "the", "a", "an", "this", "that", "these", "those", "it", "its", "he", "she", "they",
        "we", "you", "i", "in", "on", "at", "for", "with", "from", "to", "and", "but", "or",
        "if", "as", "by", "of", "is", "are", "was", "were", "be", "been", "being",
    }

    def __init__(
        self,
        base_threshold: float = DIFFICULTY_BASE_THRESHOLD,
        alpha: float = DIFFICULTY_ALPHA,
        max_threshold: float = DIFFICULTY_MAX_THRESHOLD,
    ):
        self.base_threshold = float(base_threshold)
        self.alpha = float(alpha)
        self.max_threshold = float(max_threshold)

        self.w_len = float(DIFF_WEIGHT_LENGTH)
        self.w_ent = float(DIFF_WEIGHT_ENTITY)
        self.w_unc = float(DIFF_WEIGHT_UNCERTAINTY)

    @staticmethod
    def _clip01(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _normalize(value: float, vmin: float, vmax: float) -> float:
        if vmax <= vmin:
            return 0.0
        return DifficultyAwareSafetySwitch._clip01((float(value) - vmin) / (vmax - vmin))

    @staticmethod
    def _simple_sentence_split(text: str) -> List[str]:
        sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if sents:
            return sents
        stripped = text.strip()
        if stripped:
            return [stripped]
        return []

    @staticmethod
    def _word_tokens(text: str) -> List[str]:
        return re.findall(r"[A-Za-z][A-Za-z\-']*|\d+(?:[\.,]\d+)?", text)

    def _length_signal(self, article: str) -> Dict[str, float]:
        words = self._word_tokens(article)
        word_count = len(words)
        norm = self._normalize(word_count, DIFF_LENGTH_MIN_WORDS, DIFF_LENGTH_MAX_WORDS)
        return {
            "raw": float(word_count),
            "norm": norm,
        }

    def _entity_density_signal(self, article: str) -> Dict[str, float]:
        tokens = self._word_tokens(article)
        if not tokens:
            return {"raw": 0.0, "norm": 0.0}

        entity_like = 0
        for tok in tokens:
            low = tok.lower()
            has_digit = any(ch.isdigit() for ch in tok)
            looks_cap = tok[0].isupper() and len(tok) > 2 and low not in self._COMMON_NON_ENTITY_CAPS
            looks_month = low in self._MONTH_TOKENS
            if has_digit or looks_cap or looks_month:
                entity_like += 1

        per_100_words = (entity_like / max(len(tokens), 1)) * 100.0
        norm = self._normalize(per_100_words, DIFF_ENTITY_MIN_PER_100W, DIFF_ENTITY_MAX_PER_100W)
        return {
            "raw": float(per_100_words),
            "norm": norm,
        }

    def _retrieval_uncertainty_signal(self, evidence_pool: List[Dict]) -> Dict[str, float]:
        if not evidence_pool:
            return {"raw": 0.0, "norm": 0.0}

        scores = sorted(
            [float(e.get("hybrid_score", 0.0)) for e in evidence_pool],
            reverse=True,
        )
        if len(scores) < 2:
            return {"raw": 0.0, "norm": 0.0}

        top_margin = max(0.0, scores[0] - scores[1])
        uncertainty = self._clip01(1.0 - top_margin)
        return {
            "raw": uncertainty,
            "norm": uncertainty,
        }

    def analyze(self, article: str, evidence_pool: List[Dict]) -> Dict:
        """Return normalized signals and combined difficulty score D in [0, 1]."""
        length_sig = self._length_signal(article)
        entity_sig = self._entity_density_signal(article)
        uncert_sig = self._retrieval_uncertainty_signal(evidence_pool)

        difficulty = (
            self.w_len * length_sig["norm"]
            + self.w_ent * entity_sig["norm"]
            + self.w_unc * uncert_sig["norm"]
        )
        difficulty = self._clip01(difficulty)

        sentence_count = len(self._simple_sentence_split(article))

        return {
            "difficulty": difficulty,
            "components": {
                "length_norm": length_sig["norm"],
                "entity_norm": entity_sig["norm"],
                "uncertainty_norm": uncert_sig["norm"],
            },
            "raw": {
                "word_count": length_sig["raw"],
                "entity_per_100_words": entity_sig["raw"],
                "retrieval_uncertainty": uncert_sig["raw"],
                "sentence_count": float(sentence_count),
            },
        }

    def dynamic_threshold(self, difficulty: float) -> float:
        threshold = self.base_threshold + self.alpha * self._clip01(difficulty)
        return min(self.max_threshold, max(0.0, threshold))
