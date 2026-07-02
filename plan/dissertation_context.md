# Dissertation Codebase — Complete Context & Decision Log

**Project**: A Two-Stage Summarisation Pipeline for News Articles: Extraction-Guided Abstractive Generation
**Student**: Puthineedi Venkata Sai Charan | 2024AA05606
**Degree**: M.Tech AIML, BITS Pilani WILP
**Supervisor**: Veeraswamy Ponnuru, Lead QA Engineer, Opentext
**Course**: AIMLCZG628T: Dissertation

---

## 1. Project Overview

A four-stage grounded summarisation pipeline:

```
Article → [Stage 1] Evidence Retrieval → [Stage 2] Abstractive Generation
        → [Stage 3] NLI Verification  → [Stage 4] Preference Reranking → Summary
```

**Core innovation**: Hybrid BM25 + sentence-embedding retrieval feeds a fine-tuned BART model. Best-of-N nucleus sampling generates candidates. DeBERTa NLI verifier computes a Factual Consistency Score (FCS) per candidate. Weighted reranker (0.6×FCS + 0.4×BERTScore-F1) selects the best; extractive fallback fires when FCS < threshold.

**Dataset**: CNN/DailyMail 3.0.0 (`abisee/cnn_dailymail`)
**Primary generator**: `facebook/bart-large-cnn` (fine-tuned)
**Comparison baseline**: `google/pegasus-cnn_dailymail` (zero-shot only — already CNN/DM tuned)
**Multilingual study**: `facebook/mbart-large-cc25` (fine-tuned on CNN/DM, Hindi XL-Sum feasibility)
**NLI verifier**: `cross-encoder/nli-deberta-v3-base`
**Embeddings**: `sentence-transformers/all-MiniLM-L6-v2`

---

## 2. Repository Structure

```
dissertation/
├── config.py                        # Single source of truth — all hyperparams & paths
├── requirements.txt
├── data/
│   └── data_pipeline.py             # CNN/DM load, clean, cache, corpus_stats()
├── pipeline/
│   ├── pipeline.py                  # SummarizationPipeline — chains all 4 stages
│   ├── retrieval.py                 # Stage 1: EvidenceRetriever (hybrid BM25+embed)
│   ├── generator.py                 # Stage 2: Generator (BART/mBART, Best-of-N)
│   ├── verifier.py                  # Stage 3: EvidenceVerifier (NLI FCS)
│   └── reranker.py                  # Stage 4: PreferenceReranker + extractive fallback
├── baselines/
│   ├── lead3.py                     # Lead-3Summarizer
│   ├── textrank.py                  # TextRankSummarizer (also ablation arm)
│   ├── bart_baseline.py             # BartBaseline(mode="zeroshot"|"finetuned")
│   └── pegasus_baseline.py          # PegasusBaseline (zero-shot only, no fine-tuning)
├── train/
│   └── train_seq2seq.py             # Fine-tune BART or mBART via HF Seq2SeqTrainer
├── experiments/
│   ├── run_baselines.py             # Evaluate all baselines → baselines_table.csv
│   ├── run_pipeline.py              # Full comparison table + optional target check
│   └── run_ablations.py             # Ablations A (retrieval) B (N) C (verifier on/off)
├── evaluation/
│   ├── eval_metrics.py              # evaluate_system() — ROUGE, BERTScore, FCS, latency
│   └── check_targets.py             # Compare results vs dissertation EXPECTED_TARGETS
├── multilingual/
│   └── multilingual_study.py        # Hindi XL-Sum feasibility study
├── app/
│   └── app.py                       # Streamlit demo (4 stages, evidence trace, download)
├── analysis/
│   └── attention_viz.py             # Attention visualisation (optional)
└── googlecolab/
    ├── finetune_bart.ipynb          # Colab notebook — fine-tune BART
    ├── finetune_mbart.ipynb         # Colab notebook — fine-tune mBART
    └── pegasus_direct.ipynb         # Colab notebook — PEGASUS zero-shot eval
```

**Removed files** (were in original zip, deleted as unnecessary):
- `scratch_inspect.py` — dev scratch file
- `googlecolab/generate_notebooks.py` — stale notebook generator script
- `evaluation/human_eval.py` — unconnected stub

---

## 3. config.py — Canonical Values

```python
# Dataset
DATASET_NAME       = "abisee/cnn_dailymail"
DATASET_VERSION    = "3.0.0"
ARTICLE_COL        = "article"
SUMMARY_COL        = "highlights"
MAX_TRAIN_SAMPLES  = 15000      # optimised for Colab free T4 (~2.5hr)
MAX_EVAL_SAMPLES   = 2000       # cap validation during training evals
SEED               = 42

# Models
BART_MODEL    = "facebook/bart-large-cnn"
PEGASUS_MODEL = "google/pegasus-cnn_dailymail"   # zero-shot only
MBART_MODEL   = "facebook/mbart-large-cc25"
NLI_MODEL     = "cross-encoder/nli-deberta-v3-base"
EMBED_MODEL   = "sentence-transformers/all-MiniLM-L6-v2"

BART_CKPT     = CKPT_DIR / "bart_finetuned"
MBART_CKPT    = CKPT_DIR / "mbart_finetuned"

# Tokeniser limits
BART_MAX_INPUT     = 512     # was 1024; halved for Colab speed (fair vs PEGASUS)
BART_MAX_OUTPUT    = 128
PEGASUS_MAX_INPUT  = 512
PEGASUS_MAX_OUTPUT = 128

# Training (BART)
TRAIN_BATCH_SIZE   = 4       # was 2; doubled after max_in dropped to 512
GRAD_ACCUM_STEPS   = 4       # keeps effective batch = 16
LEARNING_RATE      = 3e-5
NUM_EPOCHS         = 2       # was 3; epoch 3 gives <0.5 ROUGE-2 gain on CNN/DM
WARMUP_STEPS       = 200
WEIGHT_DECAY       = 0.01
SAVE_STEPS         = 500
EVAL_STEPS         = 500
LOGGING_STEPS      = 50

# Retrieval
RETRIEVAL_K        = 8
BM25_WEIGHT        = 0.5
EMBED_WEIGHT       = 0.5
TOKEN_BUDGET       = BART_MAX_INPUT

# Generation
NUM_CANDIDATES     = 5
TOP_P              = 0.92
TEMPERATURE        = 1.0

# Verification
FCS_THRESHOLD      = 0.40

# Reranking
FCS_WEIGHT         = 0.60
BERTSCORE_WEIGHT   = 0.40
BERTSCORE_LANG     = "en"

# Dissertation objective targets
EXPECTED_TARGETS = {
    "pipeline_rouge2_min":        18.0,
    "pipeline_nli_fcs_min":       0.65,
    "baseline_nli_fcs_max":       0.55,
    "fallback_rate_max_pct":      15.0,
    "human_factual_accuracy_min": 4.0,
    "human_kappa_min":            0.6,
}

# Multilingual
XLSUM_LANG        = "hindi"
XLSUM_TRAIN_SIZE  = 2000
XLSUM_TEST_SIZE   = 200
TRANSLATE_MODEL   = "Helsinki-NLP/opus-mt-hi-en"
```

---

## 4. Fine-Tuning Decisions

### PEGASUS — NO fine-tuning (critical decision)

`google/pegasus-cnn_dailymail` is **already fine-tuned by Google on CNN/DailyMail**.
Fine-tuning it again would:
- Re-learn what it already knows → no gain
- Introduce instability from seeing the same data twice
- Waste ~2hr of Colab GPU
- Make the BART vs PEGASUS comparison **unfair** (both fine-tuned vs one pre-trained)

**Decision**: Use PEGASUS as a **zero-shot baseline** only via `PegasusBaseline` class.
This makes the comparison stronger: if our fine-tuned BART pipeline beats a model purpose-built for CNN/DM, that is a more compelling dissertation result.

Notebook: `googlecolab/pegasus_direct.ipynb` — zero-shot evaluation only, ~15 min on T4.

### BART — fine-tune on CNN/DailyMail

Primary generator. Fine-tuned from `facebook/bart-large-cnn`.

**Optimised Colab parameters (BART)**:
```python
train_batch_size = 4       # was 2
grad_accum_steps = 4       # effective batch stays 16
num_epochs       = 2       # was 3
learning_rate    = 3e-5
warmup_steps     = 200     # scaled to fewer total steps
eval_steps       = 500
save_steps       = 500
logging_steps    = 50
```
**Expected time**: ~2.8 hr on free T4

### mBART — fine-tune on CNN/DailyMail (multilingual study only)

Used for Hindi XL-Sum feasibility — not the primary pipeline generator.

**mBART-specific requirements**:
```python
tokenizer.src_lang = "en_XX"   # MUST set before any tokenisation
tokenizer.tgt_lang = "en_XX"
forced_bos_token_id = tokenizer.lang_code_to_id["en_XX"]   # in TrainingArguments
```

**Optimised Colab parameters (mBART)**:
```python
train_batch_size = 2       # was 1; safe with max_in=512
grad_accum_steps = 8       # effective batch = 16
num_epochs       = 2
learning_rate    = 3e-5
warmup_steps     = 150
eval_steps       = 500
```
**Expected time**: ~3.4 hr on free T4

### Why original config timed out on Colab

| Model   | Original estimate | Colab free limit |
|---------|------------------|-----------------|
| BART    | ~182 hr          | 12 hr           |
| PEGASUS | ~91 hr (wrong)   | 12 hr           |
| mBART   | ~355 hr          | 12 hr           |

Two killers: **50,000 samples × 3 epochs** + **eval on full 13,368 val set every 500 steps** (150 eval runs, ~63 min each).

**Fixes applied**:
- `MAX_TRAIN_SAMPLES`: 50,000 → 15,000
- `MAX_EVAL_SAMPLES`: 13,368 → 2,000 (cap validation split during training)
- `BART_MAX_INPUT`: 1024 → 512 (halves memory, doubles throughput; same as PEGASUS — now fair comparison)
- `NUM_EPOCHS`: 3 → 2 (epoch 3 gives <0.5 ROUGE-2 gain empirically)
- `TRAIN_BATCH_SIZE`: 2 → 4 for BART/PEGASUS (512 tokens fits 4 on T4)
- `WARMUP_STEPS`: 500 → 200 (scaled to fewer total steps)

### Configurable fine-tuning (use existing HF checkpoints)

`generator.py` `Generator` class has `use_finetuned: bool` parameter:
- `use_finetuned=True` → loads from `checkpoints/bart_finetuned/`
- `use_finetuned=False` → loads pretrained HF weights (zero-shot)
- If `use_finetuned=True` but checkpoint doesn't exist → **auto-fallback to pretrained** with warning

For the pipeline, you can also use any HF-published CNN/DM checkpoint by pointing `BART_CKPT` to the downloaded model path. No code changes needed.

**To use an existing HF fine-tuned BART** (e.g. from someone else's training run):
```python
# In config.py, change:
BART_CKPT = CKPT_DIR / "bart_finetuned"
# To point to any local path containing config.json + model.safetensors
BART_CKPT = Path("/path/to/your/downloaded/bart-cnn-checkpoint")
```

---

## 5. Critical Bugs Fixed (Across All Iterations)

### Bug 1 — `processing_class=tokenizer` (ALL notebooks, train_seq2seq.py)
`processing_class` is a transformers v5 rename. transformers 4.x uses `tokenizer=`.
**Fix**: Version-safe detection via `inspect.signature`:
```python
trainer_params = inspect.signature(Seq2SeqTrainer.__init__).parameters
if "processing_class" in trainer_params:
    trainer_kwargs["processing_class"] = tokenizer   # v5+
else:
    trainer_kwargs["tokenizer"] = tokenizer           # v4.x
```

### Bug 2 — `generation_min_length` not in `Seq2SeqTrainingArguments` (transformers <4.45)
This param was added in 4.45. Colab runs 4.40.
**Fix**: Set on the model's generation config instead:
```python
model.generation_config.min_length = 20
model.generation_config.max_length = cfg["max_out"]
```

### Bug 3 — mBART missing `src_lang`/`tgt_lang`
Without these, every encoded sequence is missing its language prefix token.
Training runs without error but produces corrupted input sequences.
**Fix**:
```python
tokenizer.src_lang = "en_XX"
tokenizer.tgt_lang = "en_XX"
# Also in preprocess fn when model_key == "mbart"
```

### Bug 4 — mBART missing `forced_bos_token_id`
Without this the decoder doesn't know what language to generate.
**Fix**: Add to `Seq2SeqTrainingArguments`:
```python
forced_bos_token_id = tokenizer.lang_code_to_id["en_XX"]
```
And in inference pipeline:
```python
forced_bos = tokenizer_eval.lang_code_to_id["en_XX"]
pipeline(..., forced_bos_token_id=forced_bos)
```

### Bug 5 — `gradient_checkpointing=True` without `use_reentrant=False`
Causes deprecation warning and potential failure on some PyTorch versions.
**Fix**:
```python
gradient_checkpointing        = True,
gradient_checkpointing_kwargs = {"use_reentrant": False},
```

### Bug 6 — PEGASUS `learning_rate=3e-5` in train() default signature
Even with Cell 9 corrected, the function default was still `3e-5`.
If called without explicit lr, would silently use wrong rate.
**Fix**: `learning_rate=1e-5` as default in the PEGASUS notebook's `train()` signature.
*(This is moot since PEGASUS is now zero-shot only.)*

### Bug 7 — mBART literal `\n` escape chars in config cell
Config cell source had `\\n# mBART override\\nMAX_TRAIN_SAMPLES = 50000\\n`
as a raw escaped string — printed instead of executed.
**Fix**: Rebuilt config cell cleanly.

### Bug 8 — Eval running on full 13,368 val samples every 500 steps
~63 min per eval × 150 evals = never finishes.
**Fix**: Cap val split to `MAX_EVAL_SAMPLES = 2000` in `get_datasets()`:
```python
val = val.shuffle(seed=SEED).select(range(MAX_EVAL_SAMPLES))
```

---

## 6. Bias Limitations (for dissertation Chapter 5 / Section 11)

These are **not bugs** — they are legitimate academic limitations to acknowledge:

| Bias | Description | Dissertation note |
|------|-------------|-------------------|
| CNN/DM dataset | Western, English, news-domain only; skews politics/crime/celebrity | State in Section 11.2 |
| BART extractive prior | Pre-trained to copy phrases; high ROUGE but not true abstraction | Note in Section 6 |
| PEGASUS lead-sentence bias | Gap-sentence pre-training biases toward first sentences | Note in Section 7 |
| mBART language imbalance | English dominates 25-language pre-training; Hindi underrepresented | Note in Section 11 |
| ROUGE optimisation | Early stopping on rouge2 rewards lexical overlap, not factual consistency | Note in Section 9 |
| Position bias | Truncation at 512 tokens never sees second half of long articles | Note in Section 5 |
| eval subset noise | 2,000-sample val gives ±0.5 ROUGE variance for early stopping | Acceptable trade-off |

**Key argument**: BART pipeline vs zero-shot PEGASUS is a strong comparison — if our fine-tuned system beats a model purpose-built for CNN/DM, that is a more compelling result.

---

## 7. Colab Notebooks — Cell Structure

Both `finetune_bart.ipynb` and `finetune_mbart.ipynb` follow identical structure:

| Cell | Purpose |
|------|---------|
| 0 | Markdown header + instructions |
| 1 | GPU assertion + VRAM check |
| 2 | pip install (mirrors requirements.txt) |
| 3 | Google Drive mount |
| 4 | NLTK punkt download |
| 5 | Config (inline copy of config.py) |
| 6 | Data pipeline (inline copy of data_pipeline.py) |
| 7 | Training function (inline copy of train_seq2seq.py) |
| 8 | Markdown: "Run Fine-tuning" |
| 9 | **The actual `train()` call — edit params here** |
| 10 | Post-training test evaluation (500 samples, saves ROUGE JSON) |
| 11 | Save checkpoint to Drive |
| 12 | Save training metrics to Drive |

`pegasus_direct.ipynb` — zero-shot evaluation only (no training cells).

---

## 8. How to Run Everything

### Step 1: Fine-tune BART (Colab)
Open `googlecolab/finetune_bart.ipynb` → Runtime → T4 GPU → Run all.
Download `bart_finetuned/` from Drive → place in `checkpoints/`.

### Step 2: Evaluate PEGASUS zero-shot (Colab, ~15 min)
Open `googlecolab/pegasus_direct.ipynb` → Run all.
Results saved to `results/test_rouge_pegasus_zeroshot.json`.

### Step 3 (optional): Fine-tune mBART for multilingual study
Open `googlecolab/finetune_mbart.ipynb` → Run all.
Download `mbart_finetuned/` from Drive → place in `checkpoints/`.

### Step 4: Run all baselines locally
```bash
python experiments/run_baselines.py --max_samples 500
```
Outputs: `results/baselines_table.csv`, `results/eval_*.json`

### Step 5: Run full pipeline comparison
```bash
python experiments/run_pipeline.py --max_samples 500 --check_targets
```
Outputs: `results/full_comparison_table.csv`

### Step 6: Run ablation studies
```bash
python experiments/run_ablations.py --ablation A --max_samples 300
python experiments/run_ablations.py --ablation B --max_samples 300
python experiments/run_ablations.py --ablation C --max_samples 300
```
Outputs: `results/ablation_A_retrieval.csv`, `ablation_B_n_candidates.csv`, `ablation_C_verifier.csv`

### Step 7: Launch demo app
```bash
streamlit run app/app.py
```

### Step 8: Multilingual feasibility study
```bash
python multilingual/multilingual_study.py
```

---

## 9. Comparison Table (Systems Evaluated)

| System | Fine-tuned? | File |
|--------|-------------|------|
| Lead-3 | ❌ | `baselines/lead3.py` |
| TextRank | ❌ | `baselines/textrank.py` |
| BART zero-shot | ❌ | `baselines/bart_baseline.py` (mode="zeroshot") |
| PEGASUS zero-shot | ❌ | `baselines/pegasus_baseline.py` |
| BART fine-tuned (single-stage) | ✅ | `baselines/bart_baseline.py` (mode="finetuned") |
| mBART fine-tuned | ✅ | `pipeline/generator.py` (model_key="mbart") |
| **Proposed pipeline** | ✅ (BART) | `pipeline/pipeline.py` |

**Ablation variants** (run_ablations.py):
- Retrieval: textrank vs bm25 vs embedding vs hybrid
- N candidates: 1, 2, 3, 5, 8
- Verifier: ON vs OFF

---

## 10. Dissertation Objective Targets

| Metric | Target | Measured on |
|--------|--------|-------------|
| Pipeline ROUGE-2 | ≥ 18.0 | CNN/DM test set |
| Pipeline NLI-FCS | ≥ 0.65 (scale 0–1) | 200-sample NLI eval |
| Single-stage BART FCS | ≤ 0.55 | Same |
| Extractive fallback rate | ≤ 15% | Full test set |
| Human factual accuracy | ≥ 4.0 / 5.0 (Likert) | 50 samples, 3 raters |
| Cohen's Kappa | ≥ 0.6 | Same |

Targets checked automatically via `evaluation/check_targets.py`, called from `run_pipeline.py --check_targets`.

---

## 11. Mid-Semester Report

**File**: `documentation/MidSem_Report_2024AA05606_final_colored.docx`

**Structure** (matches reference PDFs from Aditya and Preeti):
1. Introduction and Problem Context
2. Objectives and Research Questions
3. System Modules Completed up to Mid-Semester
4. System Architecture and Methodology
5. Tools and Technologies Used
6. Methodology and Pipeline Implementation
7. Experimental Setup and Baselines
8. Current Implementation Status
9. Technical Specifications of the Proposed System
10. Design Considerations
11. Preliminary Observations and Risks
12. Future Plan
13. Abbreviations
14. References

**Formatting**:
- Font: Times New Roman throughout
- H1: Black ALL CAPS bold
- H2/H3: Orange bold (`#C05000`) — matches `colored_document.pdf` reference
- Running header: *AIMLCZG628T - Mid-Semester Dissertation Report* (italic, top-right)
- Signature table, bordered TOC, all tables use thick borders
- Academic writing: no first-person, no conversational language, IEEE references

**Deviations from mid-sem report in code** (acceptable):
- `BART_MAX_INPUT` changed 1024 → 512 for Colab resource optimisation (noted in Section 10 Design Considerations)
- `MAX_TRAIN_SAMPLES` changed 50,000 → 15,000 (same justification)
- PEGASUS not fine-tuned (strengthens the argument)

---

## 12. Key File: train/train_seq2seq.py

Run locally:
```bash
python train/train_seq2seq.py --model bart
python train/train_seq2seq.py --model mbart
```

Key design points:
- Reads all hyperparams from `config.py` — no hardcoding
- mBART: sets `src_lang`/`tgt_lang` on tokenizer, passes `forced_bos_token_id` to trainer
- `min_length=20` set on `model.generation_config` (not TrainingArguments — not in 4.40 API)
- Version-safe tokenizer kwarg detection (works on 4.x and 5.x)
- Early stopping on `rouge2` with patience=3
- Saves checkpoint + tokenizer to `CKPT_DIR/<model>_finetuned/`
- Saves training metrics to `RESULTS_DIR/training_metrics_<model>.json`

---

## 13. Key File: pipeline/generator.py

```python
Generator(
    model_key     = "bart",           # "bart" | "mbart"
    use_finetuned = True,             # False = zero-shot
    n_candidates  = 5,               # Best-of-N
    top_p         = 0.92,            # nucleus sampling
    temperature   = 1.0,
)
```

- If `use_finetuned=True` but checkpoint missing → auto-fallback to pretrained with warning log
- `generate_candidates()` → returns list of N strings (nucleus sampling)
- `generate_beam()` → returns single string (beam search, used for baseline comparison)

---

## 14. requirements.txt (key packages)

```
torch>=2.1.0
transformers>=4.40.0
datasets>=2.18.0
accelerate>=1.1.0
sentencepiece>=0.1.99
sentence-transformers>=2.7.0
rank_bm25>=0.2.2
nltk>=3.8.1
networkx>=3.2.1
rouge-score>=0.1.2
bert-score>=0.3.13
evaluate>=0.4.1
streamlit>=1.33.0
pandas>=2.1.0
numpy>=1.26.0
scikit-learn>=1.4.0
scipy>=1.12.0
python-docx>=1.1.0
```

