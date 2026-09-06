"""BDA-backed OCR adapter — drop-in replacement for `strands_ocr`.

Why: Textract's `DetectDocumentText` only emits raw text + bbox, with no
notion of "this label belongs to the V-101 vessel cluster". Bedrock Data
Automation (BDA) Standard Output for documents/images returns the same
text + bbox + confidence triples, but with stronger line grouping and a
single managed call that we can later promote to a custom blueprint.

Contract: this module exposes the same public surface as
`backend.agents.strands_ocr`:

    detect_text_blocks(image_or_path)            -> tuple[TextBlock, ...]
    detect_text_blocks_from_bytes(payload)       -> tuple[TextBlock, ...]
    filter_label_candidates(blocks, max_chars)   -> tuple[TextBlock, ...]

The `TextBlock` dataclass is re-exported from `strands_ocr` so the
existing fusion / line_refinement / orchestrator code does not change.

Configuration (env):
  - PNID_BDA_PROJECT_ARN     : Bedrock Data Automation project ARN
  - PNID_BDA_PROFILE_ARN     : Bedrock Data Automation profile ARN
  - PNID_BDA_INPUT_BUCKET    : S3 bucket for input PNG staging
  - PNID_BDA_OUTPUT_BUCKET   : S3 bucket for BDA result manifests
  - PNID_BDA_POLL_TIMEOUT_S  : max wait (default 90)
  - PNID_BDA_POLL_INTERVAL_S : initial poll interval (default 1.5)
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from pathlib import Path
from typing import Sequence

from PIL import Image

from backend.agents.strands_ocr import (  # re-export for callers
    TextBlock,
    filter_label_candidates,
)
from backend.aws_clients import get_session


def _bda_runtime():
    return get_session().client("bedrock-data-automation-runtime")


def _s3():
    return get_session().client("s3")


def _to_png_bytes(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _stage_input(payload: bytes) -> tuple[str, str]:
    bucket = os.environ["PNID_BDA_INPUT_BUCKET"]
    digest = hashlib.sha256(payload).hexdigest()[:24]
    key = f"input/{digest}.png"
    _s3().put_object(
        Bucket=bucket, Key=key, Body=payload, ContentType="image/png",
    )
    return bucket, key


def _output_prefix(input_key: str) -> tuple[str, str]:
    bucket = os.environ["PNID_BDA_OUTPUT_BUCKET"]
    # Reuse the input digest so successive Runs of the same drawing land
    # in the same prefix (cheap S3 hit if the result manifest is cached).
    return bucket, f"output/{Path(input_key).stem}/"


def _poll_status(invocation_arn: str) -> dict:
    timeout = float(os.getenv("PNID_BDA_POLL_TIMEOUT_S", "90"))
    interval = float(os.getenv("PNID_BDA_POLL_INTERVAL_S", "1.5"))
    deadline = time.monotonic() + timeout
    runtime = _bda_runtime()
    last: dict = {}
    while time.monotonic() < deadline:
        last = runtime.get_data_automation_status(invocationArn=invocation_arn)
        status = last.get("status") or last.get("Status")
        if status in {"Success", "ServiceError", "ClientError"}:
            return last
        time.sleep(interval)
        interval = min(interval * 1.4, 6.0)
    raise TimeoutError(
        f"BDA invocation {invocation_arn} did not finish within {timeout}s"
    )


def _result_uri(status: dict) -> str:
    """Extract the S3 URI of the actual result.json from BDA output.

    BDA's get_data_automation_status returns a pointer to
    `job_metadata.json`, NOT directly to `result.json`. We must:
      1. Read the job_metadata.json
      2. Follow output_metadata[0].segment_metadata[0].standard_output_path
    to get the real Standard Output result.
    """
    cfg = (
        status.get("outputConfiguration")
        or status.get("OutputConfiguration")
        or {}
    )
    meta_uri = cfg.get("s3Uri") or cfg.get("S3Uri")
    if not meta_uri:
        raise RuntimeError(
            f"BDA status missing outputConfiguration.s3Uri: {status!r}"
        )
    # Read job_metadata.json
    meta = _read_s3_json(meta_uri)
    # Navigate to the standard_output_path
    try:
        segments = meta["output_metadata"][0]["segment_metadata"]
        result_path = segments[0]["standard_output_path"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"BDA job_metadata missing standard_output_path: {meta!r}"
        ) from exc
    return result_path


def _read_s3_json(uri: str) -> dict:
    assert uri.startswith("s3://")
    rest = uri[len("s3://"):]
    bucket, _, key = rest.partition("/")
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read())


def _denorm_bbox(
    bb: dict, img_w: int, img_h: int,
) -> tuple[float, float, float, float]:
    """BDA bounding box → pixel (x1,y1,x2,y2). BDA may return either
    {left,top,width,height} (0..1) or {l,t,w,h}; handle both."""
    def _pick(*names: str, default: float = 0.0) -> float:
        for n in names:
            if n in bb:
                return float(bb[n])
        return default
    left = _pick("left", "Left", "l")
    top = _pick("top", "Top", "t")
    width = _pick("width", "Width", "w")
    height = _pick("height", "Height", "h")
    x1 = left * img_w
    y1 = top * img_h
    x2 = (left + width) * img_w
    y2 = (top + height) * img_h
    return (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1))


def _parse_standard_output(
    payload: dict, img_w: int, img_h: int,
) -> tuple[TextBlock, ...]:
    """Parse BDA's Standard Output for image/document modality.

    Confirmed schema (2026-05, us-east-1):
        {
          "metadata": {...},
          "document": {"statistics": {...}},
          "text_lines": [
            {"id": "...", "text": "...", "confidence": 0.0..1.0,
             "locations": [{"page_index": 0,
                            "bounding_box": {"left", "top", "width", "height"}}]}
          ],
          "text_words": [...]
        }

    We use `text_lines` only — line granularity matches what
    `line_refinement` and `strands_fusion` expect from Textract LINE
    blocks. Coordinates are normalised 0..1; we denormalise to pixels.
    """
    blocks: list[TextBlock] = []
    for line in payload.get("text_lines", []) or []:
        text = (line.get("text") or "").strip()
        if not text:
            continue
        locs = line.get("locations") or []
        if not locs:
            continue
        bb = locs[0].get("bounding_box") or locs[0].get("boundingBox")
        if not isinstance(bb, dict):
            continue
        try:
            bbox = _denorm_bbox(bb, img_w, img_h)
        except Exception:  # noqa: BLE001
            continue
        conf = float(line.get("confidence") or 0.0)
        if conf <= 1.0:
            conf *= 100.0
        blocks.append(TextBlock(text=text, confidence=conf, bbox=bbox))
    return tuple(blocks)


def detect_text_blocks(image: Image.Image | Path) -> tuple[TextBlock, ...]:
    """BDA-backed equivalent of `strands_ocr.detect_text_blocks`."""
    if isinstance(image, Path):
        image = Image.open(image)
    img = image.convert("RGB")
    payload = _to_png_bytes(img)
    in_bucket, in_key = _stage_input(payload)
    out_bucket, out_prefix = _output_prefix(in_key)

    runtime = _bda_runtime()
    kwargs = dict(
        inputConfiguration={"s3Uri": f"s3://{in_bucket}/{in_key}"},
        outputConfiguration={"s3Uri": f"s3://{out_bucket}/{out_prefix}"},
        dataAutomationConfiguration={
            "dataAutomationProjectArn": os.environ["PNID_BDA_PROJECT_ARN"],
            "stage": "LIVE",
        },
        dataAutomationProfileArn=os.environ["PNID_BDA_PROFILE_ARN"],
    )
    resp = runtime.invoke_data_automation_async(**kwargs)
    arn = resp.get("invocationArn") or resp.get("InvocationArn")
    if not arn:
        raise RuntimeError(f"BDA invoke returned no invocationArn: {resp!r}")

    status = _poll_status(arn)
    final = status.get("status") or status.get("Status")
    if final != "Success":
        raise RuntimeError(f"BDA invocation {arn} ended in status={final}: {status!r}")

    result_uri = _result_uri(status)
    result = _read_s3_json(result_uri)
    return _parse_standard_output(result, *img.size)


def detect_text_blocks_from_bytes(payload: bytes) -> tuple[TextBlock, ...]:
    img = Image.open(io.BytesIO(payload)).convert("RGB")
    return detect_text_blocks(img)


__all__ = [
    "TextBlock",
    "detect_text_blocks",
    "detect_text_blocks_from_bytes",
    "filter_label_candidates",
]
