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

"""Ingest verb — write a raw observation into the live brain as an Event."""
from datetime import datetime, timezone

from memeng.models import Event

from ..config import load_config
from ..engine import open_engine

def run(dir, text, *, brain=None, kind="message", arousal=0.5, subject=None) -> dict:
    cfg = load_config(dir)
    if cfg.get("live") is False and kind == "message":
        return {"encoded": False, "reason": "live=false"}
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name:
        raise ValueError("no brains configured — run positronic init")
    s, e = open_engine(dir, name)
    subj = subject or text[:80]
    r = e.new_event(Event(stream=f"positronic:{name}", kind=kind,
                          persons=["p_kairos"], wall=datetime.now(timezone.utc),
                          features={"subject_norm": subj, "body_text": text, "arousal": arousal}))
    return {"tau": r.tau, "encoded": bool(r.verdict.encoded), "episode_id": str(r.episode_id)}