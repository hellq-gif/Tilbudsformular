#!/usr/bin/env python3
"""Create permanent transparent product PNGs for the offer generator.

Sources are the product images already configured in index.html. This script
runs in GitHub Actions once, commits static PNGs into /assets, and therefore
does NOT depend on browser-side canvas or copying data: URIs into Outlook.
"""
from pathlib import Path
from PIL import Image
import base64
import io
import re
import urllib.request
import numpy as np
import cv2

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "index.html").read_text(encoding="utf-8")
assets = ROOT / "assets"
assets.mkdir(exist_ok=True)

names = {
    "swan": "swan-transparent.png",
    "simonelli1": "simonelli1-transparent.png",
    "simonelli2": "simonelli2-transparent.png",
    "jura": "jura-transparent.png",
}

def source_for(key):
    # IMG entries in the source are one-line JS string values.
    match = re.search(r'^\s*' + re.escape(key) + r':\s*"([^"\n]+)"', html, re.MULTILINE)
    if not match:
        raise ValueError(f"Image source missing for {key}")
    src = match.group(1)
    if src.startswith("data:image/png;base64,"):
        return base64.b64decode(src.split(",", 1)[1])
    request = urllib.request.Request(src, headers={
        "User-Agent": "Mozilla/5.0 (compatible; BlackbirdCoffeeImageAssets/1.0)",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": src.split("/")[0] + "//" + src.split("/")[2] + "/",
    })
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()


def remove_white_background(image):
    pix = np.array(image.convert("RGBA"), dtype=np.uint8)
    if (pix[:, :, 3] == 0).mean() > 0.10:
        return Image.fromarray(pix, "RGBA")

    rgb = pix[:, :, :3].astype(np.int16)
    bright = rgb.min(axis=2) >= 235
    neutral = (rgb.max(axis=2) - rgb.min(axis=2)) <= 24
    candidate = np.ascontiguousarray((bright & neutral).astype(np.uint8))
    number, labels, *_ = cv2.connectedComponentsWithStats(candidate, 4)

    outside_labels = np.unique(np.concatenate([
        labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]
    ]))
    outside = np.isin(labels, outside_labels)
    alpha = np.where(outside, 0, pix[:, :, 3]).astype(np.uint8)
    pix[:, :, 3] = alpha
    # Clear transparent RGB to eliminate white fringes on dark Outlook.
    pix[outside, :3] = 0
    return Image.fromarray(pix, "RGBA")


for key, filename in names.items():
    src_data = source_for(key)
    im = Image.open(io.BytesIO(src_data)).convert("RGBA")
    im = remove_white_background(im)
    path = assets / filename
    im.save(path, format="PNG", optimize=True)
    alpha = np.asarray(im.getchannel("A"))
    print(f"{key}: {im.size} {path.stat().st_size} bytes; transparent={(alpha == 0).mean():.1%} -> {path}")
    if (alpha == 0).mean() < 0.08:
        raise RuntimeError(f"No transparency created for {key}: {path}")
