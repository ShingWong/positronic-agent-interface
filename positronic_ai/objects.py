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

"""Shared object-lookup helpers for the polytemporal dossier.

One object = a family of time-stamped sightings (messages + consolidations).
The engine records them; these helpers surface the family to the agent so it
can decide how deep to dig (ask reveals the full dossier, recall a digest).
"""
from __future__ import annotations

import re as _re

_OBJECT_SQL = ("SELECT id, canonical_name, kind, status, salience, "
               "first_seen_tau, last_seen_tau FROM object "
               "WHERE canonical_name = ? OR canonical_name LIKE ? "
               "OR REPLACE(REPLACE(canonical_name,'-',' '),'_',' ') LIKE ? "
               "ORDER BY (canonical_name = ?) DESC, canonical_name ASC "
               "LIMIT 32")
_SIGHTINGS_SQL = ("SELECT os.episode_id, os.channel, os.confidence, "
                  "e.tau, e.wall, e.subject_norm, e.kind, "
                  "COALESCE(e.subject_norm, "
                  "json_extract(e.features_json,'$.body_text')) AS body_text "
                  "FROM object_sighting os JOIN episode e ON os.episode_id=e.id "
                  "WHERE os.object_id = ? ORDER BY e.tau ASC")
_CONSOLIDATION_SQL = ("SELECT COALESCE(e.subject_norm, "
                      "json_extract(e.features_json,'$.body_text')) "
                      "AS subject_norm FROM object_sighting os "
                      "JOIN episode e ON os.episode_id=e.id "
                      "WHERE os.object_id = ? AND e.kind='consolidation' "
                      "ORDER BY e.tau ASC LIMIT 1")
def _bounds(name: str):
    """Token-boundary matcher shared by resolve and candidates.

    Bounded on both sides, so mid-word substrings never match ('shing'
    must not hit 'bashing', 'sys' must not hit 'system'). `:` and `/` count
    as boundaries alongside whitespace/hyphen/underscore: log identities
    are structured as ident:pid and kind:queue (postfix/submission/smtpd
    :28801), and the pid or queue suffix IS the token operators search by.
    For entity names (no colons or slashes in practice) this changes
    nothing -- keep the two call sites on this helper so they cannot drift.
    """
    return _re.compile(r"(^|[\s\-_:/])" + _re.escape(name)
                       + r"($|[\s\-_:/])", _re.IGNORECASE)


_DIGEST_SQL = ("SELECT COUNT(*) AS sighting_count, "
               "COALESCE(MIN(e.tau),0.0) AS oldest_tau, "
               "COALESCE(MAX(e.tau),0.0) AS latest_tau "
               "FROM object_sighting os JOIN episode e ON os.episode_id=e.id "
               "WHERE os.object_id = ?")

def resolve_object(store, object_name: str) -> dict | None:
    """Fuzzy object lookup; returns the object row dict or None.

    Matches the exact name, a whole-token substring, or a
    hyphen/underscore-normalized variant (entity extraction hyphenates
    'opencode plugin'; agents cue with spaces). Exact match ranks first.
    Token boundaries are `_bounds` (whitespace, hyphen, underscore, colon,
    slash): the colon/slash matter for log identities, where the searchable
    token is a pid or queue suffix after a separator.
    """
    object_name = (object_name or "").strip()
    if not object_name:
        return None
    like = f"%{object_name}%"
    # Candidates, not a single row: the boundary test below is what decides,
    # so it has to run over every candidate. Taking one arbitrary row first
    # could discard the only row that actually matches.
    rows = store.conn.execute(
        _OBJECT_SQL,
        (object_name, like, like, object_name)).fetchall()
    if not rows:
        return None
    boundary = _bounds(object_name)
    for row in rows:
        hit = dict(row)
        if hit["canonical_name"] == object_name:
            return hit
        norm = hit["canonical_name"].replace("-", " ").replace("_", " ")
        if boundary.search(hit["canonical_name"]) or boundary.search(norm):
            return hit
    return None

def candidate_objects(store, name: str, kind: str | None = None,
                      limit: int = 10) -> list[dict]:
    """Every object a fuzzy name could mean, exact-first, boundary-filtered.

    The list behind `--object`'s front door: resolve_object answers
    one-or-none, which cannot say "did you mean...?" when it is ambiguous.
    Same token-boundary rule (mid-word substrings never match), same
    ranking, but returns ALL matches up to `limit` with their kinds, so the
    caller lists instead of guessing. `kind` scopes the search; None
    searches every kind (the cross-kind "did you mean message:...?" retry).
    """
    name = (name or "").strip()
    if not name:
        return []
    like = f"%{name}%"
    q = ("SELECT kind, canonical_name FROM object "
         "WHERE (canonical_name = ? OR canonical_name LIKE ? "
         "OR REPLACE(REPLACE(canonical_name,'-',' '),'_',' ') LIKE ?)")
    args: list = [name, like, like]
    if kind is not None:
        q += " AND kind = ?"
        args.append(kind)
    q += " ORDER BY (canonical_name = ?) DESC, canonical_name ASC LIMIT ?"
    args += [name, limit + 1]
    boundary = _bounds(name)
    out = []
    for row in store.conn.execute(q, args).fetchall():
        hit = dict(row)
        if hit["canonical_name"] != name:
            norm = hit["canonical_name"].replace("-", " ").replace("_", " ")
            if not (boundary.search(hit["canonical_name"])
                    or boundary.search(norm)):
                continue
        out.append(hit)
        if len(out) >= limit:
            break
    return out

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