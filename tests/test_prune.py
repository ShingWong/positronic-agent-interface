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

def test_prune_seed_200():
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    from positronic_ai.ops.prune import run as prune
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        for i in range(200):
            ingest(d, f"event {i}: varied note about liquid fire engine build {i}", arousal=0.0)
        rep = prune(d, tau_now=200)
        assert rep["scanned"] >= 200
        assert rep["expired"] >= 1
        assert rep["day_merged"] >= 1

def test_prune_live_false_skips():
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.config import set_key
    from positronic_ai.ops.prune import run as prune
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        set_key(d, "live", False)
        out = prune(d)
        assert out["_note"] == "live=false — pruning disabled"
        assert "expired" not in out