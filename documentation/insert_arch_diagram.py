"""Insert architecture diagram into the styled document."""
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def _ensure_child(parent, tag):
    el = parent.find(qn(tag))
    if el is None:
        el = OxmlElement(tag)
        parent.append(el)
    return el

def _shade_cell(cell, fill):
    tcPr = _ensure_child(cell._tc, "w:tcPr")
    old  = tcPr.find(qn("w:shd"))
    if old is not None:
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)

def _set_table_borders(table):
    tbl   = table._tbl
    tblPr = _ensure_child(tbl, "w:tblPr")
    old   = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for side in ("top","left","bottom","right","insideH","insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)
    tblW = _ensure_child(tblPr, "w:tblW")
    tblW.set(qn("w:w"),    "0")
    tblW.set(qn("w:type"), "auto")

def _set_col_widths(table, widths_cm):
    """Set individual column widths in centimetres."""
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            if i >= len(widths_cm):
                break
            tc   = cell._tc
            tcPr = _ensure_child(tc, "w:tcPr")
            tcW  = _ensure_child(tcPr, "w:tcW")
            twips = int(widths_cm[i] * 567)   # 1 cm = 567 twips
            tcW.set(qn("w:w"),    str(twips))
            tcW.set(qn("w:type"), "dxa")

def _cell_write(cell, text, bold=False, sz=Pt(12),
                font='Times New Roman', align=WD_ALIGN_PARAGRAPH.LEFT, fill=None):
    if fill:
        _shade_cell(cell, fill)
    tcPr   = _ensure_child(cell._tc, "w:tcPr")
    vAlign = _ensure_child(tcPr, "w:vAlign")
    vAlign.set(qn("w:val"), "center")
    # padding
    tcMar  = _ensure_child(tcPr, "w:tcMar")
    for side, val in (("top",60),("bottom",60),("left",108),("right",108)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        tcMar.append(el)
    para = cell.paragraphs[0]
    para.clear()
    para.alignment = align
    run = para.add_run(text)
    run.font.name = font
    run.font.size = sz
    run.bold = bold

doc = Document("documentation/MidSem_Report_2024AA05606_styled.docx")

# Find the paragraph to insert the table after
target_p = None
for i, p in enumerate(doc.paragraphs):
    if p.text.startswith("Stage 4") and "Fallback" in p.text:
        target_p = p
        break

if target_p is None:
    print("Could not find the target paragraph.")
    exit(1)

# We want to insert the table right after target_p
# python-docx doesn't easily let us insert a table *between* paragraphs natively unless we use the paragraph's xml parent.
# Let's create the table and then move its XML element to be right after target_p._element.

arch_table = doc.add_table(rows=3, cols=11)
_set_table_borders(arch_table)

# Row 0: Title banner
arch_table.rows[0].cells[0].merge(arch_table.rows[0].cells[10])
_cell_write(arch_table.rows[0].cells[0],
            "Two-Stage Grounded Summarisation Pipeline — Architecture",
            bold=True, sz=Pt(10), fill="1F3864",
            align=WD_ALIGN_PARAGRAPH.CENTER)
_shade_cell(arch_table.rows[0].cells[0], "1F3864")
para = arch_table.rows[0].cells[0].paragraphs[0]
for run in para.runs:
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

# Row 1: stage boxes + arrows
stage_labels = [
    ("INPUT\nNews Article",           "375623"),
    ("->",                             "F2F2F2"),
    ("Stage 1\nEvidence\nRetrieval",   "1F3864"),
    ("->",                             "F2F2F2"),
    ("Stage 2\nAbstractive\nGeneration","2E75B6"),
    ("->",                             "F2F2F2"),
    ("Stage 3\nNLI\nVerification",    "2E75B6"),
    ("->",                             "F2F2F2"),
    ("Stage 4\nPreference\nReranking", "1F3864"),
    ("->",                             "F2F2F2"),
    ("OUTPUT\nFactual\nSummary",       "375623"),
]
for ci, (lbl, fill) in enumerate(stage_labels):
    cell = arch_table.rows[1].cells[ci]
    _shade_cell(cell, fill)
    tcPr   = _ensure_child(cell._tc, "w:tcPr")
    vAlign = _ensure_child(tcPr, "w:vAlign")
    vAlign.set(qn("w:val"), "center")
    para = cell.paragraphs[0]
    para.clear()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for j, line in enumerate(lbl.split("\n")):
        if j > 0:
            para.add_run("\n")
        run = para.add_run(line)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(9)
        run.bold = (fill not in ("F2F2F2",))
        run.font.color.rgb = (
            RGBColor(0, 0, 0) if fill == "F2F2F2"
            else RGBColor(0xFF, 0xFF, 0xFF)
        )

# Row 2: sub-descriptions
sub_data = [
    ("", "F2F2F2"),
    ("", "F2F2F2"),
    ("Hybrid BM25\n+ embedding\nscoring", "DCE6F1"),
    ("", "F2F2F2"),
    ("N-candidate\nnucleus\nsampling", "DCE6F1"),
    ("", "F2F2F2"),
    ("Sentence-level\nentailment\nscore (FCS)", "DCE6F1"),
    ("", "F2F2F2"),
    ("Weighted rank\n+ extractive\nguard", "DCE6F1"),
    ("", "F2F2F2"),
    ("", "F2F2F2"),
]
for ci, (lbl, fill) in enumerate(sub_data):
    cell = arch_table.rows[2].cells[ci]
    _shade_cell(cell, fill)
    para = cell.paragraphs[0]
    para.clear()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(lbl)
    run.font.name = 'Times New Roman'
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

# Set column widths
col_widths = [1.6, 0.5, 2.5, 0.5, 2.5, 0.5, 2.5, 0.5, 2.5, 0.5, 1.6]
_set_col_widths(arch_table, col_widths)

# Row heights
for r_idx, h in enumerate([400, 900, 600]):
    trPr = _ensure_child(arch_table.rows[r_idx]._tr, "w:trPr")
    trH  = _ensure_child(trPr, "w:trHeight")
    trH.set(qn("w:val"), str(h))
    trH.set(qn("w:hRule"), "atLeast")

# Create figure caption
fig_cap = doc.add_paragraph()
fig_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
fig_cap.paragraph_format.space_before = Pt(6)
fig_cap.paragraph_format.space_after  = Pt(12)
r = fig_cap.add_run("Figure 1: High-level architecture of the proposed grounded summarisation pipeline.")
r.italic = True
r.font.size = Pt(10)
r.font.name = 'Times New Roman'

# Move the table and caption to right after target_p
# The new table is currently at the end of the document.
# doc._body._body contains all elements.
tbl_el = arch_table._tbl
cap_el = fig_cap._p

target_p._p.addnext(tbl_el)
tbl_el.addnext(cap_el)

out_path = "documentation/MidSem_Report_2024AA05606_styled_with_arch.docx"
doc.save(out_path)
print(f"Saved styled document with architecture diagram to {out_path}")
