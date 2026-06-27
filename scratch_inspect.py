"""Extract all content from the ag docx for review."""
from docx import Document
from pathlib import Path

doc = Document("documentation/MidSem_Report_2024AA05606_ag.docx")

print(f"Paragraphs: {len(doc.paragraphs)}, Tables: {len(doc.tables)}\n")

for i, para in enumerate(doc.paragraphs):
    t = para.text.strip()
    if t:
        style = para.style.name if para.style else "Normal"
        print(f"[{style}] {t[:120]}")

print("\n=== TABLES ===")
for ti, table in enumerate(doc.tables):
    print(f"\n-- Table {ti} --")
    for row in table.rows:
        cells = [c.text.strip()[:40] for c in row.cells]
        print("  | " + " | ".join(cells) + " |")
