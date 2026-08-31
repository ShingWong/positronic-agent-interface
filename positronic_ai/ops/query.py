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

"""Query verb — brain read ops (text/cue recall, anchors, objects, sightings, raw SQL).

Faithful Python port of the plugin's TS `query` command (query.ts): each branch
uses the exact same SQL / activate call and returns the same `{ok, brain, results}`
shape (text returns the `{ms, hits, results}` shape).
"""
import json
import math
import time

from ..engine import open_engine

USAGE = ("positronic query <text> --brain <name> --k <n> | --sql <SQL> "
         "| --cue <text> | --anchors | --objects | --sightings")

_ANCHORS_SQL = ("SELECT substr(id,1,12) id,round(tau,2) tau,kind,"
                "substr(subject_norm,1,80) sn FROM episode WHERE is_anchor=1 "
                "ORDER BY tau DESC LIMIT {}")
_SIGHTINGS_SQL = ("SELECT o.canonical_name obj,e.tau,os.channel FROM "
                  "object_sighting os JOIN object o ON os.object_id=o.id "
                  "JOIN episode e ON os.episode_id=e.id ORDER BY e.tau DESC "
                  "LIMIT {}")
_OBJECTS_SQL = ("SELECT id,canonical_name,kind,first_seen_tau,last_seen_tau,"
                "status FROM object ORDER BY first_seen_tau DESC LIMIT {}")

def _round(n, d: int) -> float:
    """Math.round port (half toward +inf), matching query.ts round()."""
    m = 10 ** d
    return math.floor(n * m + 0.5) / m

def _human(parsed) -> str:
    if isinstance(parsed, list):
        if not parsed:
            return "(no results)"
        lines = []
        for i, h in enumerate(parsed, 1):
            tau = h.get("tau") if h.get("tau") is not None else h.get("first_seen_tau", 0)
            tau = tau if tau is not None else 0
            subject = (h.get("subject_norm") or h.get("canonical_name") or "")[:60]
            lines.append(f"  {i}. τ={_round(tau, 2)} {subject}")
        return "\n".join(lines)
    return json.dumps(parsed, default=str)[:200]

def run(dir, *, brain=None, text=None, sql=None, cue=None,
        objects=False, anchors=False, sightings=False, k=8) -> dict:
    brain = brain or "kairos"
    k = k or 8
    try:
        s, e = open_engine(dir, brain)
    except FileNotFoundError as ex:
        msg = str(ex)
        return {"ok": False, "error": msg, "human": msg}

    if sql:
        rows = [dict(r) for r in s.conn.execute(sql).fetchall()]
    elif anchors:
        rows = [dict(r) for r in s.conn.execute(_ANCHORS_SQL.format(k)).fetchall()]
    elif sightings:
        rows = [dict(r) for r in s.conn.execute(_SIGHTINGS_SQL.format(k)).fetchall()]
    elif objects:
        rows = [dict(r) for r in s.conn.execute(_OBJECTS_SQL.format(k)).fetchall()]
    elif cue:
        rows = e.activate({"text": cue}, k=k)
    else:
        qtext = (text or "").strip()
        if not qtext:
            return {"ok": True, "help": True, "usage": USAGE,
                    "human": ("usage: positronic query <text> | --sql <SQL> "
                              "| --cue <text> | --anchors | --objects | "
                              "--sightings [--brain kairos] [--k 8]")}
        t0 = time.perf_counter()
        hits = e.activate({"text": qtext}, k=k)
        ms = (time.perf_counter() - t0) * 1000
        out = {"ok": True, "brain": brain, "ms": _round(ms, 2),
               "hits": len(hits), "results": hits}
        out["human"] = _human(out["results"])
        return out

    out = {"ok": True, "brain": brain, "results": rows}
    out["human"] = _human(rows)
    return out