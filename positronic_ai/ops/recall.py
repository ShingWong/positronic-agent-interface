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

"""Recall verb — federated fuzzy recall fused across all configured brains.

Public-safe: touches only `.positronic/brains/*` (never the private
kairos_brain). Per-brain `activate` hits are merged with reciprocal-rank
fusion (RRF); each hit is tagged with its source brain.
"""
import json
import logging
from pathlib import Path

from ..config import load_config
from ..engine import open_engine
from ..objects import object_digest, resolve_object

log = logging.getLogger(__name__)


def run(dir, text, *, k=8, brains=None, consolidation=None,
        context_window=0, threat=None, exhaustive=False) -> dict:
    """Fuse per-brain activate hits; {results: [...], object?: {versions}}.

    threat='flagged' (any non-clean tag) or a single tag name bypasses
    lexical ranking and lists flagged episodes newest-first — lexical
    recall cannot find threat tags (they live in features, not text).

    exhaustive=True answers "all X" requests: FTS match over subject+body
    for the cue keywords, newest-first, up to k. No ranking cutoff —
    every match comes back.

    When the cue fuzzy-matches an object, a compact polytemporal digest
    (versions) is attached — the agent decides how deep to dig (ask reveals
    the full τ-ordered dossier). consolidation passes an activate view mode:
    None (default), 'only', or 'first' (see memeng.activate). context_window=N
    expands each hit's snippet to the ±N τ-adjacent stream neighbors
    (reunites premise+answer split by per-message chunking).
    """
    text = (text or "").strip()
    if not text and not threat:
        return {"results": []}
    cfg = load_config(dir)
    all_brains = cfg.get("brains", {})
    if brains is None:
        names = list(all_brains.keys())
    else:
        names = [b for b in brains if b in all_brains]

    ranked: dict[str, dict] = {}
    for name in names:
        db = Path(dir) / ".positronic" / "brains" / name / "memory.db"
        if not db.exists():
            continue
        if threat:
            _merge_threat_hits(dir, name, db, threat, k, ranked)
            continue
        if exhaustive:
            _merge_exhaustive_hits(dir, name, db, text, k, ranked)
            continue
        try:
            _s, e = open_engine(dir, name)
            hits = e.activate({"text": text}, k=k,
                              consolidation=consolidation,
                              context_window=context_window)
        except Exception:  # noqa: BLE001  (federated skip — one bad brain must not fail recall)
            log.warning("recall: brain %s skipped — open/activate failed", name)
            continue
        for i, hit in enumerate(hits):
            eid = hit.get("episode_id")
            if not eid:
                continue
            merged = ranked.setdefault(eid, {})
            merged["rrf_score"] = merged.get("rrf_score", 0.0) + 1.0 / (60.0 + i)
            if "brain" not in merged:
                merged["brain"] = name
            for key, val in hit.items():
                if key != "rrf_score":
                    merged[key] = val

    results = []
    for hit in ranked.values():
        hit["rrf_score"] = round(hit["rrf_score"], 4)
        results.append(hit)
    results.sort(key=lambda h: -h["rrf_score"])
    out: dict = {"results": results[:k]}
    if not threat and not exhaustive:
        # Ranked mode discloses coverage: top-k of how many FTS matches.
        out["total"] = sum(
            _fts_count(Path(dir) / ".positronic" / "brains" / n / "memory.db", text)
            for n in names
            if (Path(dir) / ".positronic" / "brains" / n / "memory.db").exists())
    else:
        out["total"] = len(results)

    obj = _resolve_any(dir, names, text)
    if obj is not None:
        out["object"] = obj
    return out


_STOPWORDS = frozenset(
    "all every list give me the a an of for to show find get please".split())


def _fts_or_query(text: str) -> str:
    """Keyword OR query for FTS5: strip stopwords/punctuation, quote terms.

    FTS5 does no stemming, so plural cues miss singular bodies ("invoices"
    vs "invoice"). Each term also contributes a prefix alternative on the
    de-pluralized stem — exhaustive mode over-includes by design.
    """
    import re as _re
    terms = [t for t in _re.findall(r"[A-Za-z0-9]+", (text or "").lower())
             if t not in _STOPWORDS and len(t) > 1]
    alts = []
    for t in terms:
        alts.append(f'"{t}"')
        stem = _re.sub(r"(ies|es|s)$", "", t)
        if len(stem) >= 3 and stem != t:
            alts[-1] += f" OR {stem}*"
        elif len(t) >= 4:
            alts[-1] += f" OR {t}*"
    return " OR ".join(alts)


def _fts_count(db, text) -> int:
    """Total FTS matches for the cue (disclosure: top-k of total)."""
    import sqlite3
    q = _fts_or_query(text)
    if not q:
        return 0
    try:
        c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        n = c.execute("SELECT COUNT(*) FROM episode_fts "
                      "WHERE episode_fts MATCH ?", (q,)).fetchone()[0]
        c.close()
        return int(n)
    except Exception:  # noqa: BLE001 — count is advisory, never fatal
        return 0


def _kind_snippet(row, feats) -> str:
    """Attachment extraction text is dense — line items live past the
    normal window, so attachment hits carry the wider slice."""
    body = feats.get("body_text") or ""
    try:
        kind = row["kind"]
    except (KeyError, IndexError, TypeError):
        kind = "message"
    return body[:2000] if kind == "attachment" else body[:200]


def _merge_exhaustive_hits(dir, name, db, text, k, ranked) -> None:
    """Every FTS match for the cue keywords, newest-first (no ranking)."""
    import sqlite3
    q = _fts_or_query(text)
    if not q:
        return
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        rows = c.execute(
            "SELECT e.id, e.kind, e.features_json, e.tau, e.wall "
            "FROM episode_fts f JOIN episode e ON e.id = f.id "
            "WHERE episode_fts MATCH ? "
            "ORDER BY e.tau DESC LIMIT ?", (q, k)).fetchall()
        for i, row in enumerate(rows):
            try:
                feats = json.loads(row["features_json"] or "{}")
            except ValueError:
                feats = {}
            eid = row["id"]
            merged = ranked.setdefault(eid, {})
            merged["rrf_score"] = merged.get("rrf_score", 0.0) + 1.0 / (60.0 + i)
            merged.update({
                "brain": name,
                "episode_id": eid,
                "subject": feats.get("subject_norm") or "",
                "snippet": _kind_snippet(row, feats),
                "kind": row["kind"] if "kind" in row.keys() else "message",
                "message_id": feats.get("message_id") or "",
                "sender": feats.get("sender") or "",
                "threat_tag": feats.get("threat_tag") or "clean",
                "threat_reasons": feats.get("threat_reasons") or [],
                "tau": row["tau"],
                "wall": row["wall"],
            })
    finally:
        c.close()


def _merge_threat_hits(dir, name, db, threat, k, ranked) -> None:
    """List flagged episodes newest-first (no lexical ranking)."""
    import sqlite3
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        if threat == "flagged":
            cond = ("COALESCE(json_extract(features_json,'$.threat_tag'),"
                    "'clean') != 'clean'")
            params: tuple = ()
        else:
            cond = (
                "COALESCE(json_extract(features_json,'$.threat_tag'),"
                "'clean') = ?"
            )
            params = (threat,)
        rows = c.execute(
            "SELECT id, kind, features_json, tau, wall FROM episode "
            f"WHERE kind='message' AND {cond} "
            "ORDER BY tau DESC LIMIT ?", (*params, k)).fetchall()
        for i, row in enumerate(rows):
            try:
                feats = json.loads(row["features_json"] or "{}")
            except ValueError:
                feats = {}
            eid = row["id"]
            merged = ranked.setdefault(eid, {})
            merged["rrf_score"] = merged.get("rrf_score", 0.0) + 1.0 / (60.0 + i)
            merged.update({
                "brain": name,
                "episode_id": eid,
                "subject": feats.get("subject_norm") or "",
                "snippet": _kind_snippet(row, feats),
                "kind": row["kind"] if "kind" in row.keys() else "message",
                "message_id": feats.get("message_id") or "",
                "sender": feats.get("sender") or "",
                "threat_tag": feats.get("threat_tag") or "clean",
                "threat_reasons": feats.get("threat_reasons") or [],
                "tau": row["tau"],
                "wall": row["wall"],
            })
    finally:
        c.close()


def _resolve_any(project_dir, names, text) -> dict | None:
    """First brain with a fuzzy object match wins; returns {versions, ...}."""
    for name in names:
        db = Path(project_dir) / ".positronic" / "brains" / name / "memory.db"
        if not db.exists():
            continue
        try:
            s, _e = open_engine(project_dir, name)
        except Exception:  # noqa: BLE001  (federated skip — one bad brain must not fail recall)
            log.warning("recall: object resolve skipped brain %s", name)
            continue
        row = resolve_object(s, text)
        if row is None:
            continue
        return {**row, "versions": object_digest(s, row["id"])}
    return None