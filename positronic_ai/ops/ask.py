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
import logging
from pathlib import Path

from ..config import load_config
from ..engine import open_engine
from ..objects import object_sightings, resolve_object

log = logging.getLogger(__name__)


def run(dir, object_name) -> dict:
    """Look up an object dossier across brains; {object, sightings, found}."""
    if not (object_name or "").strip():
        return {"object": None, "sightings": [], "found": False}
    cfg = load_config(dir)
    for name in cfg.get("brains", {}):
        db = Path(dir) / ".positronic" / "brains" / name / "memory.db"
        if not db.exists():
            continue
        try:
            s, _e = open_engine(dir, name)
            row = resolve_object(s, object_name)
            if row is None:
                continue
            sightings = object_sightings(s, row["id"])
            return {"object": row, "sightings": sightings, "found": True}
        except Exception:  # noqa: BLE001  (federated skip — one bad brain must not fail the search)
            log.warning("ask: brain %s skipped — open/fetch failed", name)
            continue
    return {"object": None, "sightings": [], "found": False}