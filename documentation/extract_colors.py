"""Extract colors from colored document.pdf."""
import fitz

def extract_colors(pdf_path):
    doc = fitz.open(pdf_path)
    colors = set()
    print("Extracting text and colors from first few pages...")
    for i in range(min(5, doc.page_count)):
        page = doc[i]
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" in b:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text:
                            # Color is typically an integer
                            color_int = s["color"]
                            # Convert integer to hex color
                            color_hex = f"#{color_int:06x}"
                            colors.add((color_hex, s["size"], text[:30]))
                            
    for c, sz, text in sorted(colors, key=lambda x: x[1], reverse=True):
        print(f"Size: {sz:.1f}, Color: {c}, Text: {text}")

extract_colors("documentation/midsemreference/colored document.pdf")
