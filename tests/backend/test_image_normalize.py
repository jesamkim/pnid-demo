"""Image-first normalisation invariants."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from backend.tools.image_normalize import (
    load_normalized,
    normalize_to_png,
)


def _write_pdf(tmp_path: Path, name: str = "x.pdf") -> Path:
    """Write a minimal one-page PDF via PIL → pypdfium2 won't be needed
    for the input, but the output PNG conversion will exercise the
    raster branch."""
    img = Image.new("RGB", (100, 80), (220, 220, 220))
    p = tmp_path / name
    img.save(p, format="PDF")
    return p


def test_png_passthrough_writes_norm_copy(tmp_path: Path):
    src = tmp_path / "drawing.png"
    Image.new("RGB", (40, 30), (255, 0, 0)).save(src)
    out = normalize_to_png(src)
    assert out.name == "drawing.norm.png"
    assert out.exists()
    # round-trip preserves dimensions
    assert Image.open(out).size == (40, 30)


def test_jpg_input_is_converted_to_png(tmp_path: Path):
    src = tmp_path / "drawing.jpg"
    Image.new("RGB", (60, 50), (0, 128, 0)).save(src, format="JPEG")
    out = normalize_to_png(src)
    assert out.suffix == ".png"
    assert Image.open(out).size == (60, 50)


def test_pdf_input_renders_to_png(tmp_path: Path):
    src = _write_pdf(tmp_path)
    out = normalize_to_png(src, dpi=72)
    assert out.suffix == ".png"
    img = Image.open(out)
    # PDF was 100x80 logical points at 72dpi → ~100x80 px at scale 1.0
    assert img.size[0] >= 80 and img.size[1] >= 60


def test_idempotent_when_cache_fresh(tmp_path: Path):
    src = tmp_path / "x.png"
    Image.new("RGB", (10, 10)).save(src)
    a = normalize_to_png(src)
    mtime_a = a.stat().st_mtime
    b = normalize_to_png(src)
    assert a == b
    assert b.stat().st_mtime == mtime_a  # not re-written


def test_unsupported_extension_raises(tmp_path: Path):
    bad = tmp_path / "x.dwg"
    bad.write_bytes(b"\x00")
    with pytest.raises(ValueError, match="unsupported"):
        normalize_to_png(bad)


def test_oversize_image_is_capped_to_7800px(tmp_path: Path):
    """Bedrock Vision rejects > 8000 px on either edge."""
    src = tmp_path / "huge.png"
    Image.new("RGB", (10000, 3800), (200, 200, 200)).save(src)
    out = normalize_to_png(src)
    img = Image.open(out)
    assert max(img.size) <= 7800
    # Aspect ratio preserved (within 1 px rounding)
    expected_h = round(3800 * 7800 / 10000)
    assert abs(img.size[1] - expected_h) <= 2
    assert img.size[0] == 7800


def test_within_size_image_is_not_resized(tmp_path: Path):
    src = tmp_path / "ok.png"
    Image.new("RGB", (3000, 2000)).save(src)
    out = normalize_to_png(src)
    assert Image.open(out).size == (3000, 2000)


def test_load_normalized_returns_pil_rgb(tmp_path: Path):
    src = tmp_path / "x.png"
    Image.new("RGB", (12, 12), (1, 2, 3)).save(src)
    img = load_normalized(src)
    assert img.mode == "RGB"
    assert img.size == (12, 12)
