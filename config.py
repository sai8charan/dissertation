"""
config.py
---------
Single source of truth for all hyperparameters and paths.
Every other module imports from here — never hardcode values elsewhere.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
DATA_DIR    = ROOT / "data" / "cache"
CKPT_DIR    = ROOT / "checkpoints"
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "figures"

for d in [DATA_DIR, CKPT_DIR, RESULTS_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Dataset ───────────────────────────────────────────────────────────────────
DATASET_NAME    = "abisee/cnn_dailymail"
DATASET_VERSION = "3.0.0"
ARTICLE_COL     = "article"
SUMMARY_COL     = "highlights"
TRAIN_SPLIT     = 0.70
VAL_SPLIT       = 0.15
TEST_SPLIT      = 0.15
MAX_TRAIN_SAMPLES = 50_000   # Set to 50,000 for standard training size (matches Colab setup)

# ── Models ────────────────────────────────────────────────────────────────────
BART_MODEL      = "facebook/bart-large-cnn"   # pre-trained starting point
PEGASUS_MODEL   = "google/pegasus-cnn_dailymail"  # used directly; no project checkpoint
MBART_MODEL     = "facebook/mbart-large-cc25"
NLI_MODEL       = "cross-encoder/nli-deberta-v3-base"
EMBED_MODEL     = "sentence-transformers/all-MiniLM-L6-v2"

BART_CKPT       = CKPT_DIR / "bart_finetuned"   # saved after training
MBART_CKPT      = CKPT_DIR / "mbart_finetuned"

# ── Tokeniser limits ──────────────────────────────────────────────────────────
BART_MAX_INPUT  = 1024   # hard token limit for BART encoder
BART_MAX_OUTPUT = 128
PEGASUS_MAX_INPUT  = 512
PEGASUS_MAX_OUTPUT = 128

# ── Training ──────────────────────────────────────────────────────────────────
TRAIN_BATCH_SIZE   = 2
GRAD_ACCUM_STEPS   = 8      # effective batch = 16
LEARNING_RATE      = 3e-5
NUM_EPOCHS         = 3
WARMUP_STEPS       = 500
WEIGHT_DECAY       = 0.01
FP16               = True    # set False if no GPU / no apex
SAVE_STEPS         = 1000
EVAL_STEPS         = 1000
LOGGING_STEPS      = 100

# ── Evidence retrieval ────────────────────────────────────────────────────────
RETRIEVAL_K        = 8       # max sentences to select (within token budget)
BM25_WEIGHT        = 0.5     # weight in hybrid score
EMBED_WEIGHT       = 0.5
TOKEN_BUDGET       = BART_MAX_INPUT   # retrieval respects this

# ── Generation (Best-of-N) ────────────────────────────────────────────────────
NUM_CANDIDATES     = 5       # N in Best-of-N
TOP_P              = 0.92    # nucleus sampling
TEMPERATURE        = 1.0
NUM_BEAMS          = 1       # 1 = sampling; >1 = beam (switch for ablation)

# ── Verification ─────────────────────────────────────────────────────────────
NLI_BATCH_SIZE     = 32
ENTAILMENT_LABEL   = "entailment"   # DeBERTa label string
FCS_THRESHOLD      = 0.40   # below this → extractive fallback

# ── Reranking ─────────────────────────────────────────────────────────────────
FCS_WEIGHT         = 0.60
BERTSCORE_WEIGHT   = 0.40
BERTSCORE_LANG     = "en"

# ── Evaluation ────────────────────────────────────────────────────────────────
# Metric scale conventions:
#   ROUGE / BERTScore / fallback_rate / hallucination_rate → 0–100 (percent)
#   nli_fcs → 0–1 (matches verifier.py and dissertation objective targets)
ROUGE_TYPES        = ["rouge1", "rouge2", "rougeL"]
NUM_HUMAN_EVAL     = 50      # samples for human evaluation
HUMAN_EVAL_FILE    = RESULTS_DIR / "human_eval_samples.csv"

# Dissertation objective targets (replace with achieved values in Chapter 5)
EXPECTED_TARGETS = {
    "pipeline_rouge2_min":        18.0,   # ROUGE-2 F1 × 100
    "pipeline_nli_fcs_min":       0.65,   # proposed pipeline, scale 0–1
    "baseline_nli_fcs_max":       0.55,   # single-stage BART fine-tuned
    "fallback_rate_max_pct":      15.0,
    "human_factual_accuracy_min": 4.0,    # Likert 1–5
    "human_kappa_min":            0.6,
}

# ── Multilingual study ────────────────────────────────────────────────────────
XLSUM_LANG         = "hindi"
XLSUM_TRAIN_SIZE   = 2000
XLSUM_TEST_SIZE    = 200
TRANSLATE_MODEL    = "Helsinki-NLP/opus-mt-hi-en"   # Hindi → English
MULTILINGUAL_NLI   = "joeddav/xlm-roberta-large-xnli"

# ── Reproducibility ───────────────────────────────────────────────────────────
SEED = 42
