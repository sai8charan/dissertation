"""
baselines/bart_baseline.py
--------------------------
Two BART baselines:
  1. Zero-shot BART  — pre-trained, no fine-tuning, truncated input
  2. Fine-tuned BART — fine-tuned on CNN/DailyMail, single-stage (no retrieval)

Both implement the same summarise() interface as all other baselines.
"""

from pathlib import Path
import sys
import logging
from typing import Optional

import torch
from transformers import BartTokenizer, BartForConditionalGeneration

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    BART_ZERO_SHOT_MODEL, BART_MODEL, BART_CKPT,
    BART_MAX_INPUT, BART_MAX_OUTPUT,
    USE_SELF_TRAINED_BART,
    NUM_BEAMS,
)

log = logging.getLogger(__name__)


class BartBaseline:
    """
    BART summariser.

    mode="zeroshot" : loads facebook/bart-large weights, no fine-tuning.
    mode="finetuned": if USE_SELF_TRAINED_BART=True and checkpoint exists,
                       loads from BART_CKPT; otherwise uses configured
                       pretrained source (BART_FINETUNE_BASE_MODEL).
    """

    def __init__(
        self,
        mode: str = "finetuned",
        device: Optional[str] = None,
        max_input: int  = BART_MAX_INPUT,
        max_output: int = BART_MAX_OUTPUT,
        num_beams: int  = 4,
    ):
        assert mode in ("zeroshot", "finetuned"), \
            "mode must be 'zeroshot' or 'finetuned'"

        self.mode       = mode
        self.max_input  = max_input
        self.max_output = max_output
        self.num_beams  = num_beams
        self.device     = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if mode == "finetuned":
            if USE_SELF_TRAINED_BART and BART_CKPT.exists() and any(BART_CKPT.iterdir()):
                model_path = str(BART_CKPT)
                self.name = "BART-fine-tuned"
            else:
                model_path = BART_MODEL
                self.name = "BART-pretrained"
        else:
            model_path = BART_ZERO_SHOT_MODEL
            self.name = "BART-zero-shot"

        log.info("Loading %s from %s …", self.name, model_path)
        self.tokenizer = BartTokenizer.from_pretrained(model_path)
        self.model     = BartForConditionalGeneration.from_pretrained(model_path)
        self.model.eval()
        self.model.to(self.device)

    @torch.no_grad()
    def summarise(self, article: str) -> dict:
        """
        Greedy/beam-search summarisation for baseline comparison.
        (The pipeline uses nucleus sampling; baselines use beam for fair ROUGE.)

        Returns:
            dict with keys: summary, fallback, method
        """
        inputs = self.tokenizer(
            article,
            max_length=self.max_input,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        output_ids = self.model.generate(
            **inputs,
            max_new_tokens=self.max_output,
            num_beams=self.num_beams,
            no_repeat_ngram_size=3,
            length_penalty=2.0,
            early_stopping=True,
        )

        summary = self.tokenizer.decode(
            output_ids[0],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        return {
            "summary":  summary,
            "fallback": False,
            "method":   self.name,
        }

    def __call__(self, article: str) -> dict:
        return self.summarise(article)


if __name__ == "__main__":
    sample = (
        "Scientists at MIT have developed a new method for storing renewable "
        "energy using liquid metal batteries. The breakthrough could allow "
        "solar and wind energy to be stored at grid scale. The batteries use "
        "cheap, abundant materials including magnesium and antimony. "
        "Initial tests show an energy efficiency of over 80 percent. "
        "The researchers expect to commercialise the technology within five years."
    )
    # Zero-shot baseline (no training needed)
    model  = BartBaseline(mode="zeroshot")
    result = model.summarise(sample)
    print("Zero-shot BART:", result["summary"])
