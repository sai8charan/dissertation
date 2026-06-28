"""
train/train_seq2seq.py
----------------------
Fine-tunes a seq2seq model (BART or mBART) on CNN/DailyMail
using HuggingFace Seq2SeqTrainer.

Usage:
    python train/train_seq2seq.py --model bart
    python train/train_seq2seq.py --model mbart

Output:
    Saves checkpoint to checkpoints/<model>_finetuned/
    Saves training metrics to results/training_metrics_<model>.json
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
import torch
import evaluate
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    set_seed,
)

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    ARTICLE_COL,
    BART_CKPT,
    BART_MAX_INPUT,
    BART_MAX_OUTPUT,
    BART_MODEL,
    EVAL_STEPS,
    FP16,
    GRAD_ACCUM_STEPS,
    LEARNING_RATE,
    LOGGING_STEPS,
    MBART_CKPT,
    MBART_MODEL,
    NUM_EPOCHS,
    RESULTS_DIR,
    SAVE_STEPS,
    SEED,
    SUMMARY_COL,
    TRAIN_BATCH_SIZE,
    WARMUP_STEPS,
    WEIGHT_DECAY,
)
from data.data_pipeline import get_datasets

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Model registry ────────────────────────────────────────────────────────────
MODEL_REGISTRY = {
    "bart": {
        "hf_name": BART_MODEL,
        "max_in": BART_MAX_INPUT,
        "max_out": BART_MAX_OUTPUT,
        "ckpt": BART_CKPT,
    },
    "mbart": {
        "hf_name": MBART_MODEL,
        "max_in": BART_MAX_INPUT,
        "max_out": BART_MAX_OUTPUT,
        "ckpt": MBART_CKPT,
    },
}


def build_preprocess_fn(tokenizer, max_input: int, max_output: int):
    """Returns a tokenisation function for Seq2SeqTrainer."""
    def preprocess(examples):
        model_inputs = tokenizer(
            examples[ARTICLE_COL],
            max_length=max_input,
            truncation=True,
            padding=False,
        )
        labels = tokenizer(
            text_target=examples[SUMMARY_COL],
            max_length=max_output,
            truncation=True,
            padding=False,
        )
        # Replace padding token id in labels with -100 (ignored by loss)
        labels_ids = [
            [(l if l != tokenizer.pad_token_id else -100) for l in lab]
            for lab in labels["input_ids"]
        ]
        model_inputs["labels"] = labels_ids
        return model_inputs
    return preprocess


def compute_metrics_fn(tokenizer):
    """Returns a metrics function using ROUGE."""
    rouge = evaluate.load("rouge")

    def compute_metrics(eval_preds):
        preds, labels = eval_preds
        if isinstance(preds, tuple):
            preds = preds[0]
        preds = np.where(preds != -100, preds, tokenizer.pad_token_id)
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_preds  = tokenizer.batch_decode(preds,  skip_special_tokens=True)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
        decoded_preds  = [p.strip() for p in decoded_preds]
        decoded_labels = [l.strip() for l in decoded_labels]
        result = rouge.compute(
            predictions=decoded_preds,
            references=decoded_labels,
            use_stemmer=True,
        )
        return {k: round(v * 100, 2) for k, v in result.items()}

    return compute_metrics


def train(model_key: str):
    set_seed(SEED)
    cfg = MODEL_REGISTRY[model_key]
    log.info("Fine-tuning: %s", cfg["hf_name"])

    # ── Load tokeniser and model ──────────────────────────────────────────────
    tokenizer = AutoTokenizer.from_pretrained(cfg["hf_name"])
    model     = AutoModelForSeq2SeqLM.from_pretrained(cfg["hf_name"])

    # ── Load and tokenise dataset ─────────────────────────────────────────────
    splits     = get_datasets()
    preprocess = build_preprocess_fn(tokenizer, cfg["max_in"], cfg["max_out"])

    tokenised = splits.map(
        preprocess,
        batched=True,
        remove_columns=splits["train"].column_names,
        desc=f"Tokenising for {model_key}",
    )

    # Set tensorboard log dir (replaces deprecated logging_dir in transformers v5.2+)
    os.environ["TENSORBOARD_LOGGING_DIR"] = str(cfg["ckpt"] / "logs")

    # ── Training arguments ────────────────────────────────────────────────────
    training_args = Seq2SeqTrainingArguments(
        output_dir                  = str(cfg["ckpt"]),
        num_train_epochs            = NUM_EPOCHS,
        per_device_train_batch_size = TRAIN_BATCH_SIZE,
        per_device_eval_batch_size  = TRAIN_BATCH_SIZE * 2,
        gradient_accumulation_steps = GRAD_ACCUM_STEPS,
        warmup_steps                = WARMUP_STEPS,
        weight_decay                = WEIGHT_DECAY,
        learning_rate               = LEARNING_RATE,
        fp16                        = FP16 and torch.cuda.is_available(),
        eval_strategy               = "steps",
        eval_steps                  = EVAL_STEPS,
        save_strategy               = "steps",
        save_steps                  = SAVE_STEPS,
        save_total_limit            = 2,
        load_best_model_at_end      = True,
        metric_for_best_model       = "rouge2",
        greater_is_better           = True,
        predict_with_generate       = True,
        generation_max_length       = cfg["max_out"],
        logging_steps               = LOGGING_STEPS,
        # logging_dir replaced by TENSORBOARD_LOGGING_DIR env var in transformers v5.2+
        report_to                   = "none",
        seed                        = SEED,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer, model=model, pad_to_multiple_of=8
    )

    trainer = Seq2SeqTrainer(
        model             = model,
        args              = training_args,
        train_dataset     = tokenised["train"],
        eval_dataset      = tokenised["validation"],
        processing_class  = tokenizer,   # renamed from 'tokenizer' in transformers v5
        data_collator     = data_collator,
        compute_metrics   = compute_metrics_fn(tokenizer),
        callbacks         = [EarlyStoppingCallback(early_stopping_patience=3)],
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    log.info("Starting training …")
    train_result = trainer.train()

    # ── Save ─────────────────────────────────────────────────────────────────
    trainer.save_model()
    tokenizer.save_pretrained(str(cfg["ckpt"]))
    log.info("Model saved to %s", cfg["ckpt"])

    metrics = train_result.metrics
    metrics_path = RESULTS_DIR / f"training_metrics_{model_key}.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    log.info("Training metrics saved to %s", metrics_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", choices=list(MODEL_REGISTRY.keys()), default="bart",
        help="Which model to fine-tune (bart or mbart; default: bart)",
    )
    args = parser.parse_args()
    train(args.model)
