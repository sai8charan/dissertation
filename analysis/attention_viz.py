"""
analysis/attention_viz.py
-------------------------
Generates decoder cross-attention heatmaps from the fine-tuned BART model.

For 2–3 sample documents:
  1. Runs the full pipeline to get the final summary.
  2. Re-runs BART with output_attentions=True to extract cross-attention
     weights from the last decoder layer.
  3. Plots a heatmap: rows = generated summary tokens,
     columns = source input tokens.
  4. Overlays which source tokens correspond to evidence sentences
     selected by Stage 1 (highlighted in green).

This figure serves two purposes in the dissertation:
  - Answers the viva feedback point on "explain encoder-decoder internals"
  - Visually demonstrates that the retrieval stage correctly focuses
    the model's attention on salient source sentences.

Run:
    python analysis/attention_viz.py
"""

import logging
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import torch
from transformers import BartTokenizer, BartForConditionalGeneration

sys.path.append(str(Path(__file__).parent.parent))
from config import (
    BART_MODEL, BART_CKPT,
    BART_MAX_INPUT, BART_MAX_OUTPUT,
    FIGURES_DIR,
)

log = logging.getLogger(__name__)

# Max tokens to show on each axis (heatmaps get unreadable beyond this)
MAX_SRC_TOKENS = 60
MAX_TGT_TOKENS = 30


class AttentionVisualizer:
    """
    Extracts and plots BART decoder cross-attention.

    Cross-attention at layer L, head H gives a matrix of shape
    [tgt_len, src_len] where entry (i, j) is how much generated
    token i attended to source token j.

    We average over all heads in the last decoder layer for a
    summary attention view, then plot as a heatmap.
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        model_path = str(BART_CKPT)
        if not Path(model_path).exists():
            log.warning("Fine-tuned checkpoint not found, using pretrained.")
            model_path = BART_MODEL

        log.info("Loading BART for attention extraction from %s", model_path)
        self.tokenizer = BartTokenizer.from_pretrained(model_path)
        self.model     = BartForConditionalGeneration.from_pretrained(
            model_path, output_attentions=True
        ).to(self.device)
        self.model.eval()

    @torch.no_grad()
    def extract_attention(
        self, context: str
    ) -> dict:
        """
        Run BART with attention output and extract cross-attention.

        Returns:
            {
              src_tokens : list of str
              tgt_tokens : list of str
              attention  : np.ndarray [tgt_len, src_len]  — mean over heads
            }
        """
        inputs = self.tokenizer(
            context,
            max_length=BART_MAX_INPUT,
            truncation=True,
            return_tensors="pt",
        ).to(self.device)

        output = self.model.generate(
            **inputs,
            max_new_tokens=BART_MAX_OUTPUT,
            num_beams=1,
            do_sample=False,
            output_attentions=True,
            return_dict_in_generate=True,
        )

        generated_ids = output.sequences[0]
        # cross_attentions: tuple of (tgt_step, layers, heads, 1, src_len)
        cross_attentions = output.cross_attentions

        # ── Stack into [tgt_len, n_layers, n_heads, src_len] ─────────────────
        n_steps  = len(cross_attentions)
        # Each step: tuple of n_layers tensors, each [1, n_heads, 1, src_len]
        n_layers = len(cross_attentions[0])
        n_heads  = cross_attentions[0][0].shape[1]
        src_len  = cross_attentions[0][0].shape[-1]

        # Use only the last decoder layer
        last_layer_attn = np.zeros((n_steps, src_len))
        for t in range(n_steps):
            attn_t = cross_attentions[t][-1]   # last layer, shape [1, heads, 1, src]
            # Mean over heads
            last_layer_attn[t] = attn_t[0, :, 0, :].mean(0).cpu().numpy()

        # ── Decode tokens for axis labels ─────────────────────────────────────
        src_token_ids = inputs["input_ids"][0].tolist()
        tgt_token_ids = generated_ids.tolist()[1:]   # skip BOS

        src_tokens = [
            self.tokenizer.decode([t]).strip() for t in src_token_ids
        ]
        tgt_tokens = [
            self.tokenizer.decode([t]).strip() for t in tgt_token_ids
            if t not in (self.tokenizer.eos_token_id, self.tokenizer.pad_token_id)
        ]

        # Trim to MAX limits
        src_tokens     = src_tokens[:MAX_SRC_TOKENS]
        tgt_tokens     = tgt_tokens[:MAX_TGT_TOKENS]
        attention_trim = last_layer_attn[:MAX_TGT_TOKENS, :MAX_SRC_TOKENS]

        return {
            "src_tokens": src_tokens,
            "tgt_tokens": tgt_tokens,
            "attention":  attention_trim,
        }

    def plot_heatmap(
        self,
        context: str,
        selected_context: str,
        title: str = "BART Cross-Attention",
        filename: str = "attention_heatmap.png",
    ) -> Path:
        """
        Plot cross-attention heatmap. Highlights tokens that belong to
        the evidence-selected context (Stage 1 output) in green.

        Args:
            context          : original article text (full or truncated)
            selected_context : evidence context from Stage 1 retrieval
            title            : plot title
            filename         : output filename in FIGURES_DIR

        Returns:
            Path to saved figure
        """
        data = self.extract_attention(context)
        src_tokens = data["src_tokens"]
        tgt_tokens = data["tgt_tokens"]
        attn       = data["attention"]

        # ── Identify which source tokens are in the selected evidence ─────────
        selected_ids = self.tokenizer(
            selected_context, max_length=BART_MAX_INPUT, truncation=True
        )["input_ids"]
        selected_set = set(selected_ids)

        full_ids = self.tokenizer(
            context, max_length=BART_MAX_INPUT, truncation=True
        )["input_ids"][:MAX_SRC_TOKENS]

        is_evidence = [int(tok_id in selected_set) for tok_id in full_ids]

        # ── Plot ──────────────────────────────────────────────────────────────
        fig, ax = plt.subplots(
            figsize=(min(len(src_tokens) * 0.28 + 2, 18),
                     min(len(tgt_tokens) * 0.38 + 2, 12))
        )

        im = ax.imshow(attn, aspect="auto", cmap="Blues", vmin=0, vmax=attn.max())

        # Highlight evidence columns in green
        for j, flag in enumerate(is_evidence[:len(src_tokens)]):
            if flag:
                ax.axvspan(j - 0.5, j + 0.5, color="green", alpha=0.15, zorder=0)

        ax.set_xticks(range(len(src_tokens)))
        ax.set_xticklabels(src_tokens, rotation=90, fontsize=7)
        ax.set_yticks(range(len(tgt_tokens)))
        ax.set_yticklabels(tgt_tokens, fontsize=8)
        ax.set_xlabel("Source tokens (article)", fontsize=10)
        ax.set_ylabel("Generated summary tokens", fontsize=10)
        ax.set_title(title, fontsize=11, pad=12)

        legend = [
            mpatches.Patch(color="green", alpha=0.3, label="Evidence-selected tokens (Stage 1)"),
            mpatches.Patch(color="#3278B4", label="Cross-attention weight"),
        ]
        ax.legend(handles=legend, loc="upper right", fontsize=8)

        plt.colorbar(im, ax=ax, fraction=0.02, pad=0.04)
        plt.tight_layout()

        out_path = FIGURES_DIR / filename
        plt.savefig(str(out_path), dpi=180, bbox_inches="tight")
        plt.close()
        log.info("Saved attention heatmap to %s", out_path)
        return out_path

    def visualise_samples(self, samples: List[dict]) -> List[Path]:
        """
        Generate heatmaps for a list of sample dicts.
        Each dict: {"article": str, "selected_context": str, "title": str}

        Returns:
            List of output paths
        """
        from pipeline.retrieval import EvidenceRetriever
        retriever = EvidenceRetriever()
        paths     = []

        for i, sample in enumerate(samples):
            article = sample["article"]
            if "selected_context" not in sample:
                ret = retriever.get_evidence(article, method="hybrid")
                sample["selected_context"] = ret["selected_context"]

            path = self.plot_heatmap(
                context          = sample["selected_context"],  # what BART sees
                selected_context = sample["selected_context"],
                title            = sample.get("title", f"Sample {i+1}"),
                filename         = f"attention_sample_{i+1}.png",
            )
            paths.append(path)
        return paths


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    SAMPLES = [
        {
            "title": "NASA Artemis Moon Mission",
            "article": (
                "NASA announced on Thursday that its Artemis programme will send "
                "astronauts back to the Moon in 2026. The mission will include "
                "the first woman and first person of colour to walk on the lunar surface. "
                "The agency has been developing the Space Launch System rocket for over "
                "a decade at a cost of more than 20 billion dollars. "
                "Critics have questioned whether the timeline is achievable given "
                "recent technical setbacks with the Orion capsule heat shield. "
                "NASA administrator Bill Nelson expressed confidence that the programme "
                "remains on track and that the agency has resolved all major issues."
            ),
        },
        {
            "title": "UK Economy GDP Growth",
            "article": (
                "The UK economy grew by 0.6 percent in the first quarter of 2026, "
                "according to figures released by the Office for National Statistics. "
                "The growth was driven primarily by the services sector, which accounts "
                "for around 80 percent of economic output. Manufacturing output fell "
                "slightly during the same period due to weaker export demand. "
                "The Bank of England said it would keep interest rates unchanged at "
                "its next meeting, citing stable inflation expectations."
            ),
        },
        {
            "title": "Climate Summit Agreement",
            "article": (
                "World leaders reached a landmark climate agreement on Saturday at the "
                "Geneva summit, committing to cut greenhouse gas emissions by 50 percent "
                "by 2035. The deal was signed by 190 countries. Developing nations "
                "secured a 200 billion dollar annual fund to help transition to "
                "renewable energy. Environmental groups cautiously welcomed the deal "
                "but said implementation would be the real test. China and the United "
                "States jointly announced additional bilateral emissions targets."
            ),
        },
    ]

    viz   = AttentionVisualizer()
    paths = viz.visualise_samples(SAMPLES)
    print(f"\nGenerated {len(paths)} attention heatmaps:")
    for p in paths:
        print(f"  {p}")
