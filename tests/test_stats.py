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

def _seed(dir, n=3):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    for i in range(n):
        ingest(dir, f"stats probe event {i}", arousal=0.4)

def test_stats_counts_episodes():
    import tempfile

    from positronic_ai.ops.stats import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d, 3)
        out = run(d)
        b = out["brains"]["kairos"]
        assert b["episodes"] == 3
        assert b["profile"] == "balanced"
        assert b["embed"] == "lexical"

def test_stats_brain_filter():
    import tempfile

    from positronic_ai.ops.stats import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d, 1)
        out = run(d, brain="kairos")
        assert list(out["brains"].keys()) == ["kairos"]

def test_stats_missing_db_skipped():
    import tempfile

    from positronic_ai.config import save_config
    from positronic_ai.ops.stats import run
    with tempfile.TemporaryDirectory() as d:
        save_config(d, {"brains": {"ghost": {"profile": "balanced", "embed": "lexical"}}})
        out = run(d)
        assert "ghost" not in out["brains"]