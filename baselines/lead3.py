"""
baselines/lead3.py
------------------
Lead-3 baseline: return the first 3 sentences of the article.

This is the mandatory minimum bar for any news summarisation system.
See: See et al. (ACL 2017) for discussion of lead bias in CNN/DailyMail.
"""

from pathlib import Path
import sys
import nltk
nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
nltk.download("punkt", quiet=True)       # fallback for older NLTK
from nltk.tokenize import sent_tokenize

sys.path.append(str(Path(__file__).parent.parent))


class Lead3Summarizer:
    """
    Returns the first N sentences of an article.
    Default N=3, which is the standard Lead-3 baseline.
    """

    def __init__(self, n: int = 3):
        self.n = n
        self.name = f"Lead-{n}"

    def summarise(self, article: str) -> dict:
        """
        Args:
            article: raw article text

        Returns:
            dict with keys:
              summary (str): the generated summary
              fallback (bool): always False for this baseline
              method (str): baseline name
        """
        sentences = sent_tokenize(article)
        selected  = sentences[: self.n]
        summary   = " ".join(selected)
        return {
            "summary":  summary,
            "fallback": False,
            "method":   self.name,
        }

    # Alias for uniform interface with pipeline
    def __call__(self, article: str) -> dict:
        return self.summarise(article)


if __name__ == "__main__":
    sample = (
        "London, England (Reuters) -- Harry Potter star Daniel Radcliffe "
        "gains access to a reported 20 million in inheritances from the "
        "late producer David Heyman. Radcliffe's spokesman confirmed the "
        "windfall last week. The 18-year-old actor said he was relieved. "
        "He plans to give away most of his fortune to charity."
    )
    model = Lead3Summarizer()
    result = model.summarise(sample)
    print("Lead-3 summary:", result["summary"])
