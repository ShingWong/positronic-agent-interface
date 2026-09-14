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

"""Tag verb — manual threat-tag correction on one episode."""
import json

from ..engine import open_engine

ALLOWED = ("clean", "spam", "phishing", "scam")


def run(dir, *, brain=None, episode_id=None, message_id=None,
        tag=None) -> dict:
    if tag not in ALLOWED:
        return {"ok": False, "error": f"tag must be one of {ALLOWED}"}
    name = brain or "kairos"
    try:
        s, _e = open_engine(dir, name)
    except FileNotFoundError as ex:
        return {"ok": False, "error": str(ex)}
    row = None
    if episode_id:
        row = s.conn.execute(
            "SELECT id, features_json FROM episode WHERE id=?",
            (str(episode_id),)).fetchone()
    elif message_id:
        from .ingest import normalize_message_id
        mid = normalize_message_id(message_id)
        row = s.conn.execute(
            "SELECT id, features_json FROM episode WHERE kind='message' "
            "AND json_extract(features_json,'$.message_id') = ? LIMIT 1",
            (mid,)).fetchone()
    if row is None:
        return {"ok": False, "error": "episode not found"}
    feat = json.loads(row["features_json"])
    feat["threat_tag"] = tag
    feat["threat_reasons"] = ["manual"]
    s.conn.execute("UPDATE episode SET features_json=? WHERE id=?",
                   (json.dumps(feat), row["id"]))
    subj = feat.get("subject_norm") or ""
    body = feat.get("body_text") or ""
    s.conn.execute("DELETE FROM episode_fts WHERE id=?", (row["id"],))
    if (subj + " " + body).strip():
        s.fts_upsert(row["id"], f"{subj} threat:{tag} {body}".strip())
    s.conn.commit()
    return {"ok": True, "brain": name, "episode_id": row["id"], "tag": tag}
