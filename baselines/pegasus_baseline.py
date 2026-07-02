"""
baselines/pegasus_baseline.py
-----------------------------
Direct PEGASUS baseline.

google/pegasus-cnn_dailymail is already trained on CNN/DailyMail, so this
project loads it directly instead of fine-tuning it again.

The class mirrors the baseline interface used elsewhere in the repository:
  - summarise(article) -> dict
  - __call__(article)  -> dict
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    PEGASUS_MODEL,
    PEGASUS_MAX_INPUT,
    PEGASUS_MAX_OUTPUT,
)
from utils.hf_local import configure_hf_offline, hf_from_pretrained_kwargs

log = logging.getLogger(__name__)


class PegasusBaseline:
    """
    PEGASUS summariser loaded directly from the Hugging Face model hub.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        max_input: int = PEGASUS_MAX_INPUT,
        max_output: int = PEGASUS_MAX_OUTPUT,
        num_beams: int = 4,
    ):
        self.name = "PEGASUS-pretrained"
        self.max_input = max_input
        self.max_output = max_output
        self.num_beams = num_beams
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        model_path = PEGASUS_MODEL
        log.info("Loading %s from %s ...", self.name, model_path)
        configure_hf_offline()
        kwargs = hf_from_pretrained_kwargs()
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, **kwargs)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path, **kwargs)
        self.model.eval()
        self.model.to(self.device)

    @torch.no_grad()
    def summarise(self, article: str) -> dict:
        """
        Beam-search PEGASUS summarisation for comparison against BART.
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
            "summary": summary,
            "fallback": False,
            "method": self.name,
        }

    def __call__(self, article: str) -> dict:
        return self.summarise(article)


if __name__ == "__main__":
    sample = (
        "NASA announced its Artemis programme will send astronauts back to "
        "the Moon in 2026. The agency has spent over 20 billion dollars on "
        "the Space Launch System rocket. NASA administrator Bill Nelson said "
        "the programme remains on track despite recent setbacks."
    )
    model = PegasusBaseline()
    result = model.summarise(sample)
    print("PEGASUS summary:", result["summary"])
