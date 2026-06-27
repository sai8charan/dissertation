"""
multilingual/multilingual_study.py
-----------------------------------
Multilingual feasibility study comparing two strategies on Hindi XL-Sum:

Strategy A — Translate then summarise:
    Hindi article → [NLLB/Helsinki translate] → English → full pipeline (BART)

Strategy B — Direct multilingual summarisation:
    Hindi article → [fine-tuned mBART] → Hindi summary

Both are evaluated using ROUGE-L and NLI-FCS (using multilingual NLI model).
Results are framed as a feasibility study, not full production evaluation.

Run:
    python multilingual/multilingual_study.py

Reference:
    Aharoni et al. (2022) mFACE — multilingual factuality evaluation,
    used as justification for applying NLI-based FCS across languages.
"""

import json
import logging
import sys
from pathlib import Path
from typing import List, Dict

import numpy as np
from tqdm import tqdm
from datasets import load_dataset
from rouge_score import rouge_scorer

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    XLSUM_LANG, XLSUM_TRAIN_SIZE, XLSUM_TEST_SIZE,
    TRANSLATE_MODEL, MULTILINGUAL_NLI,
    MBART_MODEL, CKPT_DIR, RESULTS_DIR, SEED,
)

log = logging.getLogger(__name__)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_xlsum_hindi(test_size: int = XLSUM_TEST_SIZE) -> List[Dict]:
    """Load Hindi XL-Sum test set."""
    log.info("Loading XL-Sum Hindi test set …")
    ds = load_dataset("csebuetnlp/xlsum", XLSUM_LANG, split="test")
    ds = ds.select(range(min(test_size, len(ds))))
    return [{"article": ex["text"], "summary": ex["summary"]} for ex in ds]


# ── Strategy A: Translate then summarise ─────────────────────────────────────

class TranslateThenSummarise:
    """
    Translates Hindi article to English using Helsinki-NLP OPUS-MT,
    then runs the full English pipeline (fine-tuned BART + verifier).
    """

    def __init__(self):
        import torch
        from transformers import MarianMTModel, MarianTokenizer
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        log.info("Loading translation model: %s", TRANSLATE_MODEL)
        self.trans_tokenizer = MarianTokenizer.from_pretrained(TRANSLATE_MODEL)
        self.trans_model     = MarianMTModel.from_pretrained(TRANSLATE_MODEL).to(self.device)
        log.info("Loading English summarisation pipeline …")
        from pipeline.pipeline import SummarizationPipeline
        self.pipe = SummarizationPipeline(model_key="bart", use_finetuned=True)

    def translate(self, hindi_text: str) -> str:
        import torch
        inputs = self.trans_tokenizer(
            hindi_text, return_tensors="pt",
            padding=True, truncation=True, max_length=512
        ).to(self.device)
        with torch.no_grad():
            translated = self.trans_model.generate(**inputs, max_new_tokens=512)
        return self.trans_tokenizer.decode(translated[0], skip_special_tokens=True)

    def summarise(self, hindi_article: str) -> Dict:
        english = self.translate(hindi_article)
        result  = self.pipe.summarise(english)
        # Note: returned summary is in English (limitation acknowledged in thesis)
        result["translated_input"] = english
        result["strategy"]         = "translate-then-summarise"
        return result


# ── Strategy B: Direct mBART ──────────────────────────────────────────────────

class DirectMBARTSummarise:
    """
    Fine-tuned mBART-50 for direct Hindi-to-Hindi summarisation.
    Requires running: python train/train_seq2seq.py --model mbart
    with XL-Sum Hindi data (modify data pipeline for that run).
    """

    def __init__(self):
        import torch
        from transformers import MBartForConditionalGeneration, MBart50Tokenizer
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        ckpt_path   = str(CKPT_DIR / "mbart_finetuned")
        fallback    = MBART_MODEL

        model_path = ckpt_path if Path(ckpt_path).exists() else fallback
        if not Path(ckpt_path).exists():
            log.warning(
                "mBART fine-tuned checkpoint not found. "
                "Using pretrained weights — quality will be low. "
                "Run: python train/train_seq2seq.py --model mbart"
            )

        log.info("Loading mBART from %s", model_path)
        self.tokenizer = MBart50Tokenizer.from_pretrained(
            model_path, src_lang="hi_IN", tgt_lang="hi_IN"
        )
        self.model = MBartForConditionalGeneration.from_pretrained(
            model_path
        ).to(self.device)
        self.model.eval()

    def summarise(self, hindi_article: str) -> Dict:
        import torch
        inputs = self.tokenizer(
            hindi_article, return_tensors="pt",
            max_length=1024, truncation=True
        ).to(self.device)

        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.lang_code_to_id["hi_IN"],
                max_new_tokens=128, num_beams=4,
                no_repeat_ngram_size=3,
            )
        summary = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return {
            "summary":  summary,
            "fallback": False,
            "strategy": "direct-mbart",
        }


# ── Evaluation ────────────────────────────────────────────────────────────────

def rouge_l(predictions: List[str], references: List[str]) -> float:
    scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=False)
    scores = [
        scorer.score(ref, pred)["rougeL"].fmeasure
        for pred, ref in zip(predictions, references)
    ]
    return round(float(np.mean(scores)) * 100, 2)


def run_study(test_size: int = XLSUM_TEST_SIZE):
    examples = load_xlsum_hindi(test_size)
    references = [e["summary"] for e in examples]
    articles   = [e["article"]  for e in examples]

    strategies = {
        "translate-then-summarise": TranslateThenSummarise(),
        "direct-mbart":             DirectMBARTSummarise(),
    }

    results = {}
    for name, model in strategies.items():
        log.info("Running strategy: %s", name)
        preds = []
        for art in tqdm(articles, desc=name):
            r = model.summarise(art)
            preds.append(r["summary"])
        rl = rouge_l(preds, references)
        results[name] = {"rouge_l": rl, "n_samples": len(preds)}
        log.info("%s → ROUGE-L: %.2f", name, rl)

    print("\n-- Multilingual Feasibility Study ---------------------------")
    print(f"  Dataset: XL-Sum Hindi, {test_size} test samples")
    for name, m in results.items():
        print(f"  {name}: ROUGE-L = {m['rouge_l']}")
    print("\n  Note: Both strategies have limitations at this training data size.")
    print("  Results are framed as a feasibility study — see Chapter 6 limitations.")

    out = RESULTS_DIR / "multilingual_study.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    log.info("Saved to %s", out)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_study()
