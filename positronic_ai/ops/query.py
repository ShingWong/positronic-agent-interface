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

"""Query verb — brain read ops (text/cue recall, anchors, objects, sightings, raw SQL).

Faithful Python port of the plugin's TS `query` command (query.ts): each branch
uses the exact same SQL / activate call and returns the same `{ok, brain, results}`
shape (text returns the `{ms, hits, results}` shape).
"""
import json
import math
import time

from ..config import load_config
from ..engine import open_engine

USAGE = ("positronic query <text> --brain <name> --k <n> | --sql <SQL> "
         "| --cue <text> | --anchors | --objects | --sightings "
         "| --object <kind:canonical> [--since <iso> --until <iso>] "
         "| --range [--since <iso> --until <iso>] [--stream <name>]")

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

def _human_object(res) -> str:
    """One identity's life in a glance: count, span, handoffs.

    Unknown identity is a fact about the data, not a failure -- the engine
    returns found:False for exactly this reason, and the human line says so
    instead of echoing an empty list.
    """
    kind, canonical = res.get("kind"), res.get("canonical")
    if not res.get("found"):
        return f"(unknown identity {kind}:{canonical})"
    eps = res.get("episodes") or []
    walls = [ep.get("wall") for ep in eps if ep.get("wall")]
    span = f"{walls[0][:10]}..{walls[-1][:10]}" if walls else "?"
    lines = [f"{kind} {canonical}: {len(eps)} episodes, {span}"]
    for label in ("carried_by", "carried"):
        names = res.get(label) or []
        if names:
            lines.append(f"  {label}: {', '.join(names[:8])}")
    return "\n".join(lines)

def run(dir, *, brain=None, text=None, sql=None, cue=None,
        objects=False, anchors=False, sightings=False, k=8,
        consolidation=None, context_window=0, object_ref=None,
        range_=False, since=None, until=None, stream=None) -> dict:
    brain = brain or next(iter(load_config(dir).get("brains", {})), None) or "kairos"
    k = k or 8
    try:
        s, e = open_engine(dir, brain)
    except FileNotFoundError as ex:
        msg = str(ex)
        return {"ok": False, "error": msg, "human": msg}

    if sql:
        rows = [dict(r) for r in s.conn.execute(sql).fetchall()]
    elif object_ref:
        # Range-and-key first: one identity's life in wall order, no ranking.
        # The ref is kind:canonical with the split on the FIRST colon,
        # because canonicals themselves contain colons (message:queue:Q1).
        # A bare name with no kind is a guess about what the caller meant,
        # and guessing an identity is how the wrong dossier gets read.
        if ":" not in object_ref:
            raise ValueError(
                f"--object must be kind:canonical, got {object_ref!r}")
        kind, canonical = object_ref.split(":", 1)
        res = e.recall_object(kind, canonical, stream=stream,
                              since=since, until=until, limit=k)
        out = {"ok": True, "brain": brain, **res}
        out["human"] = _human_object(res)
        return out
    elif range_:
        # A window is a bound, not a ranking: oldest-first narrative order,
        # straight from the store. Unbounded --range reads from the
        # beginning; the limit (default --k) is what keeps it honest.
        ids = s.episodes_in_range(stream=stream, since=since, until=until,
                                 limit=k)
        rows = []
        for eid in ids:
            ep = s.get_episode(eid)
            if ep is None:
                continue
            feats = ep.features or {}
            rows.append({
                "episode_id": eid,
                "wall": ep.wall.isoformat() if hasattr(ep.wall, "isoformat")
                        else str(ep.wall),
                "tau": ep.tau,
                "stream": ep.stream,
                "subject_norm": ep.subject_norm
                                or (feats.get("body_text")
                                    or feats.get("message") or "")[:80],
            })
    elif anchors:
        rows = [dict(r) for r in s.conn.execute(_ANCHORS_SQL.format(k)).fetchall()]
    elif sightings:
        rows = [dict(r) for r in s.conn.execute(_SIGHTINGS_SQL.format(k)).fetchall()]
    elif objects:
        rows = [dict(r) for r in s.conn.execute(_OBJECTS_SQL.format(k)).fetchall()]
    elif cue:
        rows = e.activate({"text": cue}, k=k, consolidation=consolidation,
                                context_window=context_window)
    else:
        qtext = (text or "").strip()
        if not qtext:
            return {"ok": True, "help": True, "usage": USAGE,
                    "human": ("usage: positronic query <text> | --sql <SQL> "
                              "| --cue <text> | --anchors | --objects | "
                              "--sightings | --object <kind:canonical> | "
                              "--range [--brain kairos] [--k 8] "
                              "[--since <iso> --until <iso>] "
                              "[--stream <name>] "
                              "[--consolidation only|first]")}
        t0 = time.perf_counter()
        hits = e.activate({"text": qtext}, k=k, consolidation=consolidation,
                                context_window=context_window)
        ms = (time.perf_counter() - t0) * 1000
        out = {"ok": True, "brain": brain, "ms": _round(ms, 2),
               "hits": len(hits), "results": hits}
        out["human"] = _human(out["results"])
        return out

    out = {"ok": True, "brain": brain, "results": rows}
    out["human"] = _human(rows)
    return out