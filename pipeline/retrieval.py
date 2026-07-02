"""
pipeline/retrieval.py
---------------------
Stage 1: Evidence retrieval.

Scores each sentence in the source article using a hybrid of:
  - BM25 lexical scoring (rank_bm25)
  - Sentence-embedding cosine similarity (sentence-transformers)

Returns two objects:
  selected_context : top-K sentences joined into a string for BART input
  evidence_pool    : all sentences with scores, for NLI verification downstream

The TextRank baseline (baselines/textrank.py) is retained as an ablation arm
and can be swapped in by setting method="textrank" in get_evidence().
"""

from pathlib import Path
import sys
import logging
from typing import List

import numpy as np
import nltk
nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
nltk.download("punkt", quiet=True)       # fallback for older NLTK
from nltk.tokenize import sent_tokenize, word_tokenize
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    EMBED_MODEL, RETRIEVAL_K,
    BM25_WEIGHT, EMBED_WEIGHT,
    TOKEN_BUDGET,
)
from utils.hf_local import configure_hf_offline, hf_from_pretrained_kwargs

log = logging.getLogger(__name__)


class EvidenceRetriever:
    """
    Hybrid BM25 + sentence-embedding evidence retriever.

    The retriever sentences the article, scores each sentence by:
        hybrid_score = BM25_WEIGHT * bm25_score + EMBED_WEIGHT * cosine_sim

    where the query for both BM25 and embedding similarity is the
    article's first sentence (lead sentence as pseudo-query) combined
    with all other sentences to form a self-retrieval setup.

    This is equivalent to extracting the most salient sentences
    relative to the article's own information density — appropriate
    for single-document summarisation without an external query.
    """

    def __init__(
        self,
        embed_model_name: str = EMBED_MODEL,
        top_k: int = RETRIEVAL_K,
        bm25_weight: float = BM25_WEIGHT,
        embed_weight: float = EMBED_WEIGHT,
        token_budget: int = TOKEN_BUDGET,
    ):
        self.top_k        = top_k
        self.bm25_weight  = bm25_weight
        self.embed_weight = embed_weight
        self.token_budget = token_budget
        self._embed_model = None
        self._embed_model_name = embed_model_name

    @property
    def embed_model(self) -> SentenceTransformer:
        if self._embed_model is None:
            log.info("Loading sentence-transformer: %s", self._embed_model_name)
            configure_hf_offline()
            kwargs = hf_from_pretrained_kwargs()
            self._embed_model = SentenceTransformer(self._embed_model_name, **kwargs)
        return self._embed_model

    # ── BM25 scoring ──────────────────────────────────────────────────────────

    def _bm25_scores(self, sentences: List[str]) -> np.ndarray:
        """
        Treat each sentence as a document. Query = concat of all sentences
        (article-level tf-idf style scoring).
        """
        tokenised_sents = [word_tokenize(s.lower()) for s in sentences]
        bm25  = BM25Okapi(tokenised_sents)
        # Query: all unique tokens across the article
        query = list({tok for sent in tokenised_sents for tok in sent})
        scores = np.array(bm25.get_scores(query))
        # Normalise to [0, 1]
        if scores.max() > 0:
            scores = scores / scores.max()
        return scores

    # ── Embedding similarity scoring ──────────────────────────────────────────

    def _embedding_scores(self, sentences: List[str]) -> np.ndarray:
        """
        Sentence-level cosine similarity to the article centroid embedding.
        Centroid = mean of all sentence embeddings.
        """
        embeddings = self.embed_model.encode(
            sentences, show_progress_bar=False, convert_to_numpy=True
        )
        centroid = embeddings.mean(axis=0, keepdims=True)
        sims     = cosine_similarity(embeddings, centroid).flatten()
        if sims.max() > 0:
            sims = sims / sims.max()
        return sims

    # ── Token budget enforcement ───────────────────────────────────────────────

    def _enforce_token_budget(
        self, sentences: List[str], ranked_indices: List[int]
    ) -> List[int]:
        """
        Select as many top-ranked sentences as fit within the token budget.
        Approximation: 1 token ≈ 0.75 words (conservative).
        """
        selected = []
        token_count = 0
        for idx in ranked_indices:
            word_count  = len(sentences[idx].split())
            token_est   = int(word_count / 0.75)
            if token_count + token_est > self.token_budget:
                break
            selected.append(idx)
            token_count += token_est
            if len(selected) >= self.top_k:
                break
        return selected

    # ── Public API ────────────────────────────────────────────────────────────

    def get_evidence(self, article: str, method: str = "hybrid") -> dict:
        """
        Main entry point.

        Args:
            article : source news article text
            method  : "hybrid" (default) | "bm25" | "embedding" | "textrank"
                      "textrank" delegates to baselines/textrank.py

        Returns:
            {
              "selected_context" : str   — top-K sentences for BART input
              "evidence_pool"    : list  — all sentences with hybrid scores
              "selected_indices" : list  — original indices of selected sents
              "method"           : str
            }
        """
        if method == "textrank":
            from baselines.textrank import TextRankSummarizer
            tr = TextRankSummarizer(top_k=self.top_k)
            return tr.get_context(article)

        sentences = sent_tokenize(article)
        if not sentences:
            return {
                "selected_context": "",
                "evidence_pool":    [],
                "selected_indices": [],
                "method":           method,
            }

        # ── Score each sentence ───────────────────────────────────────────────
        bm25_scores  = self._bm25_scores(sentences)
        embed_scores = self._embedding_scores(sentences)

        if method == "bm25":
            hybrid = bm25_scores
        elif method == "embedding":
            hybrid = embed_scores
        else:   # "hybrid"
            hybrid = (
                self.bm25_weight  * bm25_scores +
                self.embed_weight * embed_scores
            )

        # ── Build evidence pool (all sentences, sorted by score) ──────────────
        evidence_pool = [
            {
                "index":       i,
                "sentence":    s,
                "bm25_score":  float(bm25_scores[i]),
                "embed_score": float(embed_scores[i]),
                "hybrid_score": float(hybrid[i]),
            }
            for i, s in enumerate(sentences)
        ]
        evidence_pool_sorted = sorted(
            evidence_pool, key=lambda x: x["hybrid_score"], reverse=True
        )

        # ── Select top-K within token budget ──────────────────────────────────
        ranked_by_score   = [e["index"] for e in evidence_pool_sorted]
        selected_indices  = self._enforce_token_budget(sentences, ranked_by_score)

        # Restore original order for coherent reading
        selected_indices_ordered = sorted(selected_indices)
        selected_sentences = [sentences[i] for i in selected_indices_ordered]
        selected_context   = " ".join(selected_sentences)

        return {
            "selected_context":  selected_context,
            "evidence_pool":     evidence_pool,        # all, unfiltered
            "selected_indices":  selected_indices_ordered,
            "method":            method,
        }

    def __call__(self, article: str, method: str = "hybrid") -> dict:
        return self.get_evidence(article, method=method)


# ── CLI smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = (
        "NASA announced on Thursday that its Artemis programme will send "
        "astronauts back to the Moon in 2026. The mission will include "
        "the first woman and first person of colour to walk on the lunar surface. "
        "The agency has been developing the Space Launch System rocket for over "
        "a decade at a cost of more than 20 billion dollars. "
        "Critics have questioned whether the timeline is achievable given "
        "recent technical setbacks. NASA administrator Bill Nelson expressed "
        "confidence that the programme remains on track."
    )
    retriever = EvidenceRetriever(top_k=3)
    result    = retriever.get_evidence(sample, method="hybrid")
    print("Selected context:\n", result["selected_context"])
    print("\nEvidence pool (top 3):")
    for e in result["evidence_pool"][:3]:
        print(f"  [{e['index']}] score={e['hybrid_score']:.3f} — {e['sentence'][:80]}")
