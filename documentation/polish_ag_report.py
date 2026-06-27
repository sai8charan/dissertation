"""
documentation/polish_ag_report.py
-----------------------------------
Post-processes MidSem_Report_2024AA05606_ag.docx:

  1. Uniform professional table formatting (borders, header shading, alt rows).
  2. Removes malformed raw XML tables (no tblPr/tblGrid from ch2 insertion).
  3. Replaces architecture placeholder with a clean Word-table-based diagram.
  4. Global cleanup: consistent Times New Roman, spacing, margins.

Saves output as MidSem_Report_2024AA05606_ag.docx (overwrites).
If the file is open in Word, saves as MidSem_Report_2024AA05606_ag_polished.docx.

Run from dissertation root:
    python documentation/polish_ag_report.py
"""

from __future__ import annotations
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.paragraph import Paragraph

# ─────────────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
SRC_PATH  = ROOT / "documentation" / "MidSem_Report_2024AA05606_ag.docx"
OUT_PATH  = ROOT / "documentation" / "MidSem_Report_2024AA05606_ag.docx"
FALL_PATH = ROOT / "documentation" / "MidSem_Report_2024AA05606_ag_polished.docx"

# Design tokens
NAVY   = "1F3864"
BLUE   = "2E75B6"
ALT    = "DCE6F1"
WHITE  = "FFFFFF"
DKTEXT = "1F3864"
BODY_F = "Times New Roman"
HEAD_F = "Times New Roman"


# ══════════════════════════════════════════════════════════════════════════════
# TABLE FORMATTING UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_child(parent_el, tag):
    el = parent_el.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        parent_el.append(el)
    return el


def _set_table_borders(table):
    tbl   = table._tbl
    tblPr = _ensure_child(tbl, "w:tblPr")
    # Remove existing tblBorders and recreate
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "6")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), NAVY)
        tblBorders.append(el)
    tblPr.append(tblBorders)

    # Full-width auto
    tblW = _ensure_child(tblPr, "w:tblW")
    tblW.set(qn("w:w"),    "0")
    tblW.set(qn("w:type"), "auto")

    # Centre
    jc = _ensure_child(tblPr, "w:jc")
    jc.set(qn("w:val"), "center")


def _shade_cell(cell, fill: str):
    tcPr = _ensure_child(cell._tc, "w:tcPr")
    old  = tcPr.find(qn("w:shd"))
    if old is not None:
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  fill)
    tcPr.append(shd)


def _pad_cell(cell, top=72, bot=72, left=108, right=108):
    tcPr  = _ensure_child(cell._tc, "w:tcPr")
    tcMar = _ensure_child(tcPr, "w:tcMar")
    tcMar.clear()
    for side, val in (("top", top), ("bottom", bot), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"),    str(val))
        el.set(qn("w:type"), "dxa")
        tcMar.append(el)


def _set_cell_borders(cell):
    tcPr      = _ensure_child(cell._tc, "w:tcPr")
    tcBorders = _ensure_child(tcPr, "w:tcBorders")
    tcBorders.clear()
    for side in ("top", "bottom", "left", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "6")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), NAVY)
        tcBorders.append(el)


def _style_cell_runs(cell, bold=False, fg=None, sz=Pt(11)):
    for para in cell.paragraphs:
        para.paragraph_format.space_before = Pt(1)
        para.paragraph_format.space_after  = Pt(1)
        for run in para.runs:
            run.font.name = BODY_F
            run.font.size = sz
            run.bold = bold
            if fg:
                run.font.color.rgb = RGBColor.from_string(fg)
        # If paragraph has text but no runs (can happen in merged cells)
        if para.text and not para.runs:
            run = para.add_run(para.text)
            run.font.name = BODY_F
            run.font.size = sz
            run.bold = bold
            if fg:
                run.font.color.rgb = RGBColor.from_string(fg)


def format_table(table, has_header=True, alt_rows=True):
    """Apply professional formatting to a table."""
    _set_table_borders(table)
    for r_idx, row in enumerate(table.rows):
        is_header = (r_idx == 0 and has_header)
        is_alt    = (r_idx % 2 == 0 and not is_header and alt_rows)
        fill      = NAVY if is_header else (ALT if is_alt else WHITE)
        fg        = WHITE if is_header else DKTEXT
        bold      = is_header

        for cell in row.cells:
            _set_cell_borders(cell)
            _pad_cell(cell)
            _shade_cell(cell, fill)
            _style_cell_runs(cell, bold=bold, fg=fg)

            # Vertical alignment centre
            tcPr   = _ensure_child(cell._tc, "w:tcPr")
            vAlign = _ensure_child(tcPr, "w:vAlign")
            vAlign.set(qn("w:val"), "center")


# ══════════════════════════════════════════════════════════════════════════════
# REMOVE MALFORMED RAW XML TABLES
# ══════════════════════════════════════════════════════════════════════════════

def remove_malformed_tables(doc: Document):
    NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = doc.element.body
    removed = 0
    for tbl_el in list(body.findall(f"{{{NS}}}tbl")):
        tblPr   = tbl_el.find(f"{{{NS}}}tblPr")
        tblGrid = tbl_el.find(f"{{{NS}}}tblGrid")
        if tblPr is None or tblGrid is None:
            parent = tbl_el.getparent()
            if parent is not None:
                parent.remove(tbl_el)
                removed += 1
    print(f"  Removed {removed} malformed table(s)")


# ══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE DIAGRAM — Table-based (Word-safe, always opens)
# ══════════════════════════════════════════════════════════════════════════════

def _make_arch_para(doc: Document, text: str, bold=False, sz=Pt(11),
                    center=False, italic=False, fg=None) -> Paragraph:
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after  = Pt(0)
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    run.font.name   = BODY_F
    run.font.size   = sz
    run.bold        = bold
    run.italic      = italic
    if fg:
        run.font.color.rgb = RGBColor.from_string(fg)
    return para


def _cell_write(cell, text: str, bold=False, sz=Pt(10), fg=WHITE,
                fill=NAVY, center=True):
    _shade_cell(cell, fill)
    _pad_cell(cell, top=80, bot=80, left=80, right=80)
    _set_cell_borders(cell)
    tcPr   = _ensure_child(cell._tc, "w:tcPr")
    vAlign = _ensure_child(tcPr, "w:vAlign")
    vAlign.set(qn("w:val"), "center")
    para = cell.paragraphs[0]
    para.clear()
    if center:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, line in enumerate(text.split("\n")):
        if i > 0:
            para.add_run("\n")
        run = para.add_run(line)
        run.font.name = BODY_F
        run.font.size = sz
        run.bold = bold
        run.font.color.rgb = RGBColor.from_string(fg)


def insert_architecture_diagram(doc: Document):
    """
    Replace the architecture placeholder paragraphs with:
      - A section heading
      - A 3-row × 9-column Word table showing the pipeline flow
      - A centred italic caption
    """
    CAPTION_MARKER = "Fig. 2.1"
    cap_idx = None
    for i, para in enumerate(doc.paragraphs):
        if para.text.strip().startswith(CAPTION_MARKER):
            cap_idx = i
            break

    if cap_idx is None:
        print("  [WARN] Architecture caption not found; skipping diagram.")
        return

    # Remove blank lines above caption (up to 3)
    i = cap_idx - 1
    removed = 0
    while i >= 0 and removed < 3 and not doc.paragraphs[i].text.strip():
        el = doc.paragraphs[i]._element
        el.getparent().remove(el)
        cap_idx -= 1
        i -= 1
        removed += 1

    # Replace caption text
    cap_para = doc.paragraphs[cap_idx]
    cap_para.clear()
    cap_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_run = cap_para.add_run(
        "Figure 3.1: High-level architecture of the proposed two-stage grounded "
        "summarisation pipeline."
    )
    cap_run.font.name   = BODY_F
    cap_run.font.size   = Pt(10)
    cap_run.italic      = True
    cap_run.font.color.rgb = RGBColor.from_string("404040")

    # ── Build architecture table (inserted before caption) ────────────────────
    # Layout: 3 rows × 9 cols
    #   Row 0: header label row
    #   Row 1: main stage boxes with arrow separators
    #   Row 2: sub-description row
    #
    # Cols: [IN] [->] [S1] [->] [S2] [->] [S3] [->] [S4] [->] [OUT]  = 11 cols
    #
    # We use 11 columns: stage boxes in cols 0,2,4,6,8,10; arrows in 1,3,5,7,9

    COLS = 11

    table = doc.add_table(rows=3, cols=COLS)
    table.style = "Normal Table"

    # Merge header: first cell spans all cols for title bar
    hdr_row = table.rows[0]
    hdr_row.cells[0].merge(hdr_row.cells[COLS - 1])
    _cell_write(hdr_row.cells[0],
                "Two-Stage Grounded Summarisation Pipeline — Architecture",
                bold=True, sz=Pt(11), fg=WHITE, fill=NAVY)

    # Main row
    main_row = table.rows[1]
    # Input cell (col 0)
    _cell_write(main_row.cells[0],
                "INPUT\nNews\nArticle",
                bold=True, sz=Pt(9), fg=WHITE, fill="375623")
    # Arrow col 1
    _cell_write(main_row.cells[1], "->", bold=True, sz=Pt(11),
                fg=NAVY, fill="F2F2F2")

    stages = [
        ("Stage 1\nEvidence\nRetrieval\n(BM25 + Embed)", NAVY),
        ("Stage 2\nAbstractive\nGeneration\n(BART Best-of-N)", BLUE),
        ("Stage 3\nNLI\nVerification\n(DeBERTa FCS)", BLUE),
        ("Stage 4\nPreference\nReranking\n+ Fallback", NAVY),
    ]
    arrow_cols = [1, 3, 5, 7, 9]
    stage_cols = [2, 4, 6, 8]

    for i, (s_text, s_fill) in enumerate(stages):
        col = stage_cols[i]
        _cell_write(main_row.cells[col], s_text,
                    bold=True, sz=Pt(9), fg=WHITE, fill=s_fill)
        if i < 3:
            arr_col = arrow_cols[i + 1]
            _cell_write(main_row.cells[arr_col], "->",
                        bold=True, sz=Pt(11), fg=NAVY, fill="F2F2F2")

    # Output cell (col 10)
    _cell_write(main_row.cells[10],
                "OUTPUT\nFactual\nSummary",
                bold=True, sz=Pt(9), fg=WHITE, fill="375623")

    # Sub-description row
    sub_row = table.rows[2]
    # Merge the 2 arrow cols and the input/output with neutral colour
    sub_row.cells[0].merge(sub_row.cells[1])
    _cell_write(sub_row.cells[0], "", fill="F2F2F2", fg=NAVY)

    sub_texts = [
        "Hybrid BM25\n+ embedding\nscoring",
        "N-candidate\nnucleus\nsampling",
        "Sentence-level\nentailment\nscore (FCS)",
        "Weighted rank\n+ extractive\nguard",
    ]
    sub_cols  = [2, 4, 6, 8]
    for col, txt in zip(sub_cols, sub_texts):
        _cell_write(sub_row.cells[col], txt,
                    bold=False, sz=Pt(8), fg=DKTEXT, fill=ALT)

    # Merge arrow cols in sub row
    for ac in [3, 5, 7]:
        _cell_write(sub_row.cells[ac], "", fill="F2F2F2", fg=NAVY)

    sub_row.cells[9].merge(sub_row.cells[10])
    _cell_write(sub_row.cells[9], "", fill="F2F2F2", fg=NAVY)

    # Column widths (twips): arrow cols narrow, stage cols wider
    # Total ~9000 twips ≈ 15.8 cm
    col_widths = [900, 300, 1500, 300, 1500, 300, 1500, 300, 1500, 300, 900]
    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            tc   = cell._tc
            tcPr = _ensure_child(tc, "w:tcPr")
            tcW  = _ensure_child(tcPr, "w:tcW")
            tcW.set(qn("w:w"),    str(col_widths[ci]))
            tcW.set(qn("w:type"), "dxa")

    # Row heights
    for r_idx, height_twips in enumerate([400, 900, 600]):
        trPr = _ensure_child(table.rows[r_idx]._tr, "w:trPr")
        trH  = _ensure_child(trPr, "w:trHeight")
        trH.set(qn("w:val"),   str(height_twips))
        trH.set(qn("w:hRule"), "atLeast")

    # Apply outer border
    _set_table_borders(table)

    # Move the table element to be BEFORE the caption paragraph
    cap_el    = cap_para._element
    table_el  = table._tbl
    cap_el.addprevious(table_el)

    # Add a small spacer between table and caption
    spacer = OxmlElement("w:p")
    spPr   = OxmlElement("w:pPr")
    spSz   = OxmlElement("w:spacing")
    spSz.set(qn("w:before"), "60")
    spSz.set(qn("w:after"),  "60")
    spPr.append(spSz)
    spacer.append(spPr)
    cap_el.addprevious(spacer)

    print("  Architecture diagram (table-based) inserted.")


# ══════════════════════════════════════════════════════════════════════════════
# GLOBAL TYPOGRAPHY CLEANUP
# ══════════════════════════════════════════════════════════════════════════════

def cleanup_document(doc: Document):
    for para in doc.paragraphs:
        sname = para.style.name if para.style else ""

        if sname == "Normal":
            para.paragraph_format.space_before = Pt(0)
            para.paragraph_format.space_after  = Pt(6)
            para.paragraph_format.line_spacing  = Pt(14)
            for run in para.runs:
                if not run.font.name or run.font.name in ("Calibri", "Arial"):
                    run.font.name = BODY_F
                if not run.font.size or run.font.size < Pt(10):
                    run.font.size = Pt(11)

        elif "Heading 1" in sname:
            para.paragraph_format.space_before = Pt(18)
            para.paragraph_format.space_after  = Pt(6)
            for run in para.runs:
                run.font.name = HEAD_F
                run.font.size = Pt(14)
                run.bold = True
                run.font.color.rgb = RGBColor.from_string(NAVY)

        elif "Heading 2" in sname:
            para.paragraph_format.space_before = Pt(12)
            para.paragraph_format.space_after  = Pt(4)
            for run in para.runs:
                run.font.name = HEAD_F
                run.font.size = Pt(12)
                run.bold = True
                run.font.color.rgb = RGBColor.from_string(BLUE)

        elif "List Paragraph" in sname:
            para.paragraph_format.space_before = Pt(2)
            para.paragraph_format.space_after  = Pt(2)
            for run in para.runs:
                if not run.font.name or run.font.name in ("Calibri", ""):
                    run.font.name = BODY_F
                run.font.size = Pt(11)


def set_page_margins(doc: Document):
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(2.54)
        section.right_margin  = Cm(2.54)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not SRC_PATH.exists():
        raise FileNotFoundError(f"Source not found: {SRC_PATH}")

    doc = Document(str(SRC_PATH))

    print("Step 1: Removing malformed tables ...")
    remove_malformed_tables(doc)

    print("Step 2: Formatting all valid tables ...")
    for i, table in enumerate(doc.tables):
        try:
            format_table(table)
            print(f"  Table {i:2d} formatted OK")
        except Exception as exc:
            print(f"  Table {i:2d} SKIPPED: {exc}")

    print("Step 3: Inserting architecture diagram ...")
    insert_architecture_diagram(doc)

    print("Step 4: Global typography cleanup ...")
    cleanup_document(doc)

    print("Step 5: Setting page margins ...")
    set_page_margins(doc)

    # Save — try primary path; fall back if locked
    saved_to = None
    for dest in (OUT_PATH, FALL_PATH):
        try:
            doc.save(str(dest))
            saved_to = dest
            break
        except PermissionError:
            print(f"  [WARN] {dest.name} is locked — trying fallback name ...")

    if saved_to is None:
        raise RuntimeError("Could not save to any path — close the file in Word first.")

    size_kb = saved_to.stat().st_size // 1024
    print(f"\nSaved: {saved_to}  ({size_kb} KB)")
    print("Done — report is polished and ready to open in Word.")


if __name__ == "__main__":
    main()
