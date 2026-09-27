"""Generate responsive AVIF/WebP (+ one fallback) derivatives for images referenced by the site.

Originals under docs/assets/ are never modified or deleted. Output goes to
docs/assets/optimized/ and a manifest is written to tools/image-manifest.json.

Usage:  python tools/optimize_images.py [--force]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
OUT = ASSETS / "optimized"
MANIFEST = ROOT / "tools" / "image-manifest.json"

PHOTO_WIDTHS = [640, 1024, 1600, 2400]
PRODUCT_WIDTHS = [480, 800, 1200, 1600]

# source path (relative to docs/assets) -> (kind, widths, fallback width)
SOURCES: dict[str, tuple[str, list[int], int]] = {
    "factory/20260318184938_644_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184941_649_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184942_650_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184939_645_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184931_635_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184941_648_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/20260318184930_634_41.jpg": ("photo", PHOTO_WIDTHS, 1600),
    "factory/R5_L6212.png": ("product", PRODUCT_WIDTHS, 1200),
    "factory/R5_L6178.png": ("product", PRODUCT_WIDTHS, 1200),
    "factory/R5_L6223.png": ("product", PRODUCT_WIDTHS, 1200),
    "factory/R5_L6200.png": ("product", PRODUCT_WIDTHS, 1200),
    "factory/R5_L6220.png": ("product", PRODUCT_WIDTHS, 1200),
    "slide-view/R5_L6213.png": ("product", PRODUCT_WIDTHS, 1200),
    "slide-view/R5_L6202.png": ("product", PRODUCT_WIDTHS, 1200),
    "slide-view/R5_L6226.png": ("product", PRODUCT_WIDTHS, 1200),
    "slide-view/R5_L6187.png": ("product", PRODUCT_WIDTHS, 1200),
    "tomography/R5_L6234_trimmed.png": ("product", [480, 960, 1472], 1472),
    "factory/20260325065243_32_99_transparent.png": ("product", [544], 544),
}


def resized(img: Image.Image, width: int) -> Image.Image:
    if width >= img.width:
        return img.copy()
    height = round(img.height * width / img.width)
    return img.resize((width, height), Image.LANCZOS)


def main() -> int:
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    for rel, (kind, widths, fallback_width) in SOURCES.items():
        src = ASSETS / rel
        stem = src.stem
        with Image.open(src) as original:
            original.load()
            has_alpha = original.mode in ("RGBA", "LA", "P")
            base = original.convert("RGBA" if has_alpha else "RGB")

        widths = sorted({min(w, base.width) for w in widths})
        entry = {"source": rel, "kind": kind, "alpha": has_alpha,
                 "width": base.width, "height": base.height,
                 "source_bytes": src.stat().st_size, "variants": []}

        for w in widths:
            img = resized(base, w)
            targets = {
                "avif": dict(quality=60 if kind == "product" else 52, speed=6),
                "webp": dict(quality=82 if kind == "product" else 78, method=6),
            }
            for ext, opts in targets.items():
                dest = OUT / f"{stem}-{w}.{ext}"
                if force or not dest.exists():
                    img.save(dest, ext.upper(), **opts)
                entry["variants"].append({"file": dest.name, "width": img.width, "height": img.height,
                                          "bytes": dest.stat().st_size})
            if w == min(fallback_width, base.width):
                ext = "png" if has_alpha else "jpg"
                dest = OUT / f"{stem}-{w}.{ext}"
                if force or not dest.exists():
                    if has_alpha:
                        img.save(dest, "PNG", optimize=True)
                    else:
                        img.save(dest, "JPEG", quality=80, optimize=True, progressive=True)
                entry["fallback"] = {"file": dest.name, "width": img.width, "height": img.height,
                                     "bytes": dest.stat().st_size}
            print(f"{rel} -> {w}w", flush=True)

        manifest[rel] = entry

    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
