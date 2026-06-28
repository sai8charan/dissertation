# A Two-Stage Summarisation Pipeline for News Articles

**Dissertation — M.Tech AIML, BITS Pilani WILP (2024AA05606)**

> Extraction-Guided Abstractive Generation with Evidence Retrieval,
> NLI-based Factual Verification, and Preference Reranking.

---

## Repository structure

```
dissertation/
├── config.py                        # All hyperparameters — edit this first
├── requirements.txt
│
├── data/
│   └── data_pipeline.py             # CNN/DailyMail loading + corpus stats
│
├── baselines/
│   ├── lead3.py                     # Lead-3 baseline
│   ├── textrank.py                  # TextRank extractive baseline
│   ├── bart_baseline.py             # Zero-shot and fine-tuned BART baselines
│   └── pegasus_baseline.py          # Direct pretrained PEGASUS baseline
│
├── train/
│   └── train_seq2seq.py             # Fine-tune BART / mBART only
│
├── pipeline/
│   ├── retrieval.py                 # Stage 1: hybrid BM25 + embedding retrieval
│   ├── generator.py                 # Stage 2: Best-of-N nucleus sampling
│   ├── verifier.py                  # Stage 3: NLI factual consistency scoring
│   ├── reranker.py                  # Stage 4: preference reranking + fallback
│   └── pipeline.py                  # Full pipeline wrapper
│
├── evaluation/
│   ├── eval_metrics.py              # ROUGE, BERTScore, FCS, fallback rate
│   └── human_eval.py               # Generate + score human evaluation CSV
│
├── experiments/
│   ├── run_baselines.py             # Evaluate all four baselines
│   ├── run_pipeline.py              # Pipeline + direct PEGASUS/mBART comparison
│   └── run_ablations.py             # Ablation studies A / B / C
│
├── multilingual/
│   └── multilingual_study.py        # Hindi XL-Sum feasibility study
│
├── analysis/
│   └── attention_viz.py             # Decoder cross-attention heatmaps
│
└── app/
    └── app.py                       # Streamlit demo application
```

---

## Setup

```bash
# 1. Clone / download this repository
cd dissertation

# 2. Create a virtual environment (Python 3.10+)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Download NLTK data
python -c "import nltk; nltk.download('punkt')"
```

**GPU note**: Fine-tuning BART-large and mBART requires a GPU with ≥16GB VRAM
(A100 on Google Colab Pro+ / Kaggle). PEGASUS is already trained on
CNN/DailyMail and is loaded directly, so it does not need a training run.
Inference runs on CPU but is slow — use a T4 or better for evaluation.

---

## Execution order (follow the dissertation timeline)

### Step 1 — Verify data pipeline

```bash
python data/data_pipeline.py
```
Downloads CNN/DailyMail 3.0.0, cleans it, and prints corpus statistics
(article length, summary length, compression ratio). Output cached to
`data/cache/` so subsequent runs are instant.

### Step 2 — Evaluate baselines (no training needed for Lead-3 and TextRank)

```bash
python experiments/run_baselines.py --max_samples 200 --no_fcs
```
`--no_fcs` skips the slow NLI-FCS computation during early development.
Results saved to `results/baselines_table.csv`.

### Step 3 — Fine-tune BART

```bash
python train/train_seq2seq.py --model bart
```
Takes ~6–8 hours on an A100. Checkpoint saved to `checkpoints/bart_finetuned/`.
For fast iteration, set `MAX_TRAIN_SAMPLES = 5000` in `config.py` first.

### Step 4 — Direct PEGASUS comparison and mBART

```bash
python train/train_seq2seq.py --model mbart
```
PEGASUS is loaded directly from `google/pegasus-cnn_dailymail`, so no
additional fine-tuning step is needed for that comparison row.

### Step 5 — Full pipeline evaluation

```bash
python experiments/run_pipeline.py --max_samples 500
python evaluation/check_targets.py
```
Compares proposed pipeline vs all baselines + direct PEGASUS + mBART.
Results saved to `results/full_comparison_table.csv`.
Use `--check_targets` on `run_pipeline.py` to evaluate and check objectives in one step.

### Step 6 — Ablation studies

```bash
python experiments/run_ablations.py --ablation all --max_samples 300
```
Runs ablations A (retrieval method), B (Best-of-N), C (verifier on/off).

### Step 7 — Human evaluation

```bash
# Generate blind evaluation CSV
python evaluation/human_eval.py --generate

# After evaluators complete ratings, compute agreement:
python evaluation/human_eval.py --compute --file results/human_eval_completed.csv
```

### Step 8 — Multilingual feasibility study

```bash
python multilingual/multilingual_study.py
```

### Step 9 — Attention visualisation

```bash
python analysis/attention_viz.py
```
Saves heatmap PNGs to `figures/`.

### Step 10 — Demo application

```bash
streamlit run app/app.py
```
Opens at http://localhost:8501

---

## Key config options (`config.py`)

| Parameter | Default | What it controls |
|---|---|---|
| `MAX_TRAIN_SAMPLES` | `None` | Set to `5000` for fast iteration |
| `NUM_CANDIDATES` | `5` | Best-of-N candidates generated per article |
| `RETRIEVAL_K` | `8` | Max sentences selected by retriever |
| `FCS_THRESHOLD` | `0.40` | Below this → extractive fallback |
| `FCS_WEIGHT` | `0.60` | Reranker weight for factual consistency |
| `BERTSCORE_WEIGHT` | `0.40` | Reranker weight for fluency |

---

## Results (fill in after running experiments)

Target thresholds are defined in `config.py` (`EXPECTED_TARGETS`). After evaluation, run
`python evaluation/check_targets.py` to compare achieved metrics against dissertation objectives.

| System | ROUGE-1 | ROUGE-2 | ROUGE-L | BERTScore | FCS (0–1) | Fallback% | vs Target |
|---|---|---|---|---|---|---|---|
| Lead-3 | TBD | TBD | TBD | TBD | TBD | — | — |
| TextRank | TBD | TBD | TBD | TBD | TBD | — | — |
| BART zero-shot | TBD | TBD | TBD | TBD | TBD | — | — |
| BART fine-tuned | TBD | TBD | TBD | TBD | TBD | — | baseline FCS ≤ 0.55 |
| PEGASUS pretrained | TBD | TBD | TBD | TBD | TBD | — | — |
| mBART fine-tuned | TBD | TBD | TBD | TBD | TBD | — | — |
| **Proposed pipeline** | **TBD** | **TBD (target ≥ 18.0)** | **TBD** | **TBD** | **TBD (target ≥ 0.65)** | **TBD (target < 15%)** | `check_targets.py` |

Human evaluation targets: factual accuracy ≥ 4.0/5.0, Cohen's κ ≥ 0.6 (checked via `human_eval.py --compute`).

---

## References

1. Lewis et al. (2020). BART. ACL 2020.
2. Zhang et al. (2020). PEGASUS. ICML 2020.
3. Mihalcea & Tarau (2004). TextRank. EMNLP 2004.
4. Laban et al. (2022). SummaC. TACL 2022.
5. Liu et al. (2026). Summarization is Not Dead Yet. arXiv:2606.08000.
6. Mujahid, Wright & Augenstein (2026). Stress Testing Factual Consistency. ACL 2026.
