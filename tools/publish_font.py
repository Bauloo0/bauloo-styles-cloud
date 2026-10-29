"""
Bauloo Styles Cloud - publish fonts: drop whole resource packs on "Publish font.bat".

For every pack it takes only the font pictures (ascii, accented, nonlatin_european, ascii_sga),
draws a preview with some text in that font and publishes it to the "font" collection. The name
comes from the pack's file name. Packs without their own font are skipped.

    python publish_font.py <pack.zip> [<pack.zip> ...]
"""

import io
import os
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stylescloud  # noqa: E402

FONT_FILES = ["ascii.png", "accented.png", "nonlatin_european.png", "ascii_sga.png"]


def clean_name(file_name):
    name = os.path.splitext(os.path.basename(file_name))[0]
    name = re.sub(r"§.", "", name)                      # colour codes
    name = re.sub(r"(?i)[\s_-]*(converted|copy|edit|1\.\d+(\.\d+)?|\d+x)\b", "", name)
    name = re.sub(r"[!#_]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -()")
    return (name or "Font")[:40]


def font_files(z):
    """{file name: bytes} of the pack's own font pictures, wherever its assets folder sits."""
    out = {}
    for n in z.namelist():
        low = n.replace("\\", "/").lower()
        for f in FONT_FILES:
            if low.endswith("assets/minecraft/textures/font/" + f) and f not in out:
                out[f] = z.read(n)
    return out


def glyph_line(ascii_img, text, scale):
    from PIL import Image
    cell = ascii_img.width // 16
    px = ascii_img.load()
    parts = []
    for ch in text:
        c = ord(ch)
        if c == 32:
            parts.append(None)
            continue
        gx, gy = (c % 16) * cell, (c // 16) * cell
        right = 0
        for x in range(cell):
            if any(px[gx + x, gy + y][3] > 0 for y in range(cell)):
                right = x + 1
        g = ascii_img.crop((gx, gy, gx + max(right, 1), gy + cell))
        parts.append(g.resize((max(1, round(g.width * 8 / cell)) * scale, 8 * scale), Image.NEAREST))
    width = sum(4 * scale if p is None else p.width + scale for p in parts)
    line = Image.new("RGBA", (max(1, width), 8 * scale), (0, 0, 0, 0))
    x = 0
    for p in parts:
        if p is None:
            x += 4 * scale
            continue
        line.alpha_composite(p, (x, 0))
        x += p.width + scale
    return line


def preview(ascii_bytes, target):
    from PIL import Image, ImageDraw
    img = Image.open(io.BytesIO(ascii_bytes)).convert("RGBA")
    card = Image.new("RGBA", (256, 256), (24, 18, 34, 255))
    d = ImageDraw.Draw(card)
    d.rectangle((0, 0, 255, 255), outline=(60, 46, 80, 255), width=2)
    for text, scale, y in (("Aa", 8, 34), ("Bauloo", 4, 140), ("Styles 123", 2, 196)):
        line = glyph_line(img, text, scale)
        if line.width > 236:
            line = line.resize((236, max(1, line.height * 236 // line.width)), Image.NEAREST)
        card.alpha_composite(line, ((256 - line.width) // 2, y))
    card.save(target)


def main():
    packs = [a for a in sys.argv[1:] if a.lower().endswith(".zip")]
    if not packs:
        raise SystemExit("Drag one or more resource pack .zip files onto Publish font.bat.")
    done = 0
    for pack in packs:
        try:
            with zipfile.ZipFile(pack) as z:
                files = font_files(z)
        except (zipfile.BadZipFile, OSError):
            print(f"skipped (not a zip): {os.path.basename(pack)}")
            continue
        if "ascii.png" not in files:
            print(f"skipped (no font inside): {os.path.basename(pack)}")
            continue
        name = clean_name(pack)
        tmp = tempfile.mkdtemp(prefix="bauloo-font-")
        cut = os.path.join(tmp, stylescloud.slug(name) + ".zip")
        with zipfile.ZipFile(cut, "w", zipfile.ZIP_DEFLATED) as out:
            out.writestr("pack.mcmeta", '{"pack":{"pack_format":46,"description":"Font: %s (Bauloo Styles)"}}'
                         % name.replace('"', ""))
            for f, data in files.items():
                out.writestr("assets/minecraft/textures/font/" + f, data)
        pic = os.path.join(tmp, "preview.png")
        preview(files["ascii.png"], pic)
        print(f"publishing font: {name}")
        stylescloud.publish(cut, pic, auto=("font", name))
        done += 1
    print()
    print(f"{done} font(s) published.")


if __name__ == "__main__":
    main()
