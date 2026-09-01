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

"""Recall verb — federated fuzzy recall fused across all configured brains.

Public-safe: touches only `.positronic/brains/*` (never the private
kairos_brain). Per-brain `activate` hits are merged with reciprocal-rank
fusion (RRF); each hit is tagged with its source brain.
"""
import logging
from pathlib import Path

from ..config import load_config
from ..engine import open_engine
from ..objects import object_digest, resolve_object

log = logging.getLogger(__name__)


def run(dir, text, *, k=8, brains=None) -> dict:
    """Fuse per-brain activate hits; {results: [...], object?: {versions}}.

    When the cue fuzzy-matches an object, a compact polytemporal digest
    (versions) is attached — the agent decides how deep to dig (ask reveals
    the full τ-ordered dossier).
    """
    text = (text or "").strip()
    if not text:
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
        try:
            _s, e = open_engine(dir, name)
            hits = e.activate({"text": text}, k=k)
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

    obj = _resolve_any(dir, names, text)
    if obj is not None:
        out["object"] = obj
    return out


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