"""
app/app.py
----------
Streamlit demo application for the dissertation final viva.

Features:
  - Paste or upload a news article
  - Run the full 4-stage pipeline
  - Display: final summary, FCS score, fallback status
  - Evidence trace: highlight which source sentences support each
    generated sentence (colour-coded by entailment probability)
  - Side-by-side comparison with Lead-3 and single-stage BART baselines
  - Download results as JSON

Run:
    streamlit run app/app.py
"""

import sys
import json
import time
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent.parent))


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="News Summarisation Pipeline",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.fcs-high   { color: #1a7a3a; font-weight: 600; }
.fcs-mid    { color: #b38000; font-weight: 600; }
.fcs-low    { color: #c0392b; font-weight: 600; }
.fallback-badge { background: #faeeda; color: #633806; padding: 3px 10px;
                  border-radius: 999px; font-size: 0.85em; font-weight: 500; }
.abstract-badge { background: #eeedfe; color: #534ab7; padding: 3px 10px;
                  border-radius: 999px; font-size: 0.85em; font-weight: 500; }
.evidence-high  { background-color: rgba(39,174,96,0.18); border-radius: 4px;
                  padding: 2px 4px; }
.evidence-mid   { background-color: rgba(241,196,15,0.22); border-radius: 4px;
                  padding: 2px 4px; }
.evidence-low   { background-color: rgba(192,57,43,0.12); border-radius: 4px;
                  padding: 2px 4px; }
.metric-box { border: 0.5px solid #e0e0e0; border-radius: 8px; padding: 12px 16px;
              background: #f8f9fa; text-align: center; }
</style>
""", unsafe_allow_html=True)


# ── Model loading (cached so it only runs once) ───────────────────────────────
@st.cache_resource(show_spinner="Loading models … (first run only)")
def load_pipeline():
    from pipeline.pipeline import SummarizationPipeline
    return SummarizationPipeline(model_key="bart")

@st.cache_resource(show_spinner=False)
def load_lead3():
    from baselines.lead3 import Lead3Summarizer
    return Lead3Summarizer()

@st.cache_resource(show_spinner=False)
def load_bart_baseline():
    from baselines.bart_baseline import BartBaseline
    from config import BART_CKPT, USE_SELF_TRAINED_BART
    if USE_SELF_TRAINED_BART and BART_CKPT.exists() and any(BART_CKPT.iterdir()):
        try:
            return BartBaseline(mode="finetuned"), "BART-fine-tuned"
        except FileNotFoundError:
            pass
    return BartBaseline(mode="zeroshot"), "BART-pretrained (facebook/bart-large-cnn)"


# ── Helper functions ──────────────────────────────────────────────────────────

def fcs_colour(fcs: float) -> str:
    if fcs >= 0.65:
        return "fcs-high"
    elif fcs >= 0.40:
        return "fcs-mid"
    return "fcs-low"


def render_evidence_trace(trace: list):
    """Render sentence-level evidence trace with colour coding."""
    if not trace:
        st.info("No evidence trace available (extractive fallback was used).")
        return

    st.markdown("**Sentence-level evidence trace**")
    st.caption("Colour intensity = entailment probability → source sentence")

    for t in trace:
        prob    = t["entail_prob"]
        css_cls = "evidence-high" if prob >= 0.65 else (
                  "evidence-mid"  if prob >= 0.40 else "evidence-low")
        st.markdown(
            f'<span class="{css_cls}"><b>[{prob:.2f}]</b> {t["summary_sent"]}</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"↳ Source: {t['best_evidence'][:120]}{'…' if len(t['best_evidence']) > 120 else ''}")


def render_evidence_pool(pool: list, max_show: int = 5):
    """Show top retrieved evidence sentences."""
    if not pool:
        return
    st.markdown("**Retrieved evidence (top 5 by hybrid score)**")
    top = sorted(pool, key=lambda x: x["hybrid_score"], reverse=True)[:max_show]
    for e in top:
        score = e["hybrid_score"]
        bar   = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        st.markdown(
            f"`{bar}` `{score:.3f}` — {e['sentence'][:120]}"
            + ("…" if len(e["sentence"]) > 120 else "")
        )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Settings")
    show_baseline   = st.checkbox("Show baseline comparison", value=True)
    show_trace      = st.checkbox("Show evidence trace", value=True)
    show_pool       = st.checkbox("Show retrieved evidence", value=False)
    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "**Dissertation**: A Two-Stage Summarisation Pipeline "
        "for News Articles: Extraction-Guided Abstractive Generation  \n"
        "**BITS ID**: 2024AA05606  \n"
        "**Degree**: M.Tech AIML, BITS Pilani WILP"
    )
    st.markdown("---")
    st.markdown("### Pipeline stages")
    st.markdown(
        "1. 🔍 Evidence retrieval (BM25 + embeddings)  \n"
        "2. 🤖 Abstractive generation (BART, Best-of-N)  \n"
        "3. ✅ Evidence verification (NLI)  \n"
        "4. 🏆 Preference reranking + fallback"
    )


# ── Main UI ───────────────────────────────────────────────────────────────────
st.title("📰 News Summarisation Pipeline")
st.markdown(
    "Grounded, verifiable abstractive summarisation with "
    "evidence retrieval, NLI-based fact-checking, and extractive fallback."
)

# ── Input area ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    sample_articles = {
        "Custom input": "",
        "NASA Moon Mission": (
            "NASA announced on Thursday that its Artemis programme will send "
            "astronauts back to the Moon in 2026. The mission will include "
            "the first woman and first person of colour to walk on the lunar surface. "
            "The agency has been developing the Space Launch System rocket for over "
            "a decade at a cost of more than 20 billion dollars. "
            "Critics have questioned whether the timeline is achievable given "
            "recent technical setbacks with the Orion capsule heat shield. "
            "NASA administrator Bill Nelson expressed confidence the programme "
            "remains on track and all major issues have been resolved."
        ),
        "UK Economy Growth": (
            "The UK economy grew by 0.6 percent in the first quarter of 2026, "
            "according to figures released by the Office for National Statistics. "
            "The growth was driven primarily by the services sector, which accounts "
            "for around 80 percent of economic output. Manufacturing output fell "
            "slightly during the same period due to weaker export demand. "
            "The Bank of England said it would keep interest rates unchanged "
            "at its next meeting, citing stable inflation expectations. "
            "Analysts were cautiously optimistic but warned that global trade "
            "uncertainty could dampen growth in the second half of the year."
        ),
    }
    selected = st.selectbox("Choose a sample article or enter your own:", list(sample_articles.keys()))

with col2:
    st.markdown("&nbsp;", unsafe_allow_html=True)

article_text = st.text_area(
    "News article",
    value=sample_articles.get(selected, ""),
    height=240,
    placeholder="Paste a news article here …",
)

run_btn = st.button("▶  Run pipeline", type="primary", use_container_width=True)

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_btn:
    if len(article_text.strip()) < 50:
        st.warning("Please paste a longer article (at least 50 characters).")
        st.stop()

    pipeline = load_pipeline()

    with st.spinner("Running pipeline …"):
        t0     = time.time()
        result = pipeline.summarise(article_text)
        elapsed = round(time.time() - t0, 2)

    # ── Pipeline result ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📄 Pipeline output")

    # Metric row
    m1, m2, m3, m4 = st.columns(4)
    fcs_val  = result["fcs"]
    bs_val   = result["bertscore"]
    with m1:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600;'
            f'color:{"#1a7a3a" if fcs_val>=0.65 else "#b38000" if fcs_val>=0.4 else "#c0392b"}">'
            f'{fcs_val:.3f}</div><div style="font-size:0.8em;color:#666">Factual Consistency (FCS)</div></div>',
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600">'
            f'{bs_val:.3f}</div><div style="font-size:0.8em;color:#666">BERTScore F1</div></div>',
            unsafe_allow_html=True,
        )
    with m3:
        badge = (
            '<span class="fallback-badge">Extractive fallback</span>'
            if result["fallback"]
            else '<span class="abstract-badge">Abstractive</span>'
        )
        st.markdown(
            f'<div class="metric-box">{badge}'
            f'<div style="font-size:0.8em;color:#666;margin-top:6px">Output mode</div></div>',
            unsafe_allow_html=True,
        )
    with m4:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600">'
            f'{elapsed}s</div><div style="font-size:0.8em;color:#666">Latency</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Summary")
    st.success(result["summary"])

    if show_trace:
        st.markdown("### Evidence trace")
        render_evidence_trace(result.get("evidence_trace", []))

    if show_pool:
        st.markdown("### Retrieved evidence")
        render_evidence_pool(result.get("evidence_pool", []))

    # ── Baseline comparison ───────────────────────────────────────────────────
    if show_baseline:
        st.markdown("---")
        st.markdown("## 📊 Baseline comparison")

        lead3 = load_lead3()
        bart_base, bart_label = load_bart_baseline()

        with st.spinner("Running baselines …"):
            r_lead3 = lead3(article_text)
            r_bart  = bart_base(article_text)

        b1, b2 = st.columns(2)
        with b1:
            st.markdown("**Lead-3 baseline**")
            st.info(r_lead3["summary"])
        with b2:
            st.markdown(f"**{bart_label}**")
            st.info(r_bart["summary"])

    # ── Download ──────────────────────────────────────────────────────────────
    st.markdown("---")
    download_data = {
        "article_excerpt": article_text[:500],
        "summary":         result["summary"],
        "fallback":        result["fallback"],
        "fcs":             result["fcs"],
        "bertscore":       result["bertscore"],
        "evidence_trace":  result.get("evidence_trace", []),
    }
    st.download_button(
        label="⬇ Download results (JSON)",
        data=json.dumps(download_data, indent=2),
        file_name="summarisation_result.json",
        mime="application/json",
    )

else:
    st.markdown("---")
    st.markdown(
        "👆 Paste a news article above and click **Run pipeline** to see "
        "the grounded summarisation in action."
    )
    st.markdown("#### How it works")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**🔍 Stage 1**  \nEvidence retrieval  \nHybrid BM25 + embeddings")
    with c2:
        st.markdown("**🤖 Stage 2**  \nAbstractive generation  \nBART, N candidates")
    with c3:
        st.markdown("**✅ Stage 3**  \nEvidence verification  \nNLI factual consistency")
    with c4:
        st.markdown("**🏆 Stage 4**  \nPreference reranking  \nBest candidate or fallback")
