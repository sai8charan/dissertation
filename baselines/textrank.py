"""
baselines/textrank.py
---------------------
TextRank extractive summariser (Mihalcea & Tarau, EMNLP 2004).

Builds a sentence similarity graph, ranks sentences by PageRank,
and returns the top-K sentences in their original order.

Also used as an ablation comparator against the hybrid BM25+embedding
retrieval in the main pipeline (see pipeline/retrieval.py).
"""

from pathlib import Path
import sys
from typing import List

import numpy as np
import networkx as nx
import nltk
nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
nltk.download("punkt", quiet=True)       # fallback for older NLTK
from nltk.tokenize import sent_tokenize
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

sys.path.append(str(Path(__file__).parent.parent))
from config import EMBED_MODEL, RETRIEVAL_K
from utils.hf_local import configure_hf_offline, hf_from_pretrained_kwargs


class TextRankSummarizer:
    """
    Extractive summariser using sentence-embedding based TextRank.

    Steps:
      1. Split article into sentences.
      2. Encode with sentence-transformers.
      3. Build a fully connected similarity graph.
      4. Run PageRank to score sentences.
      5. Return top-K sentences in original order.
    """

    def __init__(
        self,
        model_name: str = EMBED_MODEL,
        top_k: int = RETRIEVAL_K,
        damping: float = 0.85,
    ):
        self.top_k   = top_k
        self.damping = damping
        self.name    = "TextRank"
        self._model  = None          # lazy-loaded
        self._model_name = model_name

    @property
    def model(self):
        if self._model is None:
            configure_hf_offline()
            kwargs = hf_from_pretrained_kwargs()
            self._model = SentenceTransformer(self._model_name, **kwargs)
        return self._model

    def _build_graph(self, embeddings: np.ndarray) -> nx.Graph:
        sim_matrix = cosine_similarity(embeddings)
        np.fill_diagonal(sim_matrix, 0)           # no self-loops
        graph = nx.from_numpy_array(sim_matrix)
        return graph

    def rank_sentences(self, sentences: List[str]) -> List[int]:
        """
        Returns sentence indices sorted by TextRank score (descending).
        """
        if len(sentences) == 1:
            return [0]
        embeddings = self.model.encode(sentences, show_progress_bar=False)
        graph      = self._build_graph(embeddings)
        scores     = nx.pagerank(graph, alpha=self.damping)
        ranked     = sorted(scores, key=scores.get, reverse=True)
        return ranked

    def get_context(self, article: str, top_k: int = None) -> dict:
        """
        Returns selected sentences and a full evidence pool dict.
        Used by pipeline/retrieval.py as the TextRank ablation arm.

        Returns:
            selected_context (str): top-K sentences joined, for BART input
            evidence_pool    (list[dict]): all sentences with scores
        """
        k         = top_k or self.top_k
        sentences = sent_tokenize(article)
        if not sentences:
            return {"selected_context": "", "evidence_pool": []}

        ranked    = self.rank_sentences(sentences)
        scores    = nx.pagerank(
            self._build_graph(
                self.model.encode(sentences, show_progress_bar=False)
            ),
            alpha=self.damping,
        )

        evidence_pool = [
            {"sentence": s, "score": scores[i], "index": i}
            for i, s in enumerate(sentences)
        ]
        evidence_pool.sort(key=lambda x: x["score"], reverse=True)

        # Select top-K, restore original order for coherent reading
        top_indices = sorted(ranked[:k])
        selected    = [sentences[i] for i in top_indices]
        context     = " ".join(selected)

        return {
            "selected_context": context,
            "evidence_pool":    evidence_pool,
        }

    def summarise(self, article: str) -> dict:
        result = self.get_context(article)
        return {
            "summary":  result["selected_context"],
            "fallback": False,
            "method":   self.name,
        }

    def __call__(self, article: str) -> dict:
        return self.summarise(article)


if __name__ == "__main__":
    sample = (
        "The stock market rose sharply on Monday after positive economic "
        "data was released. Investors were encouraged by lower-than-expected "
        "inflation figures. The Dow Jones climbed 400 points by midday. "
        "Analysts noted that the Federal Reserve is likely to maintain its "
        "current interest rate policy given the new data. Tech stocks led "
        "the gains, with Apple and Microsoft both rising over 2 percent."
    )
    model  = TextRankSummarizer(top_k=2)
    result = model.summarise(sample)
    print("TextRank summary:", result["summary"])
