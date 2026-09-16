# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

"""Attachment extraction for the mail pipeline.

`parse_eml` keeps bodies only; attachments are out of body policy.
This module walks the raw MIME tree, finds each attachment part
(non-text mime or Content-Disposition: attachment), and extracts
text via the right tool per suffix. Results are a list of
`{filename, mime, status, content_md, reason}` where status is one
of `ok | deferred | unsupported` — every mail produces at least one
record so deferrals are always visible, never silent.

Extractors: pdf (pdftotext), docx/xlsx/ods/odt (office.py, openpyxl),
rtf (pandoc), eml (raw body text), images (metadata only, vision gated
on Qwen-VL :8080), zip (listing), winmail.dat (deferred, no apt root).
"""
import email
import io
import shutil
import subprocess
import zipfile
from email import policy
from pathlib import Path

from .office import office_to_markdown

_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/gif",
                "image/tiff", "image/bmp", "image/webp"}

# Max image dimension (long edge) sent to the vision endpoint. Larger
# images are downscaled in-memory (cv2, no file I/O) — Qwen-VL wastes
# VRAM and time on full-res mail attachments with no accuracy gain.
VISION_MAX_EDGE = 1536


def downscale_image(data: bytes, max_edge: int = VISION_MAX_EDGE) -> bytes:
    """Downscale encoded image bytes so the long edge <= max_edge.

    In-memory via cv2.imdecode/imencode — no file I/O. Already-small
    images and undecodable input pass through unchanged (never fail
    the pipeline on a resize).
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return data
    try:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return data
        h, w = img.shape[:2]
        long_edge = max(h, w)
        if long_edge <= max_edge:
            return data
        scale = max_edge / long_edge
        small = cv2.resize(img, (int(w * scale), int(h * scale)),
                           interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", small,
                               [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            return data
        return buf.tobytes()
    except Exception:  # noqa: BLE001 — resize never kills ingest
        return data


def _extension(filename: str) -> str:
    return Path(filename.lower()).suffix.lstrip(".") or "bin"


def _rtf_to_markdown(data: bytes) -> str:
    bin_ = shutil.which("pandoc")
    if not bin_:
        raise RuntimeError("pandoc not on PATH (apt install pandoc)")
    r = subprocess.run([bin_, "-f", "rtf", "-t", "markdown"],
                        input=data.decode("utf-8", "replace"),
                        capture_output=True, text=True,
                        timeout=300, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"pandoc rtf failed: {r.stderr[:200]}")
    return r.stdout


def _part_bytes(part) -> bytes:
    data = part.get_payload(decode=True)
    if data is None:
        p = part.get_payload()
        if isinstance(p, bytes):
            return p
        data = p.encode("utf-8", "replace") if isinstance(p, str) else b""
    return data


def extract_attachments(raw: bytes) -> list[dict]:
    """Walk raw MIME bytes; return one record per attachment part."""
    msg = email.message_from_bytes(raw, policy=policy.compat32)
    out = []
    walker = msg.walk() if msg.is_multipart() else [msg]
    for part in walker:
        try:
            mime = part.get_content_type()
            if mime.startswith("multipart/"):
                continue
            fname = part.get_filename() or ""
            disposition = (part.get("Content-Disposition") or "").lower()
            is_attachment = "attachment" in disposition
            is_attachment = is_attachment or (
                not mime.startswith("text/")
                and not mime.startswith("multipart/"))
            if not is_attachment:
                continue
            if mime == "application/ms-tnef" or fname.lower() == "winmail.dat":
                out.append({"filename": fname or "winmail.dat", "mime": mime,
                            "status": "deferred", "content_md": None,
                            "reason": "TNEF: no CLI/runtime available"})
                continue
            ext = _extension(fname or f"part-{mime.split('/')[-1]}")
            out.append(_extract_one(part, fname, ext, mime))
            continue
        except Exception as ex:  # noqa: BLE001 — one part never kills the mail
            out.append({"filename": (part.get_filename() or "part"),
                        "mime": mime, "status": "deferred",
                        "content_md": None,
                        "reason": f"part error: {str(ex)[:100]}"})
    return out


def _extract_one(part, fname: str, ext: str, mime: str) -> dict:
    data = _part_bytes(part)
    record = {"filename": fname, "mime": mime, "status": "unsupported",
              "content_md": None, "reason": None}
    md = _extract_by_ext(data, ext, fname)
    if md is None:
        return record
    record["status"] = "ok"
    record["content_md"] = md
    return record


def _extract_by_ext(data: bytes, ext: str, fname: str):
    """Returns md string, or None (meaning unsupported for this ext)."""
    if ext in ("pdf",):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            tf.write(data); path = tf.name
        try:
            from .pdf import pdf_to_text
            return pdf_to_text(path, layout=True)
        finally:
            Path(path).unlink(missing_ok=True)
    if ext in ("docx",):
        return _office_bytes(data, "docx")
    if ext in ("xlsx",):
        return _office_bytes(data, "xlsx")
    if ext in ("odt", "ods"):
        return _office_bytes(data, ext)
    if ext == "rtf":
        return _rtf_to_markdown(data)
    if ext == "eml":
        try:
            msg = email.message_from_bytes(data, policy=policy.compat32)
            subj = msg.get("Subject", "") or ""
            body = ""
            if msg.is_multipart():
                for p in msg.walk():
                    mt = p.get_content_type()
                    if mt in ("text/plain", "text/html"):
                        body = p.get_payload(decode=True) or b""
                        body = body.decode("utf-8", "replace")
                        break
            else:
                body = msg.get_payload(decode=True) or b""
                body = body.decode("utf-8", "replace")
            body = body.strip()
            return f"{subj}\n\n{body}" if subj else body
        except Exception as ex:  # noqa: BLE001 — malformed eml never kills
            return f"eml parse error: {ex}"
    if ext in ("zip",):
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
            return "\n".join(names) if names else "(empty zip)"
        except Exception as ex:  # noqa: BLE001 — corrupt zip deferred
            return f"zip listing error: {ex}"
    if ext in ("png", "jpg", "jpeg", "gif", "tiff", "bmp", "webp"):
        size = len(data)
        small = downscale_image(data)
        if len(small) != size:
            return (f"<image {fname} {size}B -> {len(small)}B downscaled "
                    f"to {VISION_MAX_EDGE}px — vision gated on Qwen-VL :8080>")
        return f"<image {fname} {size}B — vision gated on Qwen-VL :8080>"
    if ext in ("wav", "mp3", "mp4", "mpg", "mpeg"):
        return None
    return None


def _office_bytes(data: bytes, ext: str) -> str:
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tf:
        tf.write(data); path = tf.name
    try:
        return office_to_markdown(path)
    finally:
        Path(path).unlink(missing_ok=True)
