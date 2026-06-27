"""Inspect document to find where to insert the architecture diagram."""
from docx import Document

doc = Document("documentation/MidSem_Report_2024AA05606_styled.docx")
for i, p in enumerate(doc.paragraphs):
    style_name = p.style.name if p.style else ""
    if "architecture" in p.text.lower() or "diagram" in p.text.lower() or style_name.startswith("Heading"):
        print(f"[{i}] ({style_name}): {p.text[:80]}")
