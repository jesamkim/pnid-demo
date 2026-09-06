"""Image-first normalization for every drawing input.

Why this exists
---------------
The pipeline (Vision agent + Textract + Fusion + canvas overlay) is
pixel-coordinate-precise. If the Vision input PNG and the viewer's
displayed PNG go through *separate* render passes (e.g. one at 200 dpi
from pypdfium2, one at the same dpi but a slightly different scale
factor), the bounding boxes the Vision agent emits land ~1px off the
shapes the user sees. Aligning every consumer onto the *same* PNG
file solves it deterministically.

Contract
--------
`normalize_to_png(source: Path, target_dir: Path | None = None,
                   dpi: int = 200) -> Path`

  - For .pdf inputs: render page 0 at `dpi` and write a PNG.
  - For .png / .jpg / .jpeg / .tif / .tiff inputs: load with PIL,
    convert to RGB, and write a PNG copy.
  - Writes to `<target_dir or source.parent>/<stem>.norm.png` and
    returns the PNG path. Idempotent — re-running is a no-op when
    the PNG is already up-to-date relative to the source mtime.

Both `render_page` and the FastAPI image route delegate here so the
`/api/drawings/{key}/image` bytes and the orchestrator's analysis
input are byte-identical.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from backend.tools.pdf_renderer import render_page


_PDF_SUFFIX = ".pdf"
_RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}

# Bedrock ConverseStream Vision input rejects images whose larger edge
# exceeds 8000 px. We cap at 7800 to leave headroom — the dimensions
# event the orchestrator emits to the frontend uses these *capped*
# values, so bbox overlay coordinates stay aligned with the displayed
# image and the upstream Vision call no longer 4xx's.
MAX_EDGE_PX = 7800


def normalize_to_png(
    source: Path | str,
    *,
    target_dir: Optional[Path] = None,
    dpi: int = 200,
    page: int = 0,
) -> Path:
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"input does not exist: {src}")
    suffix = src.suffix.lower()

    out_dir = target_dir or src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.stem}.norm.png"

    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out  # idempotent — cache valid

    if suffix == _PDF_SUFFIX:
        img = render_page(src, page=page, dpi=dpi)
    elif suffix in _RASTER_SUFFIXES:
        img = Image.open(src).convert("RGB")
    else:
        raise ValueError(
            f"unsupported drawing extension {suffix!r} — "
            "expected pdf / png / jpg / jpeg / tif / tiff"
        )

    img = _cap_edge(img, MAX_EDGE_PX)
    img.save(out, format="PNG", optimize=True)
    return out


def _cap_edge(img: Image.Image, max_edge: int) -> Image.Image:
    """Downscale so neither edge exceeds `max_edge`, preserving aspect.

    Uses LANCZOS for sharp text — ISA labels survive the resample.
    Returns the input unchanged when both edges are already ≤ max_edge.
    """
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_edge:
        return img
    scale = max_edge / float(long_edge)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    return img.resize((new_w, new_h), Image.LANCZOS)


def load_normalized(
    source: Path | str,
    *,
    target_dir: Optional[Path] = None,
    dpi: int = 200,
    page: int = 0,
) -> Image.Image:
    """Convenience: normalize then load the resulting PNG into PIL."""
    png_path = normalize_to_png(
        source, target_dir=target_dir, dpi=dpi, page=page,
    )
    return Image.open(png_path).convert("RGB")
