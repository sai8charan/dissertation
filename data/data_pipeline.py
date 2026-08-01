"""
data/data_pipeline.py
---------------------
Loads CNN/DailyMail 3.0.0, cleans the text, performs a deterministic
70/15/15 train/val/test split, and computes corpus statistics.

Usage:
    from data.data_pipeline import get_datasets, corpus_stats
    splits = get_datasets()        # returns DatasetDict
    stats  = corpus_stats(splits)  # prints + returns dict
"""

import re
import logging
from pathlib import Path

import numpy as np
from datasets import load_dataset, DatasetDict

import sys
sys.path.append(str(Path(__file__).parent.parent))
from config import (
    DATASET_NAME, DATASET_VERSION, ARTICLE_COL, SUMMARY_COL,
    DATA_DIR, SEED, MAX_TRAIN_SAMPLES,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _ensure_nltk_punkt() -> None:
    """Download punkt only if it is not already available locally."""
    import nltk

    try:
        nltk.data.find("tokenizers/punkt")
        return
    except LookupError:
        pass

    nltk.download("punkt", quiet=True)


# ── Text cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """Remove CNN/DailyMail boilerplate and normalise whitespace."""
    # Remove "(CNN)" / "(CNN) --" prefix common in CNN articles
    text = re.sub(r"^\s*\(CNN\)\s*[-–—]?\s*", "", text)
    # Remove "(By <Name>)" and similar bylines
    text = re.sub(r"\(By\s+[^)]+\)", "", text)
    # Collapse multiple newlines / spaces
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def preprocess_example(example: dict) -> dict:
    """Clean article and summary; add sentence count."""
    from nltk.tokenize import sent_tokenize

    article  = clean_text(example[ARTICLE_COL])
    summary  = clean_text(example[SUMMARY_COL])
    # Replace newline-separated highlights with a single paragraph
    summary  = summary.replace("\n", " ")
    sents    = sent_tokenize(article)
    return {
        ARTICLE_COL: article,
        SUMMARY_COL: summary,
        "article_sents": sents,
        "num_sents":     len(sents),
        "article_len":   len(article.split()),
        "summary_len":   len(summary.split()),
    }


# ── Split helper ──────────────────────────────────────────────────────────────

def _split_train_val_test(ds):
    """
    CNN/DailyMail ships with train/validation/test splits.
    We keep those but optionally subsample training for fast experiments.
    """
    train = ds["train"]
    val   = ds["validation"]
    test  = ds["test"]

    if MAX_TRAIN_SAMPLES is not None:
        train = train.shuffle(seed=SEED).select(range(MAX_TRAIN_SAMPLES))
        log.info("Subsampling train to %d examples", MAX_TRAIN_SAMPLES)

    return DatasetDict({"train": train, "validation": val, "test": test})


_CACHED_SPLITS: DatasetDict = None


def get_datasets(force_reprocess: bool = False) -> DatasetDict:
    """
    Load, clean, and split CNN/DailyMail.
    Results are cached in DATA_DIR and in-memory to avoid repeated downloads and disk I/O.

    Returns:
        DatasetDict with keys 'train', 'validation', 'test'.
        Each example has columns:
          article, highlights, article_sents, num_sents,
          article_len, summary_len.
    """
    global _CACHED_SPLITS
    if _CACHED_SPLITS is not None and not force_reprocess:
        return _CACHED_SPLITS

    cache_path = DATA_DIR / "cnn_dm_processed"

    if cache_path.exists() and not force_reprocess:
        log.info("Loading processed dataset from local cache: %s", cache_path)
        from datasets import load_from_disk
        try:
            _CACHED_SPLITS = load_from_disk(str(cache_path))
            return _CACHED_SPLITS
        except Exception as exc:
            log.warning("Cached processed dataset is unreadable (%s). Reprocessing.", exc)

    log.info("Processed cache missing or reprocess requested. Loading raw dataset…")
    # Prefer local HF cache when available; download only if missing.
    raw = load_dataset(
        DATASET_NAME,
        DATASET_VERSION,
        download_mode="reuse_dataset_if_exists",
    )

    _ensure_nltk_punkt()
    log.info("Cleaning and tokenising sentences …")
    processed = raw.map(
        preprocess_example,
        num_proc=4,
        desc="Preprocessing",
    )

    splits = _split_train_val_test(processed)

    log.info("Saving processed dataset to %s", cache_path)
    splits.save_to_disk(str(cache_path))
    _CACHED_SPLITS = splits
    return splits


def corpus_stats(splits: DatasetDict) -> dict:
    """
    Compute and print corpus statistics for the dissertation Chapter 3.

    Returns dict with keys:
        train_size, val_size, test_size,
        mean_article_len, median_article_len, std_article_len,
        mean_summary_len, median_summary_len,
        mean_num_sents, compression_ratio
    """
    train = splits["train"]

    art_lens  = np.array(train["article_len"])
    sum_lens  = np.array(train["summary_len"])
    num_sents = np.array(train["num_sents"])

    stats = {
        "train_size":         len(splits["train"]),
        "val_size":           len(splits["validation"]),
        "test_size":          len(splits["test"]),
        "mean_article_len":   float(np.mean(art_lens)),
        "median_article_len": float(np.median(art_lens)),
        "std_article_len":    float(np.std(art_lens)),
        "mean_summary_len":   float(np.mean(sum_lens)),
        "median_summary_len": float(np.median(sum_lens)),
        "mean_num_sents":     float(np.mean(num_sents)),
        "compression_ratio":  float(np.mean(art_lens / (sum_lens + 1e-9))),
    }

    print("\n-- Corpus Statistics (CNN/DailyMail) --------------------------")
    print(f"  Train: {stats['train_size']:,}  Val: {stats['val_size']:,}  "
          f"Test: {stats['test_size']:,}")
    print(f"  Article length (words)  — mean: {stats['mean_article_len']:.0f}  "
          f"median: {stats['median_article_len']:.0f}  "
          f"std: {stats['std_article_len']:.0f}")
    print(f"  Summary length (words)  — mean: {stats['mean_summary_len']:.0f}  "
          f"median: {stats['median_summary_len']:.0f}")
    print(f"  Sentences per article   — mean: {stats['mean_num_sents']:.1f}")
    print(f"  Compression ratio       — {stats['compression_ratio']:.1f}×")
    print("--------------------------------------------------------------\n")

    return stats


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    splits = get_datasets()
    corpus_stats(splits)
    print("Sample article:\n", splits["test"][0][ARTICLE_COL][:500], "…")
    print("\nSample summary:\n", splits["test"][0][SUMMARY_COL])
