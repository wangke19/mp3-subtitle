#!/usr/bin/env python3
"""Convert all PNG images in imgs/ to JPG format."""

from pathlib import Path
from PIL import Image

imgs_dir = Path(__file__).parent / "imgs"

for png_path in sorted(imgs_dir.glob("*.png")):
    jpg_path = png_path.with_suffix(".jpg")
    with Image.open(png_path) as img:
        rgb_img = img.convert("RGB")
        rgb_img.save(jpg_path, "JPEG", quality=95)
    print(f"{png_path.name} -> {jpg_path.name}")
