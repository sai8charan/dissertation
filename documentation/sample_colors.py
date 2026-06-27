"""Sample colors from the PNGs to get the exact blue."""
from PIL import Image
from collections import Counter

# Page 4 has the blue heading. Let's sample a region where we know the text is.
# Heading 2 "1.1 Scope at the Mid-Semester Stage" is around y=360, x=100-300
img4 = Image.open('documentation/colored_p4.png')
rgb_img4 = img4.convert('RGB')
colors4 = []
for x in range(100, 300):
    for y in range(355, 375):
        c = rgb_img4.getpixel((x, y))
        # Ignore near white/gray
        if max(c) - min(c) > 30 and c[2] > c[0]: # Look for blueish
            colors4.append(c)

if colors4:
    most_common = Counter(colors4).most_common(1)[0][0]
    print(f"H2 Blue Color: #{most_common[0]:02x}{most_common[1]:02x}{most_common[2]:02x}")
else:
    print("Could not find blue in the H2 region.")

# Page 3 has the table header.
# "Section" is around y=130, x=100-200. Background fill color is what we want.
img3 = Image.open('documentation/colored_p3.png')
rgb_img3 = img3.convert('RGB')
colors3 = []
for x in range(150, 200):
    for y in range(130, 140):
        c = rgb_img3.getpixel((x, y))
        # Ignore black text
        if min(c) > 50:
            colors3.append(c)

if colors3:
    most_common_bg = Counter(colors3).most_common(1)[0][0]
    print(f"Table Header Fill: #{most_common_bg[0]:02x}{most_common_bg[1]:02x}{most_common_bg[2]:02x}")
else:
    print("Could not find background color in the table header region.")
