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

def _seed_brain(dir):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    for text, arousal in [("deploy positronic probe engine v0", 0.4),
                          ("probe positronic recall works", 0.8),
                          ("gamma followup event", 0.5)]:
        ingest(dir, text, arousal=arousal)

def test_brain_test_probe_hits():
    import tempfile

    from positronic_ai.ops.brain_test import run
    with tempfile.TemporaryDirectory() as d:
        _seed_brain(d)
        out = run(d)
        assert out["ok"] is True
        assert out["hits"] >= 1
        assert isinstance(out["encode_ms"], (int, float))
        assert isinstance(out["recall_ms"], (int, float))
        assert out["rrf_score"] == 0.016
        assert isinstance(out["fallback"], bool)

def test_brain_test_no_brain_db():
    import tempfile

    from positronic_ai.ops.brain_test import run
    with tempfile.TemporaryDirectory() as d:
        try:
            run(d)
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError:
            pass

def test_update_check_returns_behind():
    import tempfile

    from positronic_ai.ops.update import run
    with tempfile.TemporaryDirectory() as d:
        out = run(check=True, dir=d)
        assert isinstance(out["behind"], int)
        assert out["engramTagDiff"] is None
        assert out["npmOutdated"] is False
        assert out["logTail"] == []