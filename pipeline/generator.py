"""
pipeline/generator.py
---------------------
Stage 2: Abstractive generation.

Loads a fine-tuned seq2seq model (BART by default) and generates
N candidate summaries via nucleus sampling (top_p).

The module also supports mBART for the comparison study
(experiments/run_pipeline.py passes --model to switch).

Key design decisions:
  - num_return_sequences > 1 with do_sample=True produces diverse candidates
    that the downstream verifier and reranker can choose between.
  - Beam search is available for baselines (num_beams > 1, do_sample=False),
    where the single-best output is what matters.
"""

from pathlib import Path
import sys
import logging
from typing import List, Optional

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    BART_FINETUNE_BASE_MODEL, BART_CKPT,
    MBART_MODEL, MBART_CKPT,
    BART_MAX_INPUT, BART_MAX_OUTPUT,
    NUM_CANDIDATES, TOP_P, TEMPERATURE,
    USE_SELF_TRAINED_BART, USE_SELF_TRAINED_MBART,
)
from utils.hf_local import configure_hf_offline, hf_from_pretrained_kwargs

log = logging.getLogger(__name__)

# ── Model registry ────────────────────────────────────────────────────────────
_REGISTRY = {
    "bart": {
        "pretrained": BART_FINETUNE_BASE_MODEL,
        "source":     BART_FINETUNE_BASE_MODEL,
        "finetuned":  str(BART_CKPT),
        "use_self_trained": USE_SELF_TRAINED_BART,
        "max_input":  BART_MAX_INPUT,
        "max_output": BART_MAX_OUTPUT,
    },
    "mbart": {
        "pretrained": MBART_MODEL,
        "source":     MBART_MODEL,
        "finetuned":  str(MBART_CKPT),
        "use_self_trained": USE_SELF_TRAINED_MBART,
        "max_input":  BART_MAX_INPUT,
        "max_output": BART_MAX_OUTPUT,
    },
}


class Generator:
    """
    Seq2seq generator with Best-of-N nucleus sampling.

    Args:
        model_key   : "bart" | "mbart"
        use_finetuned: True  → load from checkpoints/<model>_finetuned/
                       False → load pretrained HuggingFace weights (zero-shot)
        n_candidates: number of diverse summaries to generate per article
        top_p       : nucleus sampling probability threshold
        temperature : sampling temperature
        device      : "cuda" / "cpu" / None (auto-detect)
    """

    def __init__(
        self,
        model_key: str = "bart",
        use_finetuned: Optional[bool] = None,
        n_candidates: int = NUM_CANDIDATES,
        top_p: float = TOP_P,
        temperature: float = TEMPERATURE,
        device: Optional[str] = None,
    ):
        self.model_key    = model_key
        self.n_candidates = n_candidates
        self.top_p        = top_p
        self.temperature  = temperature
        self.device       = device or ("cuda" if torch.cuda.is_available() else "cpu")

        cfg = _REGISTRY[model_key]
        if use_finetuned is None:
            use_finetuned = cfg["use_self_trained"]

        if use_finetuned:
            model_path = cfg["finetuned"]
        else:
            model_path = cfg["pretrained"]

        # If self-trained checkpoint doesn't exist yet, fall back to the configured source model.
        if use_finetuned and not Path(model_path).exists():
            log.warning(
                "Self-trained checkpoint not found at %s. Falling back to source model (%s).",
                model_path, cfg["source"]
            )
            model_path = cfg["source"]

        log.info("Loading generator from %s …", model_path)
        configure_hf_offline()
        kwargs = hf_from_pretrained_kwargs()
        self.tokenizer  = AutoTokenizer.from_pretrained(model_path, **kwargs)
        self.model      = AutoModelForSeq2SeqLM.from_pretrained(model_path, **kwargs)
        self.model.eval()
        self.model.to(self.device)

        self.max_input  = cfg["max_input"]
        self.max_output = cfg["max_output"]
        self.name       = f"{model_key}-{'ft' if use_finetuned else 'zs'}"

    # ── Core generation ───────────────────────────────────────────────────────

    @torch.no_grad()
    def generate_candidates(self, context: str) -> List[str]:
        """
        Generate N diverse candidate summaries via nucleus sampling.

        Args:
            context : selected evidence context (output of Stage 1)

        Returns:
            List of N candidate summary strings
        """
        inputs = self.tokenizer(
            context,
            max_length=self.max_input,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.max_output,
            num_beams=1,                      # must be 1 for do_sample=True multi-sequence generation
            num_return_sequences=self.n_candidates,
            do_sample=True,
            top_p=self.top_p,
            temperature=self.temperature,
            no_repeat_ngram_size=3,
        )

        candidates = [
            self.tokenizer.decode(
                ids, skip_special_tokens=True, clean_up_tokenization_spaces=True
            )
            for ids in output_ids
        ]
        return candidates

    @torch.no_grad()
    def generate_beam(self, context: str, num_beams: int = 4) -> str:
        """
        Single best output via beam search — used for baseline comparison,
        not for the main pipeline (which uses nucleus sampling + reranking).
        """
        inputs = self.tokenizer(
            context,
            max_length=self.max_input,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.max_output,
            num_beams=num_beams,
            no_repeat_ngram_size=3,
            length_penalty=2.0,
            early_stopping=True,
        )
        return self.tokenizer.decode(
            output_ids[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )

    # ── Uniform interface ─────────────────────────────────────────────────────

    def __call__(self, context: str) -> List[str]:
        """Returns N candidate summaries."""
        return self.generate_candidates(context)


# ── CLI smoke test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    context = (
        "NASA announced its Artemis programme will send astronauts back to "
        "the Moon in 2026. The agency has spent over 20 billion dollars on "
        "the Space Launch System rocket. NASA administrator Bill Nelson said "
        "the programme remains on track despite recent setbacks."
    )
    gen        = Generator(model_key="bart", use_finetuned=False)
    candidates = gen.generate_candidates(context)
    print(f"Generated {len(candidates)} candidates:")
    for i, c in enumerate(candidates, 1):
        print(f"  [{i}] {c}")
