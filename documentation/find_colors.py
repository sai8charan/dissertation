"""Find dominant colors in the PDF images."""
from PIL import Image
from collections import Counter

def is_colored(c):
    # Ignore if near grayscale (R~G~B)
    if max(c) - min(c) < 20:
        return False
    # Ignore if near white
    if min(c) > 230:
        return False
    # Ignore if near black
    if max(c) < 50:
        return False
    return True

# Page 4 (H2 Blue)
img4 = Image.open('documentation/colored_p4.png')
rgb_img4 = img4.convert('RGB')
colors4 = [rgb_img4.getpixel((x, y)) for x in range(img4.width) for y in range(img4.height)]
colored_pixels4 = [c for c in colors4 if is_colored(c)]
most_common4 = Counter(colored_pixels4).most_common(5)
print("Dominant colors on Page 4 (Headings):")
for color, count in most_common4:
    print(f"#{color[0]:02x}{color[1]:02x}{color[2]:02x} - count: {count}")

# Page 3 (Table Header Light Blue)
img3 = Image.open('documentation/colored_p3.png')
rgb_img3 = img3.convert('RGB')
colors3 = [rgb_img3.getpixel((x, y)) for x in range(img3.width) for y in range(img3.height)]
colored_pixels3 = [c for c in colors3 if is_colored(c)]
most_common3 = Counter(colored_pixels3).most_common(5)
print("\nDominant colors on Page 3 (Tables):")
for color, count in most_common3:
    print(f"#{color[0]:02x}{color[1]:02x}{color[2]:02x} - count: {count}")
