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

"""Consolidate verb — write a consolidation summary as kind='consolidation' event."""
from .ingest import run as ingest_run


def run(dir, text, *, brain=None, arousal=0.4) -> dict:
    """Write a consolidation event; {ok, tau, encoded, episode_id} on success."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "_note": "(empty summary — nothing to consolidate)"}
    r = ingest_run(dir, text, brain=brain, kind="consolidation", arousal=arousal)
    return {"ok": True, "tau": r["tau"], "encoded": r["encoded"],
            "episode_id": r["episode_id"]}