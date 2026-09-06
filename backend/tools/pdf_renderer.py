"""PDF -> page image rendering (pypdfium2) and tiling for large drawings.

Tile geometry preserves overlap for cross-tile entity reconciliation.
Returns Tile objects with absolute pixel coords on the original page so
extracted bbox can be back-projected.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image


@dataclass(frozen=True)
class Tile:
    page: int
    index: int
    image: Image.Image
    x: int
    y: int
    width: int
    height: int


def render_page(pdf_path: Path | str, page: int = 0, dpi: int = 300) -> Image.Image:
    """Render a single page (0-indexed) of a PDF as a Pillow RGB image."""
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if page >= len(pdf):
            raise IndexError(f"page {page} out of range (PDF has {len(pdf)} pages)")
        scale = dpi / 72.0
        pil = pdf[page].render(scale=scale).to_pil().convert("RGB")
        return pil
    finally:
        pdf.close()


def tile_image(img: Image.Image, tile_size: int = 2048, overlap: int = 256, page: int = 1) -> tuple[Tile, ...]:
    """Slice image into overlapping tiles.

    A drawing smaller than tile_size emits a single tile equal to the image.
    """
    W, H = img.size
    if W <= tile_size and H <= tile_size:
        return (Tile(page=page, index=0, image=img, x=0, y=0, width=W, height=H),)

    step = tile_size - overlap
    out: list[Tile] = []
    idx = 0
    y = 0
    while y < H:
        x = 0
        while x < W:
            x2 = min(x + tile_size, W)
            y2 = min(y + tile_size, H)
            crop = img.crop((x, y, x2, y2))
            out.append(Tile(page=page, index=idx, image=crop,
                            x=x, y=y, width=x2 - x, height=y2 - y))
            idx += 1
            if x2 == W:
                break
            x += step
        if y2 == H:
            break
        y += step
    return tuple(out)
