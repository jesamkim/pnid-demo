"""Ephemeral upload registry — backs the audience-driven Run Live flow.

When a user POSTs a PDF or image to `/api/uploads`, the file is saved
under `/tmp/uploads/<uuid>.<ext>` and an entry is registered here so
later WebSocket calls can resolve the temporary `upl-<uuid>` drawing
key. Entries TTL after 30 minutes; the disk file is removed when
the entry expires or when `discard()` is called explicitly.

Validation lives here too:
- accepted MIME via `magic bytes` (no trust of Content-Type header)
- size cap from `MAX_BYTES`

The class is process-local; ECS task restart drops everything, which
matches the "transient, single-session" intent of the upload flow.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

UPLOAD_DIR = Path("/tmp/pnid_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
TTL_SECONDS = 30 * 60         # 30 minutes

# (extension, magic-byte prefix) — keep this list short and explicit.
ALLOWED: tuple[tuple[str, bytes], ...] = (
    ("pdf", b"%PDF"),
    ("png", b"\x89PNG\r\n\x1a\n"),
    ("jpg", b"\xff\xd8\xff"),
    ("tif", b"II*\x00"),
    ("tif", b"MM\x00*"),
)


@dataclass(frozen=True)
class UploadEntry:
    drawing_id: str
    path: Path
    ext: str
    expires_at: float


class UnsupportedUploadType(ValueError):
    """Raised when the uploaded bytes don't match any allowed magic header."""


class UploadTooLarge(ValueError):
    """Raised when the uploaded payload exceeds MAX_BYTES."""


class UploadRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, UploadEntry] = {}

    def _detect_ext(self, head: bytes) -> Optional[str]:
        for ext, sig in ALLOWED:
            if head.startswith(sig):
                return ext
        return None

    def register(self, payload: bytes) -> UploadEntry:
        if len(payload) > MAX_BYTES:
            raise UploadTooLarge(f"payload exceeds {MAX_BYTES} bytes")
        ext = self._detect_ext(payload[:16])
        if not ext:
            raise UnsupportedUploadType(
                "file is not a recognised PDF/PNG/JPG/TIFF"
            )
        drawing_id = "upl-" + secrets.token_hex(6)
        path = UPLOAD_DIR / f"{drawing_id}.{ext}"
        path.write_bytes(payload)
        entry = UploadEntry(
            drawing_id=drawing_id,
            path=path,
            ext=ext,
            expires_at=time.time() + TTL_SECONDS,
        )
        with self._lock:
            self._entries[drawing_id] = entry
        return entry

    def get(self, drawing_id: str) -> Optional[UploadEntry]:
        self.gc()
        with self._lock:
            return self._entries.get(drawing_id)

    def discard(self, drawing_id: str) -> None:
        with self._lock:
            entry = self._entries.pop(drawing_id, None)
        if entry and entry.path.exists():
            try:
                entry.path.unlink()
            except OSError:
                pass

    def gc(self) -> None:
        """Remove expired entries + their backing files."""
        now = time.time()
        with self._lock:
            stale = [k for k, v in self._entries.items() if v.expires_at <= now]
            for k in stale:
                entry = self._entries.pop(k)
                if entry.path.exists():
                    try:
                        entry.path.unlink()
                    except OSError:
                        pass


_REGISTRY: Optional[UploadRegistry] = None


def get_registry() -> UploadRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = UploadRegistry()
    return _REGISTRY


def _reset_for_test() -> None:
    global _REGISTRY
    _REGISTRY = None
