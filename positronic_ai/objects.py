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

"""Shared object-lookup helpers for the polytemporal dossier.

One object = a family of time-stamped sightings (messages + consolidations).
The engine records them; these helpers surface the family to the agent so it
can decide how deep to dig (ask reveals the full dossier, recall a digest).
"""
from __future__ import annotations

_OBJECT_SQL = ("SELECT id, canonical_name, kind, status, salience, "
               "first_seen_tau, last_seen_tau FROM object "
               "WHERE canonical_name = ? OR canonical_name LIKE ? "
               "OR REPLACE(REPLACE(canonical_name,'-',' '),'_',' ') LIKE ? "
               "ORDER BY (canonical_name = ?) DESC LIMIT 1")
_SIGHTINGS_SQL = ("SELECT os.episode_id, os.channel, os.confidence, "
                  "e.tau, e.wall, e.subject_norm, e.kind, "
                  "COALESCE(e.subject_norm, "
                  "json_extract(e.features_json,'$.body_text')) AS body_text "
                  "FROM object_sighting os JOIN episode e ON os.episode_id=e.id "
                  "WHERE os.object_id = ? ORDER BY e.tau DESC")
_CONSOLIDATION_SQL = ("SELECT COALESCE(e.subject_norm, "
                      "json_extract(e.features_json,'$.body_text')) "
                      "AS subject_norm FROM object_sighting os "
                      "JOIN episode e ON os.episode_id=e.id "
                      "WHERE os.object_id = ? AND e.kind='consolidation' "
                      "ORDER BY e.tau DESC LIMIT 1")
_DIGEST_SQL = ("SELECT COUNT(*) AS sighting_count, "
               "COALESCE(MIN(e.tau),0.0) AS oldest_tau, "
               "COALESCE(MAX(e.tau),0.0) AS latest_tau "
               "FROM object_sighting os JOIN episode e ON os.episode_id=e.id "
               "WHERE os.object_id = ?")

def resolve_object(store, object_name: str) -> dict | None:
    """Fuzzy object lookup; returns the object row dict or None.

    Matches the exact name, a substring, or a hyphen/underscore-normalized
    variant (entity extraction hyphenates 'opencode plugin'; agents cue with
    spaces). Exact match ranks first.
    """
    object_name = (object_name or "").strip()
    if not object_name:
        return None
    like = f"%{object_name}%"
    row = store.conn.execute(
        _OBJECT_SQL,
        (object_name, like, like, object_name)).fetchone()
    return dict(row) if row else None

def object_sightings(store, object_id: str) -> list[dict]:
    """Full τ-ordered dossier for one object (dig-deeper payload)."""
    return [dict(r) for r in store.conn.execute(
        _SIGHTINGS_SQL, (object_id,)).fetchall()]

def object_digest(store, object_id: str) -> dict:
    """Compact polytemporal digest: counts, τ span, latest consolidation."""
    row = store.conn.execute(_DIGEST_SQL, (object_id,)).fetchone()
    cons = store.conn.execute(_CONSOLIDATION_SQL, (object_id,)).fetchone()
    d = dict(row) if row else {"sighting_count": 0, "oldest_tau": 0.0,
                               "latest_tau": 0.0}
    return {
        "sighting_count": int(d["sighting_count"]),
        "tau_span": [float(d["oldest_tau"]), float(d["latest_tau"])],
        "latest_consolidation": (cons["subject_norm"] if cons else None),
        "oldest_tau": float(d["oldest_tau"]),
    }