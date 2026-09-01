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

def test_ingest_writes_event():
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        out = run(d, "hello world")
        assert out["encoded"] is True and isinstance(out["tau"], float)

def test_live_false_skips():
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.config import set_key
    from positronic_ai.ops.ingest import run
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        set_key(d, "live", False)
        out = run(d, "hello")
        assert out["encoded"] is False