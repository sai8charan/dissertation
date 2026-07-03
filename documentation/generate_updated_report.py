"""
Generate updated mid-semester report matching original PDF structure.
All text is black, consistent 12pt body / 14pt section headings.
No irregular page breaks. Minimal whitespace. 5 references only.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import nsdecls
from docx.oxml import parse_xml

OUT_DOCX = Path(__file__).parent / "2024AA05606_Updated_Report.docx"
OUT_PDF = Path(__file__).parent / "2024AA05606_Updated_Report.pdf"

FONT_NAME = "Times New Roman"
BODY_SIZE = Pt(12)
HEADING_SIZE = Pt(14)
SUB_HEADING_SIZE = Pt(12)
TABLE_SIZE = Pt(10)
SMALL_SIZE = Pt(10)


def build_report():
    doc = Document()

    # --- Global style setup ---
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.line_spacing = 1.15

    # Margins
    for sec in doc.sections:
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(2.54)
        sec.right_margin = Cm(2.54)

    # --- Helper closures ---
    def center(text, size=BODY_SIZE, bold=False, after=Pt(4)):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = after
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(text)
        r.font.name = FONT_NAME
        r.font.size = size
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.bold = bold
        return p

    def body(text, after=Pt(6), bold=False, italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = after
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(text)
        r.font.name = FONT_NAME
        r.font.size = BODY_SIZE
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.bold = bold
        r.italic = italic
        return p

    def heading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(text)
        r.font.name = FONT_NAME
        r.font.size = HEADING_SIZE
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.bold = True
        # Add bottom border
        pPr = p._p.get_or_add_pPr()
        pBdr = parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'<w:bottom w:val="single" w:sz="4" w:space="1" w:color="000000"/>'
            f'</w:pBdr>'
        )
        pPr.append(pBdr)
        return p

    def subheading(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(text)
        r.font.name = FONT_NAME
        r.font.size = SUB_HEADING_SIZE
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.bold = True
        return p

    def bullet(text):
        p = doc.add_paragraph(style="List Bullet")
        p.clear()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.space_before = Pt(0)
        r = p.add_run(text)
        r.font.name = FONT_NAME
        r.font.size = BODY_SIZE
        r.font.color.rgb = RGBColor(0, 0, 0)
        return p

    def table(headers, rows):
        t = doc.add_table(rows=1 + len(rows), cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, h in enumerate(headers):
            c = t.rows[0].cells[i]
            c.text = ""
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h)
            r.font.name = FONT_NAME
            r.font.size = TABLE_SIZE
            r.font.color.rgb = RGBColor(0, 0, 0)
            r.bold = True
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                c = t.rows[ri + 1].cells[ci]
                c.text = ""
                p = c.paragraphs[0]
                r = p.add_run(str(val))
                r.font.name = FONT_NAME
                r.font.size = TABLE_SIZE
                r.font.color.rgb = RGBColor(0, 0, 0)
        return t

    # ════════════════════════════════════════════════════════════════════
    # PAGE 1 — TITLE
    # ════════════════════════════════════════════════════════════════════
    for _ in range(4):
        doc.add_paragraph().paragraph_format.space_after = Pt(0)

    center("A TWO-STAGE SUMMARIZATION PIPELINE FOR\nNEWS ARTICLES:\nEXTRACTION-GUIDED ABSTRACTIVE GENERATION",
           size=Pt(16), bold=True, after=Pt(14))
    center("AIMLCZG628T: DISSERTATION – MID-SEMESTER REPORT", size=BODY_SIZE, after=Pt(20))
    center("by", after=Pt(4))
    center("PUTHINEEDI VENKATA SAI CHARAN", size=Pt(13), bold=True, after=Pt(2))
    center("2024AA05606", size=Pt(13), bold=True, after=Pt(20))
    center("Dissertation work carried out at", after=Pt(2))
    center("Opentext", bold=True, after=Pt(20))
    center("Submitted in partial fulfilment of the", after=Pt(2))
    center("WILP M.Tech. Artificial Intelligence and Machine Learning", after=Pt(2))
    center("degree programme", after=Pt(20))
    center("Under the Supervision of", after=Pt(2))
    center("Veeraswamy Ponnuru", bold=True, after=Pt(2))
    center("Lead Quality Assurance Engineer", after=Pt(2))
    center("Opentext", after=Pt(30))
    center("BIRLA INSTITUTE OF TECHNOLOGY & SCIENCE", bold=True, after=Pt(2))
    center("PILANI (RAJASTHAN)", bold=True, after=Pt(2))
    center("July 2026", after=Pt(0))

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 2 — ABSTRACT
    # ════════════════════════════════════════════════════════════════════
    heading("ABSTRACT")

    body("The exponential growth of online news content has made timely information processing increasingly challenging for readers, professionals, and organisations alike. Automatic text summarisation systems that can condense lengthy news articles into concise, accurate, and fluent summaries hold significant practical value, particularly in enterprise content management and information retrieval contexts.")

    body("Existing summarisation approaches are broadly divided into two paradigms: extractive methods, which preserve factual accuracy but produce disjointed output, and abstractive methods, which leverage pre-trained transformer models such as BART and PEGASUS to generate fluent text but risk factual hallucination on longer documents. This dissertation proposes and implements a grounded, two-stage summarisation pipeline that integrates both paradigms. A hybrid evidence retrieval stage, combining BM25 lexical scoring with sentence-embedding similarity, first identifies the most salient sentences from the source article within the abstractive model's input budget. A fine-tuned BART model then generates multiple candidate summaries using nucleus sampling. Each candidate is evaluated against the retrieved evidence using a Natural Language Inference (NLI) based verifier that computes a Factual Consistency Score (FCS), and a preference reranker selects the most factually consistent and fluent candidate, with a difficulty-aware extractive fallback mechanism that adapts its threshold based on article complexity.")

    body("The key novelty of this work is a Difficulty-Aware Safety Switch that replaces a fixed FCS threshold with a dynamic, per-article threshold computed from three signals: article length complexity, entity density, and retrieval uncertainty. This mechanism ensures harder articles require stronger factual confidence before accepting abstractive output, while easier articles pass at a lower threshold — improving factual safety without model retraining.")

    body("At the mid-semester milestone, the dataset preparation, baseline implementations, the complete pipeline with difficulty-aware fallback, ablation studies, and a Streamlit demonstration application have been completed. Remaining work includes human evaluation and final dissertation write-up.")

    body("Keywords: Automatic Text Summarisation, NLP, BART, Evidence Retrieval, Factual Consistency, NLI, BM25, Difficulty-Aware Threshold.", italic=True)

    # Signatures
    body("")
    sig = table(
        ["Signature of the Student", "Signature of the Supervisor"],
        [
            ["Name: Puthineedi Venkata Sai Charan", "Name: Veeraswamy Ponnuru"],
            ["Date: 03/07/2026", "Date: 03/07/2026"],
            ["Place: Hyderabad", "Place: Hyderabad"],
        ],
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 3 — CONTENTS
    # ════════════════════════════════════════════════════════════════════
    heading("CONTENTS")

    table(
        ["Section", "Page"],
        [
            ["1. Introduction and Problem Context", "4"],
            ["2. Objectives and Research Questions", "4"],
            ["3. System Modules Completed", "5"],
            ["4. System Architecture and Methodology", "6"],
            ["5. Tools and Technologies Used", "7"],
            ["6. Methodology and Pipeline Implementation", "8"],
            ["7. Experimental Setup and Baselines", "9"],
            ["8. Experimental Results", "9"],
            ["9. Current Implementation Status", "10"],
            ["10. Technical Specifications", "11"],
            ["11. Design Considerations", "11"],
            ["12. Preliminary Observations and Risks", "12"],
            ["13. Future Plan", "12"],
            ["14. Abbreviations", "13"],
            ["15. References", "13"],
        ],
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 4 — SECTION 1 & 2
    # ════════════════════════════════════════════════════════════════════
    heading("1. INTRODUCTION AND PROBLEM CONTEXT")

    body("The rapid proliferation of digital news content has created an information overload challenge for individuals and organisations. Manual review of news articles at scale is neither practical nor scalable. Automatic text summarisation addresses this challenge by producing condensed, coherent representations of source documents. Despite substantial research progress, existing systems face persistent limitations in factual accuracy: abstractive models generate fluent text but often introduce claims not grounded in the source, while purely extractive approaches avoid hallucination at the cost of fluency and conciseness.")

    body("This dissertation — titled A Two-Stage Summarization Pipeline for News Articles: Extraction-Guided Abstractive Generation — addresses the factual grounding problem by designing a modular pipeline that sequences evidence retrieval, abstractive generation, NLI-based verification, and preference reranking with a difficulty-aware extractive fallback. The proposed system targets the CNN/DailyMail benchmark and is evaluated using ROUGE, BERTScore, and NLI-based Factual Consistency Score (FCS) metrics.")

    body("A critical limitation of prior pipelines employing factual verification is the use of a fixed confidence threshold. A single threshold cannot account for the wide variation in article difficulty. This work introduces a Difficulty-Aware Safety Switch that computes a per-article difficulty score and adjusts the fallback threshold dynamically.")

    subheading("1.1 Scope at the Mid-Semester Stage")
    bullet("Dataset acquisition, preprocessing, and corpus analysis on CNN/DailyMail")
    bullet("Four baseline systems implemented and evaluated (Lead-3, TextRank, BART zero-shot, BART pretrained)")
    bullet("Complete pipeline: evidence retrieval, generation, NLI verification, difficulty-aware reranking")
    bullet("Difficulty-Aware Safety Switch designed, implemented, and validated")
    bullet("Ablation studies, PEGASUS/mBART comparison, and Streamlit demo completed")

    heading("2. OBJECTIVES AND RESEARCH QUESTIONS")

    bullet("Achieve ROUGE-2 ≥ 18.0 on CNN/DailyMail, surpassing Lead-3 baseline")
    bullet("Achieve NLI-FCS ≥ 0.65, compared to ≤ 0.55 for single-stage BART")
    bullet("Maintain extractive fallback rate below 15%")
    bullet("Demonstrate difficulty-aware threshold adapts to article complexity")
    bullet("Achieve human evaluation mean factual accuracy ≥ 4.0/5.0")

    subheading("2.1 Research Questions")
    bullet("RQ1: Does hybrid BM25 + embedding retrieval improve factual consistency over truncation?")
    bullet("RQ2: Does Best-of-N with NLI reranking improve FCS over greedy decoding?")
    bullet("RQ3: Does difficulty-aware dynamic threshold reduce factual risk vs. fixed threshold?")
    bullet("RQ4: How does the pipeline compare to BART, PEGASUS, and mBART?")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 5 — SECTION 3
    # ════════════════════════════════════════════════════════════════════
    heading("3. SYSTEM MODULES COMPLETED")

    subheading("3.1 Dataset Preparation and Corpus Analysis")
    body("CNN/DailyMail dataset acquired and split (70/15/15). Corpus statistics computed. Hindi XL-Sum subset prepared for multilingual feasibility study.")

    subheading("3.2 Lead-3 Baseline")
    body("Returns the first three sentences, exploiting journalistic front-loading convention.")

    subheading("3.3 TextRank Baseline")
    body("Unsupervised graph-based extractive approach using eigenvector centrality ranking.")

    subheading("3.4 Zero-Shot BART Baseline")
    body("Pre-trained BART-large-cnn applied without fine-tuning, isolating pre-training benefits.")

    subheading("3.5 Fine-Tuned BART Baseline")
    body("BART-large fine-tuned on CNN/DailyMail for 3 epochs. Standard single-stage abstractive pipeline.")

    subheading("3.6 Evidence Retrieval Module")
    body("Hybrid BM25 + sentence-embedding cosine similarity. Top sentences within 1024-token budget form context and evidence pool.")

    subheading("3.7 Best-of-N Abstractive Generation")
    body("Fine-tuned BART generates N=5 diverse candidates via nucleus sampling (top_p=0.92).")

    subheading("3.8 NLI Evidence Verification")
    body("DeBERTa-based NLI model computes per-sentence entailment probability. Mean across candidate sentences forms the Factual Consistency Score (FCS).")

    subheading("3.9 Preference Reranker with Difficulty-Aware Fallback")
    body("Candidates ranked by 0.6×FCS + 0.4×BERTScore-F1. If best candidate < dynamic threshold → extractive fallback.")

    subheading("3.10 Difficulty-Aware Safety Switch (Novel Contribution)")
    body("Computes per-article difficulty D from three signals. Dynamic threshold: Threshold = 0.40 + 0.20 × D. Adapts fallback to article complexity without model retraining.")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 6 — SECTION 4
    # ════════════════════════════════════════════════════════════════════
    heading("4. SYSTEM ARCHITECTURE AND METHODOLOGY")

    body("The system follows a modular four-stage pipeline extending conventional extractive-abstractive summarisation with verification and selection layers.")

    subheading("4.1 High-Level Architecture")
    bullet("Stage 1 – Evidence Retrieval: Hybrid BM25 + embedding scoring, top-K sentences within 1024-token budget.")
    bullet("Stage 2 – Abstractive Generation: Fine-tuned BART, N=5 candidates via nucleus sampling.")
    bullet("Stage 3 – NLI Verification: Sentence-level entailment scoring → per-candidate FCS.")
    bullet("Stage 4 – Difficulty-Aware Reranking: Weighted rank + dynamic threshold + extractive guard.")

    # Architecture diagram as table
    body("")
    arch = doc.add_table(rows=3, cols=11)
    arch.style = "Table Grid"
    arch.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Title row
    c0 = arch.rows[0].cells[0]
    c0.merge(arch.rows[0].cells[10])
    c0.text = ""
    p = c0.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Two-Stage Grounded Summarisation Pipeline — Architecture")
    r.font.size = TABLE_SIZE
    r.font.color.rgb = RGBColor(0, 0, 0)
    r.bold = True

    # Stage boxes
    boxes = ["INPUT\nNews\nArticle", "→", "Stage 1\nEvidence\nRetrieval", "→",
             "Stage 2\nAbstractive\nGeneration", "→", "Stage 3\nNLI\nVerification", "→",
             "Stage 4\nDifficulty-Aware\nReranking", "→", "OUTPUT\nFactual\nSummary"]
    for i, txt in enumerate(boxes):
        c = arch.rows[1].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(txt)
        r.font.size = Pt(8)
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.bold = (i in [0, 10])

    # Sub-descriptions
    subs = ["", "", "Hybrid BM25\n+ embedding", "", "N-candidate\nnucleus sampling", "",
            "Sentence-level\nFCS scoring", "", "Dynamic threshold\n+ extractive guard", "", ""]
    for i, txt in enumerate(subs):
        c = arch.rows[2].cells[i]
        c.text = ""
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(txt)
        r.font.size = Pt(7)
        r.font.color.rgb = RGBColor(0, 0, 0)
        r.italic = True

    body("Figure 1: High-level architecture of the proposed pipeline.", italic=True, after=Pt(8))

    subheading("4.2 Literature Context")
    bullet("BART (Lewis et al., ACL 2020): Primary abstractive generator, fine-tuned on CNN/DailyMail.")
    bullet("PEGASUS (Zhang et al., ICML 2020): Domain-pretrained comparison baseline.")
    bullet("SummaC (Laban et al., TACL 2022): NLI-based inconsistency detection, informs FCS design.")
    bullet("Provenance (Sankararaman et al., EMNLP 2024): Light-weight RAG fact-checking, motivates verification stage.")
    bullet("MiniCheck (Tang et al., EMNLP 2024): Efficient grounding verification — validates NLI approach at scale.")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 7 — SECTION 5
    # ════════════════════════════════════════════════════════════════════
    heading("5. TOOLS AND TECHNOLOGIES USED")

    table(
        ["Component", "Technology / Library"],
        [
            ["Dataset & Preprocessing", "HuggingFace Datasets, NLTK"],
            ["Evidence Retrieval", "rank_bm25, sentence-transformers (all-MiniLM-L6-v2)"],
            ["Abstractive Generation", "HuggingFace Transformers (BART-large, PEGASUS, mBART), PyTorch"],
            ["NLI Verification", "cross-encoder/nli-deberta-v3-base"],
            ["Difficulty Scoring", "Custom module (pipeline/difficulty.py)"],
            ["Reranking & Evaluation", "bert-score, rouge-score, NumPy"],
            ["Demo Application", "Streamlit"],
        ],
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 8 — SECTION 6
    # ════════════════════════════════════════════════════════════════════
    heading("6. METHODOLOGY AND PIPELINE IMPLEMENTATION")

    subheading("6.1 Evidence Retrieval")
    body("Each sentence is scored using hybrid BM25 + sentence-embedding cosine similarity. Top-K sentences within 1024-token budget form both generation context and verification evidence pool.")

    subheading("6.2 Abstractive Generation")
    body("BART-large fine-tuned for 3 epochs (lr=3e-5, batch 2, grad accum 8). At inference, N=5 diverse candidates generated via nucleus sampling (top_p=0.92).")

    subheading("6.3 NLI Evidence Verification")
    body("Each summary sentence matched to best evidence sentence; entailment probability computed via DeBERTa NLI. Mean probability = FCS.")

    subheading("6.4 Preference Reranking")
    body("final_score = 0.6 × FCS + 0.4 × BERTScore_F1", bold=True)
    body("Top candidate selected. If below dynamic threshold → extractive fallback from evidence set.")

    subheading("6.5 Difficulty-Aware Safety Switch (Novel Contribution)")
    body("D = 0.4 × LengthNorm + 0.3 × EntityNorm + 0.3 × UncertaintyNorm", bold=True)
    bullet("LengthNorm = min(word_count / 800, 1.0)")
    bullet("EntityNorm = min(entity_count / 20, 1.0)")
    bullet("UncertaintyNorm = 1.0 − margin between top-2 evidence scores")
    body("Threshold_dynamic = 0.40 + 0.20 × D", bold=True)
    body("Range: [0.40, 0.60]. Harder articles need stronger confidence. No model retraining required.")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 9 — SECTION 7 & 8
    # ════════════════════════════════════════════════════════════════════
    heading("7. EXPERIMENTAL SETUP AND BASELINES")

    body("All systems evaluated on CNN/DailyMail test split with difficulty-stratified sampling. Metrics: ROUGE-1/2/L, BERTScore-F1, NLI-FCS.")

    heading("8. EXPERIMENTAL RESULTS")

    subheading("8.1 Baseline Comparison (n=15, difficulty-stratified)")
    table(
        ["System", "ROUGE-1", "ROUGE-2", "ROUGE-L", "BERTScore F1"],
        [
            ["Lead-3", "44.68", "23.47", "29.84", "87.84"],
            ["TextRank", "26.77", "12.28", "18.63", "85.72"],
            ["BART-zero-shot", "40.19", "21.21", "26.48", "87.07"],
            ["BART-pretrained", "47.46", "26.62", "37.14", "88.99"],
        ],
    )

    subheading("8.2 Pipeline with Difficulty-Aware Safety Switch (n=15)")
    table(
        ["System", "R-1", "R-2", "R-L", "BERT", "FCS", "Fallback", "Thresh.", "Difficulty"],
        [
            ["Pipeline (dynamic)", "38.69", "17.57", "27.18", "87.40", "0.9998", "0.0%", "0.555", "0.777"],
        ],
    )

    subheading("8.3 Large-Scale Evaluation (n=300)")
    table(
        ["System", "R-1", "R-2", "R-L", "BERT", "FCS", "Halluc.", "Latency"],
        [
            ["Pipeline (hybrid+verify+rerank)", "30.72", "10.10", "20.55", "87.00", "0.9997", "0.0%", "34.5s"],
            ["PEGASUS-pretrained", "35.34", "14.74", "25.74", "87.38", "0.9997", "0.0%", "—"],
        ],
    )

    subheading("8.4 Key Observations")
    bullet("Pipeline achieves FCS=0.9998 with 0% hallucination rate (exceeds target of 0.65).")
    bullet("Dynamic threshold averaged 0.555 vs. fixed 0.40, confirming adaptation to complexity.")
    bullet("ROUGE-2 of 17.57 approaches target of 18.0.")
    bullet("Zero hallucinations across all runs (n=15 and n=300).")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 10 — SECTION 9
    # ════════════════════════════════════════════════════════════════════
    heading("9. CURRENT IMPLEMENTATION STATUS")

    table(
        ["Work Package", "Deliverable", "Status", "Evidence"],
        [
            ["Dataset preparation", "CNN/DM splits, stats", "COMPLETED", "Corpus stats"],
            ["Baseline implementation", "Lead-3, TextRank, BART, PEGASUS", "COMPLETED", "Metric tables"],
            ["Evidence retrieval", "Hybrid BM25 + embedding", "COMPLETED", "Ablation results"],
            ["Abstractive generation", "BART Best-of-N sampling", "COMPLETED", "Outputs"],
            ["NLI verification & reranker", "FCS + fallback logic", "COMPLETED", "FCS analysis"],
            ["Difficulty-Aware Switch", "Dynamic threshold", "COMPLETED", "Threshold analysis"],
            ["PEGASUS/mBART comparison", "Comparative evaluation", "COMPLETED", "Metric tables"],
            ["Ablation studies", "Retrieval, N-cands, verifier", "COMPLETED", "Ablation tables"],
            ["Demo application", "Streamlit + difficulty viz", "COMPLETED", "Working demo"],
            ["Human evaluation", "50 samples, 3 raters", "PENDING", "Inter-rater stats"],
        ],
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 11 — SECTION 10 & 11
    # ════════════════════════════════════════════════════════════════════
    heading("10. TECHNICAL SPECIFICATIONS")

    table(
        ["#", "Parameter", "Specification"],
        [
            ["1", "Primary dataset", "CNN/DailyMail (70/15/15 split)"],
            ["2", "Evidence retrieval", "Hybrid BM25 + all-MiniLM-L6-v2 (384-dim)"],
            ["3", "Primary generator", "BART-large-cnn, 3 epochs, lr=3e-5"],
            ["4", "Comparison generators", "PEGASUS-cnn_dailymail, mBART-large-cc25"],
            ["5", "Generation strategy", "Nucleus sampling, top_p=0.92, N=5"],
            ["6", "NLI verifier", "cross-encoder/nli-deberta-v3-base"],
            ["7", "Reranking formula", "0.6×FCS + 0.4×BERTScore-F1"],
            ["8", "Safety switch", "Threshold = 0.40 + 0.20 × D"],
            ["9", "Difficulty weights", "Len:0.4, Entity:0.3, Uncertainty:0.3"],
            ["10", "Evaluation metrics", "ROUGE-1/2/L, BERTScore, NLI-FCS"],
            ["11", "Demo", "Streamlit (local)"],
        ],
    )

    heading("11. DESIGN CONSIDERATIONS")

    bullet("Modularity: Each stage independently testable and replaceable.")
    bullet("Traceability: Every summary has evidence trace to source sentences.")
    bullet("Graceful degradation: Difficulty-aware fallback prevents unverified output.")
    bullet("Adaptivity: Dynamic threshold adapts without retraining.")
    bullet("Reproducibility: All hyperparameters, seeds, and splits documented.")
    bullet("Scope management: Local Streamlit demo; production deployment out of scope.")

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 12 — SECTION 12 & 13
    # ════════════════════════════════════════════════════════════════════
    heading("12. PRELIMINARY OBSERVATIONS AND RISKS")

    subheading("12.1 Observations")
    bullet("Hybrid retrieval selects coherent evidence not captured by keyword overlap alone.")
    bullet("Dynamic threshold averaged 0.555 (vs. fixed 0.40); most articles are moderately difficult.")
    bullet("Zero hallucination rate across all pipeline evaluations.")
    bullet("Mean latency 34.5s/article — acceptable for batch, needs optimisation for real-time.")

    subheading("12.2 Risks and Mitigations")
    table(
        ["Risk", "Mitigation"],
        [
            ["NLI reliability on long docs", "Evaluation restricted to CNN/DM (short docs)"],
            ["Compute cost", "Colab Pro+/Kaggle A100; gradient accumulation"],
            ["Annotator availability", "Limited to 50 samples, 3 raters"],
            ["Threshold sensitivity", "Ablation across threshold range"],
        ],
    )

    heading("13. FUTURE PLAN")

    table(
        ["Phase", "Dates", "Work", "Status"],
        [
            ["1. Setup", "25 Apr – 10 May", "Literature review, environment", "COMPLETED"],
            ["2. Baselines", "11 May – 31 May", "Pipeline design, baselines", "COMPLETED"],
            ["3. Pipeline", "01 Jun – 21 Jun", "Retrieval, generation, verification", "COMPLETED"],
            ["4. Novelty", "22 Jun – 12 Jul", "Difficulty switch, ablations, demo", "COMPLETED"],
            ["5. Final", "13 Jul – 02 Aug", "Human eval, dissertation, VIVA", "IN PROGRESS"],
        ],
    )

    doc.add_page_break()

    # ════════════════════════════════════════════════════════════════════
    # PAGE 13 — SECTION 14 & 15
    # ════════════════════════════════════════════════════════════════════
    heading("14. ABBREVIATIONS")

    table(
        ["Abbreviation", "Full Form"],
        [
            ["NLP", "Natural Language Processing"],
            ["BART", "Bidirectional and Auto-Regressive Transformer"],
            ["PEGASUS", "Pre-training with Extracted Gap-Sentences for Abstractive Summarization"],
            ["ROUGE", "Recall-Oriented Understudy for Gisting Evaluation"],
            ["BERTScore", "BERT-based Semantic Similarity Metric"],
            ["NLI", "Natural Language Inference"],
            ["FCS", "Factual Consistency Score"],
            ["BM25", "Best Matching 25"],
            ["CNN/DM", "CNN/DailyMail Benchmark Dataset"],
        ],
    )

    heading("15. REFERENCES")

    refs = [
        '[1] M. Lewis et al. "BART: Denoising Sequence-to-Sequence Pre-training for NLG, Translation, and Comprehension," Proc. ACL 2020, pp. 7871–7880.',
        '[2] J. Zhang et al. "PEGASUS: Pre-training with Extracted Gap-sentences for Abstractive Summarization," Proc. ICML 2020, pp. 11328–11339.',
        '[3] P. Laban et al. "SummaC: Re-visiting NLI-based Models for Inconsistency Detection in Summarization," Trans. ACL, Vol. 10, pp. 163–177, 2022.',
        '[4] H. Sankararaman et al. "Provenance: A Light-weight Fact-checker for Retrieval Augmented LLM Generation," Proc. EMNLP 2024.',
        '[5] L. Tang et al. "MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents," Proc. EMNLP 2024.',
    ]
    for ref in refs:
        body(ref, after=Pt(4))

    # ════════════════════════════════════════════════════════════════════
    # Page numbers in footer
    # ════════════════════════════════════════════════════════════════════
    for sec in doc.sections:
        footer = sec.footer
        footer.is_linked_to_previous = False
        p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.clear()
        run = p.add_run()
        fld1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
        run._r.append(fld1)
        run2 = p.add_run()
        instr = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
        run2._r.append(instr)
        run3 = p.add_run()
        fld2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
        run3._r.append(fld2)

    # Save
    doc.save(str(OUT_DOCX))
    print(f"DOCX saved: {OUT_DOCX}")

    try:
        from docx2pdf import convert
        convert(str(OUT_DOCX), str(OUT_PDF))
        print(f"PDF saved: {OUT_PDF}")
    except Exception as e:
        print(f"PDF conversion failed: {e}")


if __name__ == "__main__":
    build_report()
