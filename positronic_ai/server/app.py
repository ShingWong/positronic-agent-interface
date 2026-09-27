# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================
"""PAI HTTP server — FastAPI wrapper around existing ops.

Exposes PAI verbs as REST endpoints. No new logic — pure transport.
Config via env vars:
  POSITRONIC_PROJECT_DIR — project dir (default: CWD)
  POSITRONIC_SERVER_HOST — bind host (default: 0.0.0.0)
  POSITRONIC_SERVER_PORT — bind port (default: 8080)
"""
import logging
import os
import re

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_DIR = os.environ.get("POSITRONIC_PROJECT_DIR", os.getcwd())
SERVER_HOST = os.environ.get("POSITRONIC_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("POSITRONIC_SERVER_PORT", "8080"))

log = logging.getLogger(__name__)

# Ingest attachment limits. The input caps bound decode cost; the text cap
# bounds what actually reaches body_text, FTS and the embedding payload.
MAX_ATTACHMENTS = 3
MAX_ATTACH_BYTES = 8 * 1024 * 1024
MAX_ATTACH_ENCODED_CHARS = 12 * 1024 * 1024     # ~9 MiB once base64-decoded
MAX_ATTACH_TEXT_CHARS = 50_000                  # total extracted text per mail

_FILENAME_STRIP = re.compile(r"[\x00-\x1f\x7f\[\]]+")


def _safe_filename(name) -> str:
    """Reduce an attachment filename to a bare, inert, bounded name.

    The name comes from the request body and is interpolated into the stored
    message text, so a name carrying newlines or brackets could forge body
    content. Basename only, no control characters or brackets, capped.
    """
    base = os.path.basename((name or "").strip().replace("\\", "/"))
    base = _FILENAME_STRIP.sub("_", base).strip(" ._")
    return base[:120] or "attachment"


def sanitize_brain(name) -> str | None:
    """Sanitize a client-supplied brain name to a safe directory slug.

    Lowercase, non-alphanumerics → underscore, max 40 chars.
    Returns None for empty/invalid input (caller falls back to default).
    """
    if not name:
        return None
    slug = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:40]
    return slug or None


# Brain isolation: the mail instance serves exactly one brain, named by
# POSITRONIC_MAIL_BRAIN. When set, every endpoint is pinned to it —
# client-supplied brain names are ignored, so mail brains can never
# cross into each other or into session brains like kairos.
#
# A value that is present but sanitizes to nothing ("---", "???", whitespace)
# is a misconfiguration, not an absent pin. Falling back to the unpinned
# federated path there would silently open every read endpoint across all
# brains, so we remember that the operator asked for isolation and refuse
# instead.
MAIL_BRAIN_RAW = os.environ.get("POSITRONIC_MAIL_BRAIN")
MAIL_BRAIN = sanitize_brain(MAIL_BRAIN_RAW)
MAIL_BRAIN_MISCONFIGURED = bool(MAIL_BRAIN_RAW) and not MAIL_BRAIN
if MAIL_BRAIN_MISCONFIGURED:
    log.error("POSITRONIC_MAIL_BRAIN=%r has no usable brain name; read "
              "endpoints are refusing service rather than fanning out across "
              "every configured brain", MAIL_BRAIN_RAW)


def isolation_guard() -> dict | None:
    """The refusal payload when the pin is set but unusable, else None."""
    return isolation_refusal() if MAIL_BRAIN_MISCONFIGURED else None


def isolation_refusal() -> dict:
    """Fail-closed response for a misconfigured isolation pin."""
    return {"error": "mail brain misconfigured",
            "detail": "POSITRONIC_MAIL_BRAIN is set but is not a usable "
                      "brain name; refusing to read across brains",
            "object": None, "sightings": [], "found": False}


def resolve_brain(req_brain) -> str | None:
    """Pin to MAIL_BRAIN when set; else sanitize the client value."""
    if MAIL_BRAIN:
        ensure_brain(MAIL_BRAIN)
        return MAIL_BRAIN
    brain = sanitize_brain(req_brain)
    if brain:
        ensure_brain(brain)
    return brain


def ensure_brain(name: str) -> str:
    """Provision a per-user brain on first use (balanced/lexical)."""
    import pathlib
    db = pathlib.Path(PROJECT_DIR) / ".positronic" / "brains" / name / "memory.db"
    if not db.exists():
        from positronic_ai.brains import init_brain
        init_brain(PROJECT_DIR, name, "balanced", "lexical")
    return name


class IngestMailRequest(BaseModel):
    subject: str = ""
    body: str = ""
    sender: str = ""
    date: str = ""
    messageId: str = ""
    brain: str | None = None
    attachments: list[dict] = []
    isHtml: bool = False


class TagRequest(BaseModel):
    brain: str | None = None
    episode_id: str | None = None
    message_id: str | None = None
    tag: str = ""


class AttachRequest(BaseModel):
    brain: str | None = None
    message_id: str = ""
    filename: str = ""
    content_b64: str = ""


class RecallRequest(BaseModel):
    text: str = ""
    k: int = 8
    brains: list[str] | None = None
    consolidation: str | None = None
    context_window: int = 0
    threat: str | None = None
    exhaustive: bool = False


class QueryRequest(BaseModel):
    brain: str | None = None
    text: str | None = None
    sql: str | None = None
    cue: str | None = None
    objects: bool = False
    anchors: bool = False
    sightings: bool = False
    k: int = 8
    consolidation: str | None = None
    context_window: int = 0


class AskRequest(BaseModel):
    object_name: str


class BrainTestRequest(BaseModel):
    brain: str | None = None
    k: int = 3


app = FastAPI(title="Positronic AI Server",
              description="PAI verbs as REST endpoints",
              version="0.1.0")

app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "project_dir": PROJECT_DIR}


@app.post("/ingest")
def ingest(req: IngestMailRequest):
    from positronic_ai.ops.ingest import run as _run
    brain = resolve_brain(req.brain)
    # Replays must not pay for extraction: this probe is a cheap indexed
    # lookup, while the extractors below can each run for minutes.
    if req.messageId:
        from positronic_ai.ops.ingest import find_duplicate
        dup = find_duplicate(PROJECT_DIR, req.messageId, brain=brain,
                             kind="message")
        if dup is not None:
            dup["brain"] = brain
            dup["body_chars"] = len((req.body or "").strip())
            dup["body_convert"] = "duplicate"
            return dup
    # Store the body honestly — empty stays empty so the client can warn.
    # The op falls back to subject only for the subject_norm label.
    text = (req.body or "").strip()
    body_convert = "plain"
    if req.isHtml and text:
        try:
            from positronic_ai.extract.html import html_to_markdown
            text = html_to_markdown(text).strip()
            body_convert = "pandoc-plain"
        except Exception:  # noqa: BLE001  (fallback must never fail ingest)
            import re as _re
            text = _re.sub(r"<[^>]*>", " ", text).strip()
            body_convert = "regex-fallback"
    # Attachments: extract text server-side (pdf/office via pandoc),
    # append under filename headers. Never fails the ingest.
    # Caps are on the *output* as well as the input: a zip lists one line per
    # member, so extracted text can dwarf the input it came from, and all of it
    # lands in body_text -> FTS -> embedding.
    attach_text, attach_names = "", []
    raw_atts: list = []  # (filename, bytes) for S3 WORM archive
    budget = MAX_ATTACH_TEXT_CHARS
    for att in (req.attachments or [])[:MAX_ATTACHMENTS]:
        try:
            import base64 as _b64

            from positronic_ai.extract.attach import _extract_by_ext, _extension
            raw = att.get("data") or ""
            # Reject on the *encoded* length: decoding first would materialise
            # an arbitrarily large buffer just to measure it.
            if len(raw) > MAX_ATTACH_ENCODED_CHARS:
                continue
            try:
                data = _b64.b64decode(raw, validate=False)
                # Heuristic: genuine base64 of binary decodes to non-text.
                if len(data) < len(raw) // 2:
                    raise ValueError("short decode — treat as text")
            except Exception:  # noqa: BLE001 — fall back to raw text bytes
                data = raw.encode("utf-8", "replace")
            if len(data) > MAX_ATTACH_BYTES:
                continue
            # The filename is attacker-controlled and is about to be written
            # into the stored body, so reduce it to a bare, inert name first:
            # newlines would otherwise forge message content.
            fname = _safe_filename(att.get("filename"))
            raw_atts.append((fname, data))
            md = _extract_by_ext(data, _extension(fname), fname)
            if md and md.strip() and budget > 0:
                md = md.strip()
                if len(md) > budget:
                    md = md[:budget].rstrip() + "\n[truncated]"
                budget -= len(md)
                attach_names.append(fname)
                attach_text += f"\n\n[Attachment: {fname}]\n{md}"
        except Exception:  # noqa: BLE001 — one bad part never kills mail
            continue
    if attach_text:
        text = (text + "\n" + attach_text.strip()).strip()
        body_convert += "+attach"
    out = _run(PROJECT_DIR, text, brain=brain, kind="message",
               subject=req.subject or None,
               sender=req.sender or None,
               date=req.date or None,
               message_id=req.messageId or None,
               role="assistant",
               # Only the names whose text actually made it in: the raw
               # request list is attacker-controlled in count and length.
               attachment_names=attach_names[:MAX_ATTACHMENTS])
    out["brain"] = brain
    out["body_chars"] = len(text)
    out["body_convert"] = body_convert
    if attach_text:
        out["attachments_extracted"] = attach_names
        out["attach_chars"] = len(attach_text)
    # S3 WORM archive: immutable copy of mail + raw attachments.
    # Never fails the ingest; duplicates and live=false skip (nothing new).
    if not out.get("duplicate") and out.get("reason") != "live=false":
        try:
            from positronic_ai.archive import archive_mail
            out["archive"] = archive_mail(
                brain=brain, message_id=req.messageId or "",
                sender=req.sender or "", subject=req.subject or "",
                date=req.date or "", body=text,
                episode_id=str(out.get("episode_id") or ""),
                tau=out.get("tau"), attachments=raw_atts)
        except Exception as ex:  # noqa: BLE001 — archive down: brain still has it
            out["archive"] = {"archived": False, "error": str(ex)[:200]}
    return out


@app.post("/tag")
def tag(req: TagRequest):
    from positronic_ai.ops.tag import run as _run
    brain = resolve_brain(req.brain)
    return _run(PROJECT_DIR, brain=brain, episode_id=req.episode_id,
                message_id=req.message_id, tag=req.tag)


@app.post("/attach-text")
def attach_text(req: AttachRequest):
    from positronic_ai.ops.attach import run as _run
    brain = resolve_brain(req.brain)
    return _run(PROJECT_DIR, brain=brain, message_id=req.message_id,
                filename=req.filename, content_b64=req.content_b64)


@app.post("/recall")
def recall(req: RecallRequest):
    from positronic_ai.ops.recall import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    brains = [MAIL_BRAIN] if MAIL_BRAIN else req.brains
    return _run(PROJECT_DIR, req.text, k=req.k, brains=brains,
                consolidation=req.consolidation,
                context_window=req.context_window, threat=req.threat,
                exhaustive=req.exhaustive)


@app.post("/query")
def query(req: QueryRequest):
    from positronic_ai.ops.query import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    brain = MAIL_BRAIN or req.brain
    return _run(PROJECT_DIR, brain=brain, text=req.text, sql=req.sql,
                cue=req.cue, objects=req.objects, anchors=req.anchors,
                sightings=req.sightings, k=req.k,
                consolidation=req.consolidation,
                context_window=req.context_window)


@app.post("/ask")
def ask(req: AskRequest):
    from positronic_ai.ops.ask import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    if MAIL_BRAIN:
        return _run(PROJECT_DIR, req.object_name, brains=[MAIL_BRAIN])
    return _run(PROJECT_DIR, req.object_name)


@app.post("/brain-test")
def brain_test(req: BrainTestRequest):
    from positronic_ai.ops.brain_test import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    return _run(PROJECT_DIR, brain=MAIL_BRAIN or req.brain, k=req.k)


@app.get("/info")
def info():
    from positronic_ai.ops.info import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    out = _run(PROJECT_DIR)
    if MAIL_BRAIN:
        # Pinned instance: disclose only the served brain.
        brains = out.get("brains") or {}
        if MAIL_BRAIN in brains:
            out["brains"] = {MAIL_BRAIN: brains[MAIL_BRAIN]}
    return out


@app.get("/stats")
def stats():
    from positronic_ai.ops.stats import run as _run
    if (refused := isolation_guard()) is not None:
        return refused
    if MAIL_BRAIN:
        return _run(PROJECT_DIR, brain=MAIL_BRAIN)
    return _run(PROJECT_DIR)


@app.get("/vitals")
def vitals():
    """Dashboard vitals: message count, db size, vision fires, threat
    breakdown, archive space. One call feeds the Thunderbird dashboard."""
    import contextlib
    import shutil
    import sqlite3
    from pathlib import Path

    from positronic_ai.ops.stats import run as _stats
    brain = MAIL_BRAIN
    out: dict = {"brain": brain, "episodes": 0, "db_mb": 0.0,
                 "vision_fires": 0, "threats": {}, "archive": {}}
    if not brain:
        return out
    db = Path(PROJECT_DIR) / ".positronic" / "brains" / brain / "memory.db"
    with contextlib.suppress(Exception):  # vitals never fail the dashboard
        if db.exists():
            out["db_mb"] = round(db.stat().st_size / 1048576, 1)
            c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                uuid_row = c.execute(
                    "SELECT v FROM meta WHERE k='brain_uuid'").fetchone()
            except Exception:  # noqa: BLE001 — old brains may lack meta
                uuid_row = None
            out["uuid"] = uuid_row[0] if uuid_row else ""
            out["episodes"] = c.execute(
                "SELECT COUNT(*) FROM episode").fetchone()[0]
            out["vision_fires"] = c.execute(
                "SELECT COUNT(*) FROM episode WHERE "
                "json_extract(features_json,'$.vision_restructured')=1"
            ).fetchone()[0]
            for tag, n in c.execute(
                    "SELECT COALESCE(json_extract(features_json,'$.threat_tag'),"
                    "'clean'), COUNT(*) FROM episode GROUP BY 1"):
                out["threats"][tag or "clean"] = n
            c.close()
    with contextlib.suppress(Exception):
        du = shutil.disk_usage(str(db.parent) if db.exists() else PROJECT_DIR)
        out["archive"] = {"total_gb": round(du.total / 1073741824, 1),
                          "free_gb": round(du.free / 1073741824, 1)}
    with contextlib.suppress(Exception):
        out["server"] = _stats(PROJECT_DIR, brain=brain)["brains"].get(brain, {})
    return out


def main():
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT,
                log_level="info")


if __name__ == "__main__":
    main()
