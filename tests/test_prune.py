# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
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
def test_prune_rejects_unknown_axis():
    """An unknown decay axis fails loud, before touching the brain. Silently
    pruning on the wrong clock would expire what the caller meant to keep."""
    import tempfile

    import pytest

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.prune import run as prune
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        with pytest.raises(ValueError, match="unknown decay_axis"):
            prune(d, decay_axis="fortnights")


def test_prune_wall_axis_runs():
    """The wall axis is reachable through the verb: fresh ingest survives a
    wall prune at its own wall_now (age ~0 days), proving the flag reaches
    the engine rather than being swallowed by dispatch."""
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    from positronic_ai.ops.prune import run as prune
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        for i in range(5):
            ingest(d, f"wall axis probe {i}: distinct harbor manifest note {i}",
                   arousal=0.0)
        import time
        rep = prune(d, decay_axis="wall", wall_now=time.time())
        assert rep["scanned"] >= 5
        assert rep["expired"] == 0
