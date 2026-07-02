"""Helpers for cache-only Hugging Face loading."""

import os

from config import MODEL_LOCAL_FILES_ONLY


if MODEL_LOCAL_FILES_ONLY:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def configure_hf_offline() -> None:
    """Set offline env vars when cache-only mode is enabled."""
    if not MODEL_LOCAL_FILES_ONLY:
        return
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def hf_from_pretrained_kwargs() -> dict:
    """Common kwargs for from_pretrained-style loaders."""
    if not MODEL_LOCAL_FILES_ONLY:
        return {}
    return {"local_files_only": True}
