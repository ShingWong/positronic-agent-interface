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

"""Ask verb — object dossier: canonical-name lookup + sightings joined to episodes.

Port of `query --objects` + `--sightings` merged for one object. Scans the
federated `.positronic/brains/*`; the first brain holding a fuzzy match wins.
Public-safe: never imports the private kairos_brain.
"""
from pathlib import Path

from ..config import load_config
from ..engine import open_engine

_OBJECT_SQL = ("SELECT id, canonical_name, kind, status, salience, "
               "first_seen_tau, last_seen_tau FROM object "
               "WHERE canonical_name = ? OR canonical_name LIKE ? "
               "ORDER BY (canonical_name = ?) DESC LIMIT 1")
_SIGHTINGS_SQL = ("SELECT os.episode_id, os.channel, os.confidence, "
                  "e.tau, e.wall, e.subject_norm, e.kind "
                  "FROM object_sighting os JOIN episode e ON os.episode_id=e.id "
                  "WHERE os.object_id = ? ORDER BY e.tau DESC")

def run(dir, object_name) -> dict:
    """Look up an object dossier across brains; {object, sightings, found}."""
    object_name = (object_name or "").strip()
    if not object_name:
        return {"object": None, "sightings": [], "found": False}
    cfg = load_config(dir)
    for name in cfg.get("brains", {}):
        db = Path(dir) / ".positronic" / "brains" / name / "memory.db"
        if not db.exists():
            continue
        try:
            s, _e = open_engine(dir, name)
            like = f"%{object_name}%"
            row = s.conn.execute(_OBJECT_SQL,
                                 (object_name, like, object_name)).fetchone()
            if row is None:
                continue
            sightings = [dict(r) for r in s.conn.execute(
                _SIGHTINGS_SQL, (row["id"],)).fetchall()]
            return {"object": dict(row), "sightings": sightings, "found": True}
        except Exception:
            continue
    return {"object": None, "sightings": [], "found": False}