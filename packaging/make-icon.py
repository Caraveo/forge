"""Regenerate desktop/forge.ico from docs/icon.png (needs Pillow).

Usage: python packaging/make-icon.py [source.png]
The source is cropped to its visible artwork and centered on a square canvas so
the mark fills small taskbar sizes instead of floating in empty margin.
"""
import shutil
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'icon.png'
ICON = ROOT / 'desktop' / 'forge.ico'

if len(sys.argv) > 1:
    shutil.copyfile(sys.argv[1], SOURCE)
art = Image.open(SOURCE).convert('RGBA')
# Ignore the faint outer glow when finding the artwork bounds.
box = art.getchannel('A').point(lambda a: 255 if a > 40 else 0).getbbox() or (0, 0, *art.size)
art = art.crop(box)
side = round(max(art.size) * 1.04)
square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
square.paste(art, ((side - art.width) // 2, (side - art.height) // 2), art)
sizes = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
square.save(ICON, format='ICO', sizes=sizes)
print(ICON, square.size, 'from', SOURCE)
