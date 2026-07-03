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
    return SummarizationPipeline(model_key="bart", safety_mode="dynamic")

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
def render_evidence_trace(trace: list):
    """Render sentence-level evidence trace with colour coding."""
    if not trace:
        st.info("No evidence trace available (extractive fallback was used).")
        return

    st.markdown("**Sentence-level evidence trace**")
    st.caption("Colour intensity = entailment probability → source sentence")

    for t in trace:
        prob    = t["entail_prob"]
        if prob >= 0.65:
            css_cls = "evidence-high"
        elif prob >= 0.40:
            css_cls = "evidence-mid"
        else:
            css_cls = "evidence-low"
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
    dynamic_switch  = st.toggle("Difficulty-aware safety switch", value=True)
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
        "4. 🏆 Difficulty-aware reranking + fallback"
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
        "[Science] NASA Moon Mission": (
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
        "[Economy] UK Economy Growth": (
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
        "[Politics] Ayodhya Temple Case": (
            "K.C. Venugopal questioned the credibility of the Special Investigation Team (SIT) "
            "constituted by the Uttar Pradesh government, saying it appeared to be little more than an 'eyewash'. "
            "Stepping up the Congress's attack over the alleged embezzlement of donations at the Ram temple in "
            "Ayodhya, party general secretary K.C. Venugopal on Thursday (July 2, 2026) wrote to Prime Minister "
            "Narendra Modi seeking an immediate Supreme Court-monitored probe into what he described as the "
            "\"Chanda Chori mega scandal\". In his letter, Mr. Venugopal alleged that the fraud involved "
            "\"hundreds of crores\" and amounted to a \"monumental betrayal\" of the Hindu faith, religion and way of life. "
            "He also questioned the credibility of the Special Investigation Team (SIT) constituted by the "
            "Uttar Pradesh government, saying it appeared to be little more than an \"eyewash\". He further alleged "
            "that there was a growing apprehension that the investigation was being used to erase the remaining "
            "evidence while shielding the \"big fish\" behind the alleged multi-crore embezzlement. \"Lord Ram is "
            "revered as the embodiment of justice and righteousness. Allowing allegations of this nature to be buried, "
            "rather than impartially investigated, would be a profound injustice to his devotees and to the values "
            "he embodies,\" Mr. Venugopal said. He claimed that the offerings made by ordinary citizens have been "
            "shamelessly looted. Mr. Venugopal said the \"systemic lapses at every level\" suggested that the alleged "
            "loot had been enabled by institutional support. \"On one hand, the counting staff bypassed regular "
            "surveillance to siphon off bundles of cash and valuable jewellery on a daily basis; on the other, 7 to 8 "
            "months of crucial CCTV footage was deliberately destroyed to cover the tracks of this criminal enterprise,\" "
            "he alleged. Mr. Venugopal also claimed that complaints of embezzlement and theft were either ignored or "
            "actively suppressed. The Trust's former Chief Accounts Officer, who flagged these systematic irregularities, "
            "was unceremoniously removed. So far only the 'small fish' have been arrested, while the institutional "
            "support and chain of command remain untouched. \"A state-appointed SIT is neither equipped nor "
            "institutionally independent to investigate individuals wielding immense political and institutional "
            "influence,\" he said. The alleged embezzlement came to light after an SIT constituted by the Uttar "
            "Pradesh government submitted its preliminary findings, following which an FIR was registered on June 25. "
            "Eight accused were subsequently arrested, and the police said nearly Rs 80 lakh in cash, besides some "
            "foreign currency, had been recovered so far from six of them."
        ),
        "[Business] Tech Merger Antitrust Dispute": (
            "The Federal Trade Commission (FTC) on Monday filed a lawsuit in federal court to block the proposed "
            "$8.4 billion acquisition of software company CloudSphere by tech giant Apex Corp. The regulator argued "
            "that the deal, first announced on January 14, 2025, would eliminate critical competition in the cloud "
            "database sector. Under the terms of the agreement, Apex Corp had agreed to pay $95 per share in cash, "
            "a 32% premium over CloudSphere's trading price at the time. However, FTC Chair Lina Khan expressed concerns "
            "that Apex Corp would integrate CloudSphere's services to restrict access to smaller competitors like "
            "DataVentures and NexaCloud. Apex Corp's CEO, Julian Vance, pushed back against the allegations in a press "
            "briefing, stating that the merger would actually accelerate innovation and reduce deployment costs for "
            "end-users by up to 25%. European Union regulators at the European Commission are also reviewing the "
            "transaction, with a provisional deadline set for September 18, 2026. The Department of Justice (DOJ) "
            "had previously cleared a related $1.2 billion acquisition of SecurityGate by Apex Corp in late 2024, "
            "but analysts suggest the current political climate poses a much steeper challenge for this transaction. "
            "CloudSphere's stock fell by 14.3% to $72.10 following the FTC's announcement, while Apex Corp saw a "
            "minor 1.2% dip."
        ),
        "[Health] Biotech Clinical Trial Results": (
            "Biopharmaceutical firm Theragenics on Wednesday released Phase III clinical trial results for its "
            "new experimental oncology drug, OncoShield, designed to treat advanced non-small cell lung cancer (NSCLC). "
            "The randomized double-blind study, which enrolled 1,420 patients across 82 clinical sites globally, "
            "compared OncoShield against the current standard of care, Paclitaxel. According to the company's official "
            "filing, patients receiving OncoShield demonstrated a median progression-free survival (PFS) of 14.8 months, "
            "compared to 9.2 months for the control group receiving Paclitaxel. This represented a statistically significant "
            "38% reduction in the risk of disease progression or death (hazard ratio of 0.62). However, safety data "
            "revealed that 18.4% of patients in the OncoShield arm experienced Grade 3 or higher adverse events, "
            "primarily neutropenia and elevated liver enzymes, compared to 12.1% in the Paclitaxel arm. Three patient "
            "deaths in the experimental group were deemed possibly related to the treatment by independent monitors. "
            "Despite the safety signals, Theragenics Chief Medical Officer, Dr. Sarah Jenkins, announced plans to submit "
            "a New Drug Application (NDA) to the Food and Drug Administration (FDA) by December 2025, with a subsequent "
            "filing to the European Medicines Agency (EMA) in early 2026. Market shares in Theragenics surged 28.5% in "
            "early trading following the announcement, while its main competitor, CellVax, which is developing a rival "
            "therapy called LungCure, dropped by 8.2%."
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

    safety_mode = "dynamic" if dynamic_switch else "fixed"
    pipeline = load_pipeline()
    pipeline.safety_mode = safety_mode  # apply sidebar toggle without reloading models

    with st.spinner("Running pipeline …"):
        t0     = time.time()
        result = pipeline.summarise(article_text)
        elapsed = round(time.time() - t0, 2)

    # ── Pipeline result ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## 📄 Pipeline output")

    # Metric row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    fcs_val  = result["fcs"]
    bs_val   = result["bertscore"]
    if fcs_val >= 0.65:
        fcs_color = "#1a7a3a"
    elif fcs_val >= 0.4:
        fcs_color = "#b38000"
    else:
        fcs_color = "#c0392b"

    with m1:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600;'
            f'color:{fcs_color}">'
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
    with m5:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600">'
            f'{result.get("threshold_used", 0.0):.3f}</div>'
            f'<div style="font-size:0.8em;color:#666">Threshold Used</div></div>',
            unsafe_allow_html=True,
        )
    with m6:
        st.markdown(
            f'<div class="metric-box"><div style="font-size:1.4em;font-weight:600">'
            f'{result.get("difficulty_score", 0.0):.3f}</div>'
            f'<div style="font-size:0.8em;color:#666">Difficulty Score</div></div>',
            unsafe_allow_html=True,
        )

    st.caption(f"Safety mode: {result.get('safety_mode', safety_mode)}")

    difficulty_signals = result.get("difficulty_signals", {})
    if difficulty_signals:
        st.markdown("### Difficulty signals")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.progress(float(difficulty_signals.get("length_norm", 0.0)), text=f"Length: {difficulty_signals.get('length_norm', 0.0):.2f}")
        with d2:
            st.progress(float(difficulty_signals.get("entity_norm", 0.0)), text=f"Entity density: {difficulty_signals.get('entity_norm', 0.0):.2f}")
        with d3:
            st.progress(float(difficulty_signals.get("uncertainty_norm", 0.0)), text=f"Retrieval uncertainty: {difficulty_signals.get('uncertainty_norm', 0.0):.2f}")

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
        "threshold_used":  result.get("threshold_used"),
        "difficulty_score": result.get("difficulty_score"),
        "difficulty_signals": result.get("difficulty_signals", {}),
        "safety_mode": result.get("safety_mode", safety_mode),
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
