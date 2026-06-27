"""Inspect the styles of the restructured document."""
from docx import Document

doc = Document("documentation/MidSem_Report_2024AA05606_restructured.docx")
print("Styles used in paragraphs:")
styles = set([p.style.name for p in doc.paragraphs])
for s in styles:
    print(f"- {s}")
