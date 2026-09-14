# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License, published by
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
"""PAI HTTP server — FastAPI wrapper around existing ops.

Exposes PAI verbs as REST endpoints. No new logic — pure transport.
Config via env vars:
  POSITRONIC_PROJECT_DIR — project dir (default: CWD)
  POSITRONIC_SERVER_HOST — bind host (default: 0.0.0.0)
  POSITRONIC_SERVER_PORT — bind port (default: 8080)
"""
import os
import re

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

PROJECT_DIR = os.environ.get("POSITRONIC_PROJECT_DIR", os.getcwd())
SERVER_HOST = os.environ.get("POSITRONIC_SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("POSITRONIC_SERVER_PORT", "8080"))


def sanitize_brain(name) -> str | None:
    """Sanitize a client-supplied brain name to a safe directory slug.

    Lowercase, non-alphanumerics → underscore, max 40 chars.
    Returns None for empty/invalid input (caller falls back to default).
    """
    if not name:
        return None
    slug = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")[:40]
    return slug or None


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


class RecallRequest(BaseModel):
    text: str
    k: int = 8
    brains: list[str] | None = None
    consolidation: str | None = None
    context_window: int = 0


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
    brain: str = "kairos"
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
    brain = sanitize_brain(req.brain)
    if not brain:
        # Per-user deployment default: the mail instance serves one user.
        brain = sanitize_brain(os.environ.get("POSITRONIC_MAIL_BRAIN"))
    if brain:
        ensure_brain(brain)
    # Store the body honestly — empty stays empty so the client can warn.
    # The op falls back to subject only for the subject_norm label.
    text = (req.body or "").strip()
    body_convert = "plain"
    if req.isHtml and text:
        try:
            from positronic_ai.extract.html import html_to_markdown
            text = html_to_markdown(text).strip()
            body_convert = "html2text"
        except Exception:  # noqa: BLE001  (fallback must never fail ingest)
            import re as _re
            text = _re.sub(r"<[^>]*>", " ", text).strip()
            body_convert = "regex-fallback"
    out = _run(PROJECT_DIR, text, brain=brain, kind="message",
               subject=req.subject or None,
               sender=req.sender or None,
               date=req.date or None,
               message_id=req.messageId or None,
               role="assistant")
    out["brain"] = brain
    out["body_chars"] = len(text)
    out["body_convert"] = body_convert
    return out


@app.post("/tag")
def tag(req: TagRequest):
    from positronic_ai.ops.tag import run as _run
    brain = sanitize_brain(req.brain)
    if not brain:
        brain = sanitize_brain(os.environ.get("POSITRONIC_MAIL_BRAIN"))
    return _run(PROJECT_DIR, brain=brain, episode_id=req.episode_id,
                message_id=req.message_id, tag=req.tag)


@app.post("/recall")
def recall(req: RecallRequest):
    from positronic_ai.ops.recall import run as _run
    return _run(PROJECT_DIR, req.text, k=req.k, brains=req.brains,
                consolidation=req.consolidation,
                context_window=req.context_window)


@app.post("/query")
def query(req: QueryRequest):
    from positronic_ai.ops.query import run as _run
    return _run(PROJECT_DIR, brain=req.brain, text=req.text, sql=req.sql,
                cue=req.cue, objects=req.objects, anchors=req.anchors,
                sightings=req.sightings, k=req.k,
                consolidation=req.consolidation,
                context_window=req.context_window)


@app.post("/ask")
def ask(req: AskRequest):
    from positronic_ai.ops.ask import run as _run
    return _run(PROJECT_DIR, req.object_name)


@app.post("/brain-test")
def brain_test(req: BrainTestRequest):
    from positronic_ai.ops.brain_test import run as _run
    return _run(PROJECT_DIR, brain=req.brain, k=req.k)


@app.get("/info")
def info():
    from positronic_ai.ops.info import run as _run
    return _run(PROJECT_DIR)


@app.get("/stats")
def stats():
    from positronic_ai.ops.stats import run as _run
    return _run(PROJECT_DIR)


def main():
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT,
                log_level="info")


if __name__ == "__main__":
    main()
