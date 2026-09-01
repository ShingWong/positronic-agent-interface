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

"""Stats verb — per-brain episode counts + profile/embed help (port of plugin stats.ts)."""
import logging
from pathlib import Path

from ..config import load_config
from ..engine import open_engine

log = logging.getLogger(__name__)

PROFILE_HELP = {
    "balanced": "Keeps recent memories for a few weeks (normal use)",
    "long_term": "Keeps memories for months",
    "archival": "Never forgets — grows forever",
    "short_term": "Keeps memories for a few days (experiments)",
}
EMBED_HELP = {
    "lexical": "Fast text search",
    "local": "Smarter search on your machine",
    "remote": "Smarter search via online service",
}

def run(dir, *, brain=None) -> dict:
    """Return {brains: {name: {episodes, profile, profileHelp, embed, embedHelp}}}.

    No brain → all configured brains; a configured brain whose db is missing
    is skipped (differs from stats.ts's episodes=0 — plan-mandated).
    """
    try:
        cfg = load_config(dir)
    except Exception:  # noqa: BLE001  (config absent → empty brains)
        log.warning("stats: no config readable — empty brains")
        cfg = {"brains": {}}
    all_brains = cfg.get("brains", {})
    brains = {brain: all_brains.get(brain)} if brain else all_brains
    out = {"brains": {}}
    for name, bcfg in (brains or {}).items():
        bcfg = bcfg or {}
        db = Path(dir) / ".positronic" / "brains" / name / "memory.db"
        if not db.exists():
            continue  # missing db → skip that brain
        profile = bcfg.get("profile") or "balanced"
        embed = bcfg.get("embed") or "lexical"
        episodes = 0
        try:
            s, _e = open_engine(dir, name)
            row = s.conn.execute("SELECT COUNT(*) c FROM episode").fetchone()
            episodes = int(row["c"])
        except Exception:  # noqa: BLE001  (db corrupt → count 0, don't fail stats)
            log.warning("stats: brain %s episode count failed", name)
            episodes = 0
        out["brains"][name] = {
            "episodes": episodes,
            "profile": profile,
            "profileHelp": PROFILE_HELP.get(profile, profile),
            "embed": embed,
            "embedHelp": EMBED_HELP.get(embed, embed),
        }
    if not out["brains"]:
        out["brains"]["_note"] = "(no .positronic/brains — run /positronic:init to create one)"
    return out