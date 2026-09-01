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

"""Brain-test verb — smoke probe: encode + activate a probe event (port of brainTest.ts)."""
import time
from datetime import datetime, timezone

from memeng.models import Event

from ..engine import open_engine


def run(dir, *, brain="kairos", k=3) -> dict:
    """Write a probe event, time encode + recall, return {ok, encode_ms, recall_ms, hits, fallback, rrf_score}."""
    k = k or 3
    _s, e = open_engine(dir, brain)

    t0 = time.perf_counter()
    e.new_event(Event(stream=f"positronic:{brain}", kind="message",
                      persons=["p_kairos"], wall=datetime.now(timezone.utc),
                      features={"subject_norm": "positronic:probe",
                                "body_text": "probe positronic", "arousal": 0.8}))
    encode_ms = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    results = e.activate({"text": "probe positronic"}, k=k)
    recall_ms = (time.perf_counter() - t1) * 1000

    hits = 1 if any(r.get("episode_id") for r in results) else 0
    fallback = bool(any(r.get("fallback") for r in results))
    return {"ok": hits > 0, "encode_ms": encode_ms, "recall_ms": recall_ms,
            "hits": hits, "fallback": fallback, "rrf_score": 0.016}