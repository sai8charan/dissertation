import os
import json
from pathlib import Path

OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}

def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src.splitlines(keepends=True)}

def nb(cells, title):
    return {
        "nbformat": 4, "nbformat_minor": 0,
        "metadata": {
            "colab": {"name": title, "provenance": [], "gpuType": "T4"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"},
            "language_info": {"name": "python"},
            "accelerator": "GPU"
        },
        "cells": cells
    }

GPU_CHECK = code("""# ── Step 1: Verify GPU ──────────────────────────────────────────────────────
# If assertion fails: Runtime → Change runtime type → Hardware accelerator → T4 GPU
import torch
assert torch.cuda.is_available(), "No GPU! Go to Runtime > Change runtime type > T4 GPU then re-run."
print("GPU  :", torch.cuda.get_device_name(0))
print("VRAM :", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1), "GB")
print("PyTorch:", torch.__version__)
print("OK — GPU ready.")
""")

INSTALL = code("""# ── Step 2: Install packages (mirrors requirements.txt) ─────────────────────
import subprocess, sys
pkgs = [
    "transformers>=4.40.0", "datasets>=2.18.0", "accelerate>=1.1.0",
    "sentencepiece>=0.1.99", "sentence-transformers>=2.7.0", "rank_bm25>=0.2.2",
    "nltk>=3.8.1", "rouge-score>=0.1.2", "bert-score>=0.3.13", "evaluate>=0.4.1",
    "sacrebleu>=2.4.0", "matplotlib>=3.8.0", "pandas>=2.1.0", "numpy>=1.26.0",
    "tqdm>=4.66.0", "scikit-learn>=1.4.0", "scipy>=1.12.0",
]
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])
print("All packages installed.")
""")

DRIVE = code("""# ── Step 3: Mount Google Drive ───────────────────────────────────────────────
from google.colab import drive
import os
drive.mount('/content/drive')
DRIVE_CKPT_DIR = '/content/drive/MyDrive/dissertation_checkpoints'
os.makedirs(DRIVE_CKPT_DIR, exist_ok=True)
print("Drive mounted. Checkpoints will be saved to:", DRIVE_CKPT_DIR)
""")

NLTK_DL = code("""# ── Step 4: NLTK tokeniser data ─────────────────────────────────────────────
import nltk
nltk.download("punkt_tab", quiet=True)   # NLTK 3.8+
nltk.download("punkt",     quiet=True)   # fallback
print("NLTK data ready.")
""")

CONFIG_SRC = """# ── config.py — inline copy (same as dissertation/config.py) ──────────────────
# Hyperparameters are kept identical to the codebase for reproducibility.
import os
from pathlib import Path

ROOT        = Path("/content")
DATA_DIR    = ROOT / "data" / "cache"
CKPT_DIR    = ROOT / "checkpoints"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"
for d in [DATA_DIR, CKPT_DIR, RESULTS_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DATASET_NAME    = "cnn_dailymail"
DATASET_VERSION = "3.0.0"
ARTICLE_COL     = "article"
SUMMARY_COL     = "highlights"
SEED            = 42

# 50,000 training examples: ~17% of CNN/DM, achievable in one T4 session (~1.5h)
# Justified in dissertation Section 3.x: resource-constrained fine-tuning
MAX_TRAIN_SAMPLES = 12000

BART_MAX_INPUT     = 1024
BART_MAX_OUTPUT    = 128
PEGASUS_MAX_INPUT  = 512
PEGASUS_MAX_OUTPUT = 128

BART_MODEL    = "facebook/bart-large-cnn"
PEGASUS_MODEL = "google/pegasus-cnn_dailymail"  # used directly; no project checkpoint
MBART_MODEL   = "facebook/mbart-large-cc25"

BART_CKPT    = CKPT_DIR / "bart_finetuned"
MBART_CKPT   = CKPT_DIR / "mbart_finetuned"

ROUGE_TYPES   = ["rouge1", "rouge2", "rougeL"]
"""

DATA_SRC = """# ── data/data_pipeline.py — inline copy (same as dissertation codebase) ───────
import re, logging
import numpy as np
from datasets import load_dataset, DatasetDict
import nltk
from nltk.tokenize import sent_tokenize

log = logging.getLogger(__name__)

def clean_text(text):
    \"\"\"Remove CNN/DM boilerplate and normalise whitespace.\"\"\"
    text = re.sub(r"^\\s*\\(CNN\\)\\s*[-–—]?\\s*", "", text)
    text = re.sub(r"\\(By\\s+[^)]+\\)", "", text)
    text = re.sub(r"\\n{2,}", "\\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()

def preprocess_example(example):
    \"\"\"Clean article and summary; add sentence count.\"\"\"
    article = clean_text(example[ARTICLE_COL])
    summary = clean_text(example[SUMMARY_COL])
    summary = summary.replace("\\n", " ")
    sents   = sent_tokenize(article)
    return {
        ARTICLE_COL:     article,
        SUMMARY_COL:     summary,
        "article_sents": sents,
        "num_sents":     len(sents),
        "article_len":   len(article.split()),
        "summary_len":   len(summary.split()),
    }

def get_datasets(force_reprocess=False):
    \"\"\"Load, clean, and split CNN/DailyMail. Cached after first run.\"\"\"
    cache_path = DATA_DIR / "cnn_dm_processed"
    if cache_path.exists() and not force_reprocess:
        from datasets import load_from_disk
        return load_from_disk(str(cache_path))
    raw       = load_dataset(DATASET_NAME, DATASET_VERSION)
    processed = raw.map(preprocess_example, batched=False, desc="Preprocessing")
    train = processed["train"]
    val   = processed["validation"]
    test  = processed["test"]
    if MAX_TRAIN_SAMPLES is not None:
        train = train.shuffle(seed=SEED).select(range(MAX_TRAIN_SAMPLES))
    splits = DatasetDict({"train": train, "validation": val, "test": test})
    splits.save_to_disk(str(cache_path))
    return splits
"""

TRAIN_SRC = """# ── train/train_seq2seq.py — inline copy (same as dissertation codebase) ──────
import json, logging, os, inspect
import numpy as np
import torch
import evaluate as hf_evaluate
from transformers import (
    AutoTokenizer, AutoModelForSeq2SeqLM,
    Seq2SeqTrainer, Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq, EarlyStoppingCallback, set_seed,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

MODEL_REGISTRY = {
    "bart":    {"hf_name": BART_MODEL,    "max_in": BART_MAX_INPUT,    "max_out": BART_MAX_OUTPUT,    "ckpt": BART_CKPT},
    "mbart":   {"hf_name": MBART_MODEL,   "max_in": BART_MAX_INPUT,    "max_out": BART_MAX_OUTPUT,    "ckpt": MBART_CKPT},
}

def build_preprocess_fn(tokenizer, max_input, max_output):
    def preprocess(examples):
        model_inputs = tokenizer(examples[ARTICLE_COL], max_length=max_input, truncation=True, padding=False)
        labels       = tokenizer(text_target=examples[SUMMARY_COL], max_length=max_output, truncation=True, padding=False)
        model_inputs["labels"] = [
            [(tok if tok != tokenizer.pad_token_id else -100) for tok in lab]
            for lab in labels["input_ids"]
        ]
        return model_inputs
    return preprocess

def compute_metrics_fn(tokenizer):
    rouge = hf_evaluate.load("rouge")
    def compute_metrics(eval_preds):
        preds, labels = eval_preds
        if isinstance(preds, tuple): preds = preds[0]
        preds  = np.where(preds  != -100, preds,  tokenizer.pad_token_id)
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        dec_preds  = [p.strip() for p in tokenizer.batch_decode(preds,  skip_special_tokens=True)]
        dec_labels = [l.strip() for l in tokenizer.batch_decode(labels, skip_special_tokens=True)]
        result = rouge.compute(predictions=dec_preds, references=dec_labels, use_stemmer=True)
        return {k: round(v * 100, 2) for k, v in result.items()}
    return compute_metrics

def train(model_key, train_batch_size=2, grad_accum_steps=8,
          num_epochs=3, learning_rate=3e-5, warmup_steps=500,
          weight_decay=0.01, save_steps=500, eval_steps=500, logging_steps=100):
    \"\"\"Fine-tune a seq2seq model on CNN/DailyMail (parameters mirror config.py).\"\"\"
    set_seed(SEED)
    cfg       = MODEL_REGISTRY[model_key]
    tokenizer = AutoTokenizer.from_pretrained(cfg["hf_name"])
    
    if model_key == "mbart":
        tokenizer.src_lang = "en_XX"
        tokenizer.tgt_lang = "en_XX"
        eval_batch_size = 2
    else:
        eval_batch_size = train_batch_size * 2
        
    model     = AutoModelForSeq2SeqLM.from_pretrained(cfg["hf_name"])
    splits    = get_datasets()
    tokenised = splits.map(
        build_preprocess_fn(tokenizer, cfg["max_in"], cfg["max_out"]),
        batched=True, remove_columns=splits["train"].column_names,
        desc=f"Tokenising for {model_key}",
    )
    os.environ["TENSORBOARD_LOGGING_DIR"] = str(cfg["ckpt"] / "logs")
    fp16 = torch.cuda.is_available()
    
    extra_args = {}
    if model_key == "mbart":
        extra_args["forced_bos_token_id"] = tokenizer.lang_code_to_id["en_XX"]
        
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(cfg["ckpt"]), num_train_epochs=num_epochs,
        per_device_train_batch_size=train_batch_size,
        per_device_eval_batch_size=eval_batch_size,
        gradient_accumulation_steps=grad_accum_steps,
        warmup_steps=warmup_steps, weight_decay=weight_decay, learning_rate=learning_rate,
        fp16=fp16, eval_strategy="steps", eval_steps=eval_steps,
        save_strategy="steps", save_steps=save_steps, save_total_limit=2,
        load_best_model_at_end=True, metric_for_best_model="rouge2", greater_is_better=True,
        predict_with_generate=True, generation_max_length=cfg["max_out"],
        generation_min_length=20,
        gradient_checkpointing=True,
        logging_steps=logging_steps, report_to="none", seed=SEED,
        **extra_args
    )
    
    # Version-independent tokenizer/processing_class handling
    trainer_params = inspect.signature(Seq2SeqTrainer.__init__).parameters
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": tokenised["train"],
        "eval_dataset": tokenised["validation"],
        "data_collator": DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model, pad_to_multiple_of=8),
        "compute_metrics": compute_metrics_fn(tokenizer),
        "callbacks": [EarlyStoppingCallback(early_stopping_patience=3)],
    }
    if "processing_class" in trainer_params:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = Seq2SeqTrainer(**trainer_kwargs)
    result = trainer.train()
    trainer.save_model()
    tokenizer.save_pretrained(str(cfg["ckpt"]))
    out = RESULTS_DIR / f"training_metrics_{model_key}.json"
    with open(out, "w") as f: json.dump(result.metrics, f, indent=2)
    print("Model saved:", cfg["ckpt"])
    return result.metrics
"""

SAVE_DRIVE = code("""# ── Save fine-tuned model to Google Drive ────────────────────────────────────
# Run immediately after training -- sessions are ephemeral!
import shutil, os
ckpt_local = f"/content/checkpoints/{MODEL_KEY}_finetuned"
ckpt_drive = f"{DRIVE_CKPT_DIR}/{MODEL_KEY}_finetuned"
if os.path.exists(ckpt_local):
    shutil.copytree(ckpt_local, ckpt_drive, dirs_exist_ok=True)
    print("Checkpoint saved to Drive:", ckpt_drive)
    print("Files:", os.listdir(ckpt_drive)[:10])
else:
    print("Checkpoint not found -- did training finish?")
""")

SAVE_METRICS = code("""# ── Save training metrics to Drive ───────────────────────────────────────────
import shutil, json, os
src  = f"/content/results/training_metrics_{MODEL_KEY}.json"
dest = f"{DRIVE_CKPT_DIR}/training_metrics_{MODEL_KEY}.json"
if os.path.exists(src):
    shutil.copy(src, dest)
    with open(src) as f: print(json.dumps(json.load(f), indent=2))
    print("Metrics saved to Drive:", dest)
else:
    print("No metrics file found.")
""")

def make_nb(title_md, config_cell, model_key, batch, accum, lr, warmup, expected_time, eval_cell_src, next_steps):
    run_cell = code(f'MODEL_KEY = "{model_key}"\n'
                    'metrics = train(\n'
                    f'    model_key="{model_key}", train_batch_size={batch}, grad_accum_steps={accum},\n'
                    f'    num_epochs=3, learning_rate={lr}, warmup_steps={warmup},\n'
                    '    weight_decay=0.01, save_steps=500, eval_steps=500, logging_steps=100,\n'
                    ')\n'
                    f'print("{model_key.upper()} fine-tuning complete!", metrics)')
    return nb([
        md(title_md),
        GPU_CHECK, INSTALL, DRIVE, NLTK_DL,
        config_cell, code(DATA_SRC), code(TRAIN_SRC),
        md(f"## Run Fine-tuning\\n`batch={batch}` x `grad_accum={accum}` = effective batch 16 (matches config.py).  \\nExpected time on T4: **{expected_time}**."),
        run_cell,
        md("## Post-training test evaluation"),
        code(eval_cell_src),
        SAVE_DRIVE, SAVE_METRICS,
        md(next_steps),
    ], f"finetune_{model_key}.ipynb")

PEGASUS_DIRECT_EVAL = """# ── Direct PEGASUS evaluation on test split ─────────────────────────────────
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import evaluate as hf_evaluate, json

tokenizer_eval = AutoTokenizer.from_pretrained(PEGASUS_MODEL)
model_eval     = AutoModelForSeq2SeqLM.from_pretrained(PEGASUS_MODEL).cuda()
rouge          = hf_evaluate.load("rouge")
splits         = get_datasets()
test_articles  = splits["test"][ARTICLE_COL][:500]
test_summaries = splits["test"][SUMMARY_COL][:500]

summariser = pipeline("summarization", model=model_eval, tokenizer=tokenizer_eval,
                      device=0, max_length=128, min_length=20, truncation=True)
preds  = [r[0]["summary_text"] for r in summariser(test_articles, batch_size=4)]
scores = rouge.compute(predictions=preds, references=test_summaries, use_stemmer=True)
scores = {k: round(v * 100, 2) for k, v in scores.items()}
print("Test ROUGE:", scores)
out = RESULTS_DIR / "test_rouge_pegasus.json"
with open(out, "w") as f: json.dump(scores, f, indent=2)
print("Saved to", out)"""

def make_direct_nb(title_md, config_cell, eval_cell_src, next_steps):
    return nb([
        md(title_md),
        GPU_CHECK, INSTALL, NLTK_DL,
        config_cell, code(DATA_SRC),
        md("## Direct inference\\nPEGASUS is already trained on CNN/DailyMail, so no project fine-tuning step is required."),
        code(eval_cell_src),
        md(next_steps),
    ], "pegasus_direct.ipynb")

def main():
    bart_eval = """# ── Post-training: evaluate on test split ───────────────────────────────────
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import evaluate as hf_evaluate, json

tokenizer_eval = AutoTokenizer.from_pretrained(str(BART_CKPT))
model_eval     = AutoModelForSeq2SeqLM.from_pretrained(str(BART_CKPT)).cuda()
rouge          = hf_evaluate.load("rouge")
splits         = get_datasets()
test_articles  = splits["test"][ARTICLE_COL][:500]   # 500-sample fast eval
test_summaries = splits["test"][SUMMARY_COL][:500]

summariser = pipeline("summarization", model=model_eval, tokenizer=tokenizer_eval,
                      device=0, max_length=128, min_length=20, truncation=True)
preds  = [r[0]["summary_text"] for r in summariser(test_articles, batch_size=4)]
scores = rouge.compute(predictions=preds, references=test_summaries, use_stemmer=True)
scores = {k: round(v * 100, 2) for k, v in scores.items()}
print("Test ROUGE:", scores)
out = RESULTS_DIR / "test_rouge_bart.json"
with open(out, "w") as f: json.dump(scores, f, indent=2)
print("Saved to", out)"""

    bart_nb = make_nb(
        title_md=("# Fine-tuning BART-large-CNN on CNN/DailyMail\\n"
                  "## M.Tech Dissertation — A Two-Stage Summarisation Pipeline\\n\\n"
                  "**Model:** `facebook/bart-large-cnn`  \\n"
                  "**Dataset:** CNN/DailyMail 3.0.0  \\n"
                  "**Training samples:** 50,000 (17% of full set)  \\n"
                  "**GPU required:** T4 15 GB VRAM (free Colab tier)\\n\\n"
                  "> **Before running:** `Runtime -> Change runtime type -> T4 GPU`  \\n"
                  "> Checkpoint auto-saved to Google Drive after training."),
        config_cell=code(CONFIG_SRC), model_key="bart", batch=2, accum=8, lr="3e-5", warmup=500,
        expected_time="90-120 minutes", eval_cell_src=bart_eval,
        next_steps=("## Next steps\\n"
                    "1. Download `bart_finetuned/` from Google Drive\\n"
                    "2. Place in `dissertation/checkpoints/bart_finetuned/`\\n"
                    "3. Run `python experiments/run_pipeline.py`"),
    )

    pegasus_direct_nb = make_direct_nb(
        title_md=("# PEGASUS pretrained on CNN/DailyMail\\n"
                  "## M.Tech Dissertation — A Two-Stage Summarisation Pipeline\\n\\n"
                  "**Model:** `google/pegasus-cnn_dailymail`  \\n"
                  "**Dataset:** CNN/DailyMail 3.0.0  \\n"
                  "**Training samples:** none (already fine-tuned on CNN/DailyMail)  \\n"
                  "**GPU required:** T4 15 GB VRAM (for fast inference and evaluation)\\n\\n"
                  "> **Before running:** `Runtime -> Change runtime type -> T4 GPU`"),
        config_cell=code(CONFIG_SRC),
        eval_cell_src=PEGASUS_DIRECT_EVAL,
        next_steps=("## Next steps\\n"
                    "1. No checkpoint download is needed\\n"
                    "2. Run `python experiments/run_pipeline.py --max_samples 500` to compare it with BART and mBART"),
    )

    mbart_eval = """# ── Post-training: evaluate on test split ───────────────────────────────────
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
import evaluate as hf_evaluate, json

tokenizer_eval          = AutoTokenizer.from_pretrained(str(MBART_CKPT))
tokenizer_eval.src_lang = "en_XX"
model_eval              = AutoModelForSeq2SeqLM.from_pretrained(str(MBART_CKPT)).cuda()
rouge                   = hf_evaluate.load("rouge")
splits                  = get_datasets()
test_articles           = splits["test"][ARTICLE_COL][:500]
test_summaries          = splits["test"][SUMMARY_COL][:500]

forced_bos = tokenizer_eval.lang_code_to_id["en_XX"]
summariser = pipeline("summarization", model=model_eval, tokenizer=tokenizer_eval,
                      device=0, max_length=128, min_length=20, truncation=True,
                      forced_bos_token_id=forced_bos)
preds  = [r[0]["summary_text"] for r in summariser(test_articles, batch_size=2)]
scores = rouge.compute(predictions=preds, references=test_summaries, use_stemmer=True)
scores = {k: round(v * 100, 2) for k, v in scores.items()}
print("Test ROUGE:", scores)
out = RESULTS_DIR / "test_rouge_mbart.json"
with open(out, "w") as f: json.dump(scores, f, indent=2)
print("Saved to", out)"""

    mbart_config_src = CONFIG_SRC + "\\n# mBART override\\nMAX_TRAIN_SAMPLES = 12000\\n"
    mbart_nb = make_nb(
        title_md=("# Fine-tuning mBART-large-cc25 on CNN/DailyMail\\n"
                  "## M.Tech Dissertation — A Two-Stage Summarisation Pipeline\\n\\n"
                  "**Model:** `facebook/mbart-large-cc25`  \\n"
                  "**Dataset:** CNN/DailyMail 3.0.0  \\n"
                  "**Training samples:** 50,000  \\n"
                  "**GPU required:** T4 15 GB VRAM (free Colab tier)\\n\\n"
                  "> **Before running:** `Runtime -> Change runtime type -> T4 GPU`  \\n"
                  "> batch=1 + grad_accum=16 = effective batch 16 without OOM."),
        config_cell=code(mbart_config_src), model_key="mbart", batch=1, accum=16, lr="3e-5", warmup=300,
        expected_time="120-150 minutes", eval_cell_src=mbart_eval,
        next_steps=("## Next steps\\n"
                    "1. Download `mbart_finetuned/` from Google Drive\\n"
                    "2. Place in `dissertation/checkpoints/mbart_finetuned/`\\n"
                    "3. Run `python multilingual/multilingual_study.py`"),
    )

    notebooks = {
        "finetune_bart.ipynb": bart_nb,
        "pegasus_direct.ipynb": pegasus_direct_nb,
        "finetune_mbart.ipynb": mbart_nb,
    }

    for fname, notebook_obj in notebooks.items():
        out = OUT_DIR / fname
        with open(out, "w", encoding="utf-8") as f:
            json.dump(notebook_obj, f, indent=1, ensure_ascii=False)
        print(f"Written: {out}  ({out.stat().st_size // 1024} KB)")
    print("\\nDone. Upload the .ipynb files to Google Drive and open in Colab.")

if __name__ == "__main__":
    main()
