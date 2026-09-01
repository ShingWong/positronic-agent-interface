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
import json
from datetime import datetime, timezone

from memeng.models import Event

from ..config import load_config, save_config
from ..engine import open_engine

def run(dir, text, *, brain=None, kind="message", arousal=0.5, subject=None,
        dedup=None, role="assistant") -> dict:
    cfg = load_config(dir)
    if cfg.get("live") is False and kind == "message":
        return {"encoded": False, "reason": "live=false"}
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name:
        raise ValueError("no brains configured — run positronic init")
    s, e = open_engine(dir, name)

    dedup_eff = cfg.get("dedup") if dedup is None else dedup
    if kind == "message" and dedup_eff:
        row = s.conn.execute(
            "SELECT features_json FROM episode WHERE kind='message' "
            "AND json_extract(features_json,'$.role') = ? "
            "ORDER BY tau DESC LIMIT 1", (role,)).fetchone()
        if row is not None:
            last = json.loads(row["features_json"]).get("body_text")
            if last == text:
                return {"duplicate": True, "skipped": True, "tau": None}

    subj = subject or text[:80]
    r = e.new_event(Event(stream=f"positronic:{name}", kind=kind,
                          persons=["p_kairos"], wall=datetime.now(timezone.utc),
                          features={"subject_norm": subj, "body_text": text,
                                    "arousal": arousal, "role": role}))
    out = {"tau": r.tau, "encoded": bool(r.verdict.encoded), "episode_id": str(r.episode_id)}
    if kind == "message":
        _advance_counters(dir, name)
    return out


def _advance_counters(dir, brain) -> None:
    cfg = load_config(dir)
    counters = cfg.setdefault("counters", {"since_consolidate": 0, "since_prune": 0})
    counters["since_consolidate"] += 1
    counters["since_prune"] += 1
    save_config(dir, cfg)
    auto = cfg.get("auto") or {}
    if int(auto.get("consolidate_every") or 0) > 0 and \
            counters["since_consolidate"] >= int(auto["consolidate_every"]):
        from .consolidate import run as consolidate_run
        consolidate_run(dir, "auto consolidation", brain=brain, arousal=0.2)
        counters["since_consolidate"] = 0
    if int(auto.get("prune_every") or 0) > 0 and \
            counters["since_prune"] >= int(auto["prune_every"]):
        from .prune import run as prune_run
        prune_run(dir, brain=brain)
        counters["since_prune"] = 0
    save_config(dir, cfg)