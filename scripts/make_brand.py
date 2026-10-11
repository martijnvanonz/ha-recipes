"""Render the integration icon/logo into custom_components/recipes/brand/.

    .venv/bin/python scripts/make_brand.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "recipes" / "brand"
S = 2048  # draw at 2x and downsample for clean edges

TOP_LEFT = (255, 159, 67)  # warm orange
BOTTOM_RIGHT = (230, 72, 72)  # tomato red
WHITE = (255, 255, 255)
SHADE = (255, 228, 210)


def gradient(size, c1, c2):
    small = Image.new("RGB", (256, 256))
    px = small.load()
    for y in range(256):
        for x in range(256):
            t = (x + y) / 510
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(c1, c2, strict=True))
    return small.resize((size, size), Image.BICUBIC)


def render() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.22), fill=255)
    img.paste(gradient(S, TOP_LEFT, BOTTOM_RIGHT), (0, 0), mask)

    hat = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(hat)
    # Puffy top: three overlapping circles.
    for cx, cy, r in ((0.33, 0.43, 0.17), (0.67, 0.43, 0.17), (0.50, 0.33, 0.21)):
        d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=WHITE)
    # Body and band.
    d.rectangle((0.27 * S, 0.43 * S, 0.73 * S, 0.66 * S), fill=WHITE)
    d.rounded_rectangle((0.25 * S, 0.66 * S, 0.75 * S, 0.78 * S), radius=int(0.03 * S), fill=SHADE)
    # Pleats.
    for x in (0.40, 0.50, 0.60):
        d.rounded_rectangle(((x - 0.008) * S, 0.50 * S, (x + 0.008) * S, 0.64 * S), radius=int(0.008 * S), fill=SHADE)

    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((120, 30, 20, 90), (0, int(0.02 * S)), hat.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(S * 0.02))
    img.alpha_composite(shadow)
    img.alpha_composite(hat)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    big = render()
    for name, size in (("icon.png", 256), ("icon@2x.png", 512), ("logo.png", 256), ("logo@2x.png", 512)):
        big.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
    print("written to", OUT)


if __name__ == "__main__":
    main()
