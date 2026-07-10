#!/usr/bin/env python3
"""In-place brand PNG title updates — unified external naming."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "figures" / "brand"
FONT_DIR = Path(r"C:\Windows\Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def vgradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        row = (
            int(top[0] * (1 - t) + bottom[0] * t),
            int(top[1] * (1 - t) + bottom[1] * t),
            int(top[2] * (1 - t) + bottom[2] * t),
        )
        for x in range(w):
            px[x, y] = row
    return img


def text_height(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[3] - bbox[1]


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0]


def draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    canvas_w: int,
) -> None:
    tw = text_width(draw, text, fnt)
    x = (canvas_w - tw) // 2
    draw.text((x, y), text, font=fnt, fill=fill)


def restore_tail(im: Image.Image, orig: Image.Image, split_y: int) -> Image.Image:
    """Keep everything below split_y from the original."""
    w, h = orig.size
    out = im.copy()
    tail = orig.crop((0, split_y, w, h))
    out.paste(tail, (0, split_y))
    return out


def update_poster_zh(path: Path, orig: Image.Image) -> None:
    w, h = orig.size
    split = 168
    header = vgradient((w, split), (25, 41, 67), (30, 72, 92)).convert("RGBA")
    im = orig.copy()
    im.paste(header, (0, 0))
    im = restore_tail(im, orig, split)
    draw = ImageDraw.Draw(im)
    line1 = "NovaPanda：智能开放交割协议"
    line2 = "（Intelligent Open Delivery Protocol）"
    fnt1 = font("msyhbd.ttc", 58)
    fnt2 = font("msyhbd.ttc", 38)
    h1, h2 = text_height(draw, line1, fnt1), text_height(draw, line2, fnt2)
    gap = 10
    block = h1 + gap + h2
    y0 = (split - block) // 2 + 8
    draw_centered(draw, line1, y0, fnt1, (255, 255, 255), w)
    draw_centered(draw, line2, y0 + h1 + gap, fnt2, (255, 255, 255), w)
    im.save(path, optimize=True)


def update_poster_en(path: Path, orig: Image.Image) -> None:
    w, h = orig.size
    split = 205
    im = orig.copy()
    im.paste(Image.new("RGB", (w, split), (241, 245, 252)), (0, 0))
    im = restore_tail(im, orig, split)
    draw = ImageDraw.Draw(im)
    title = "NovaPanda | Intelligent Open Delivery Protocol"
    fnt = font("arialbd.ttf", 80)
    th = text_height(draw, title, fnt)
    draw_centered(draw, title, (split - th) // 2 - 4, fnt, (16, 24, 32), w)
    im.save(path, optimize=True)


def update_overview_zh(path: Path, orig: Image.Image) -> None:
    w, h = orig.size
    split = 178
    im = orig.copy()
    im.paste(Image.new("RGB", (w, split), (255, 255, 255)), (0, 0))
    im = restore_tail(im, orig, split)
    draw = ImageDraw.Draw(im)
    title = "NovaPanda：智能开放交割协议"
    fnt = font("msyhbd.ttc", 68)
    draw.text((72, 52), title, font=fnt, fill=(20, 20, 20))
    im.save(path, optimize=True)


def update_overview_en(path: Path, orig: Image.Image) -> None:
    w, h = orig.size
    split = 312
    im = orig.copy()
    im.paste(Image.new("RGB", (w, split), (245, 246, 247)), (0, 0))
    im = restore_tail(im, orig, split)
    draw = ImageDraw.Draw(im)
    title = "NovaPanda: Intelligent Open Delivery Protocol"
    fnt = font("arialbd.ttf", 66)
    draw.text((44, 72), title, font=fnt, fill=(18, 18, 18))
    im.save(path, optimize=True)


def main() -> None:
    jobs = [
        ("novapanda-intelligent-open-delivery-protocol-poster-zh.png", update_poster_zh),
        ("novapanda-intelligent-open-delivery-protocol-poster-en.png", update_poster_en),
        ("novapanda-intelligent-open-delivery-protocol-overview-zh.png", update_overview_zh),
        ("novapanda-intelligent-open-delivery-protocol-overview-en.png", update_overview_en),
    ]
    backup = BRAND / "_originals"
    backup.mkdir(exist_ok=True)
    for name, fn in jobs:
        path = BRAND / name
        bak = backup / name
        if not bak.exists():
            Image.open(path).save(bak)
        orig = Image.open(bak).convert("RGBA")
        fn(path, orig)
        print(f"updated: {name}")


if __name__ == "__main__":
    main()
