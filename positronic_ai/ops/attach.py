"""Lazy attachment backfill: append extracted attachment text to an
existing message episode (old mail ingested before the harvester, or
bulk-skipped mail whose attachments were never extracted). Idempotent
via the [Attachment: fname] marker. Reindexes FTS with the same
subject+body formula as ingest so recall surfaces the new text."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from ..config import load_config
from ..engine import open_engine
from .ingest import normalize_message_id


def run(dir, *, brain=None, message_id="", filename="", content_b64="") -> dict:
    from positronic_ai.extract.attach import _extract_by_ext, _extension

    cfg = load_config(dir)
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name:
        raise ValueError("no brains configured — run positronic init")
    s, e = open_engine(dir, name)

    mid = normalize_message_id(message_id)
    if not mid:
        raise ValueError("message_id required")
    fname = (filename or "attachment").strip() or "attachment"
    row = s.conn.execute(
        "SELECT id, features_json FROM episode WHERE kind='message' "
        "AND json_extract(features_json,'$.message_id') = ? "
        "LIMIT 1", (mid,)).fetchone()
    if row is None:
        return {"ok": False, "reason": "no such message episode"}
    try:
        feats = json.loads(row["features_json"] or "{}")
    except ValueError:
        feats = {}
    marker = f"[Attachment: {fname}]"
    body = feats.get("body_text") or ""
    if marker in body:
        return {"ok": True, "skipped": True, "reason": "already extracted",
                "episode_id": row["id"]}

    try:
        data = base64.b64decode(content_b64 or "", validate=False)
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "reason": f"bad base64: {ex}"}
    if len(data) > 8 * 1024 * 1024:
        return {"ok": False, "reason": "attachment over 8MB cap"}
    try:
        md = _extract_by_ext(data, _extension(fname), fname)
    except Exception as ex:  # noqa: BLE001
        return {"ok": False, "reason": f"extract failed: {ex}"}
    if not (md and md.strip()):
        return {"ok": False, "reason": "no text extracted"}
    feats["body_text"] = (body + f"\n\n{marker}\n" + md.strip()).strip()
    names = feats.get("attachments") or []
    if fname not in names:
        names.append(fname)
    feats["attachments"] = names
    s.conn.execute("UPDATE episode SET features_json=? WHERE id=?",
                   (json.dumps(feats), row["id"]))
    bt = ((feats.get("subject_norm") or "") + " " + feats["body_text"]).strip()
    s.conn.execute("DELETE FROM episode_fts WHERE id=?", (row["id"],))
    if bt:
        s.fts_upsert(str(row["id"]), bt)
    s._commit()
    return {"ok": True, "episode_id": row["id"],
            "chars": len(md.strip()), "filename": fname}
