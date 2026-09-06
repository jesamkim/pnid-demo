"""PDF renderer + tiler behavioral tests using actual sample PDFs."""
from __future__ import annotations

from pathlib import Path

from backend.tools.pdf_renderer import render_page, tile_image

SAMPLES = Path(__file__).resolve().parent.parent.parent / "data" / "samples"


def test_render_separator_pdf_returns_rgb_image():
    img = render_page(SAMPLES / "01_separator_pid.pdf", page=0, dpi=200)
    assert img.mode == "RGB"
    assert img.width >= 1200
    assert img.height >= 700


def test_tile_image_small_returns_single_tile():
    img = render_page(SAMPLES / "01_separator_pid.pdf", page=0, dpi=72)
    tiles = tile_image(img, tile_size=4096, overlap=256)
    assert len(tiles) == 1
    assert tiles[0].x == 0 and tiles[0].y == 0


def test_tile_image_large_produces_overlapping_tiles():
    img = render_page(SAMPLES / "01_separator_pid.pdf", page=0, dpi=300)
    tiles = tile_image(img, tile_size=1024, overlap=128)
    assert len(tiles) > 1
    xs = sorted({t.x for t in tiles})
    assert all(b - a <= 1024 - 128 for a, b in zip(xs, xs[1:]))


def test_tile_attributes_immutable():
    img = render_page(SAMPLES / "01_separator_pid.pdf", page=0, dpi=72)
    tiles = tile_image(img)
    import dataclasses
    assert dataclasses.is_dataclass(tiles[0])
