"""Apply PDF colors to headings and tables."""
from docx import Document
from docx.shared import RGBColor
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

doc = Document("documentation/MidSem_Report_2024AA05606_styled_with_arch.docx")

# Colors
HEADING_BLUE = RGBColor(0x1F, 0x4D, 0x79)
TABLE_HEADER_FILL = "D8E9F6"

# Apply to Document Styles (if they exist)
for style_name in ['Heading 2', 'Heading 3']:
    try:
        style = doc.styles[style_name]
        style.font.color.rgb = HEADING_BLUE
    except KeyError:
        pass

# Apply directly to Paragraphs
for p in doc.paragraphs:
    if p.style is None:
        continue
    style_name = p.style.name
    
    if style_name in ['Heading 2', 'Heading 3']:
        for r in p.runs:
            r.font.color.rgb = HEADING_BLUE

# Apply to Table Headers
# The Architecture diagram table has a specific styling that we probably shouldn't mess up completely.
# But let's check. The architecture diagram has 3 rows. The first row is merged across all 11 columns.
# We'll apply the light blue fill ONLY to the first row of tables where the first row has the same number of cells as the second row (i.e. standard tables).
for table in doc.tables:
    if len(table.rows) > 1:
        # Check if first row is merged like the architecture diagram
        if len(table.rows[0].cells) == len(table.rows[1].cells) and table.rows[0].cells[0] != table.rows[0].cells[-1]:
            # Standard table header
            for cell in table.rows[0].cells:
                _shade_cell(cell, TABLE_HEADER_FILL)

out_path = "documentation/MidSem_Report_2024AA05606_final_colored.docx"
doc.save(out_path)
print(f"Saved colored document to {out_path}")
