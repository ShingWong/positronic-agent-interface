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
    events = [
        ("deploy positronic query engine v0", 0.4),
        ("epsilon anchor memory marker persists", 1.0),
        ("gamma followup event", 0.5),
    ]
    for text, arousal in events[:n]:
        ingest(dir, text, arousal=arousal)
    return events[:n]

def test_query_text_returns_hit():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, text="epsilon")
        assert out["ok"] is True and out["brain"] == "kairos"
        assert out["hits"] == 1 and isinstance(out["ms"], float)
        assert out["results"][0]["episode_id"]

def test_query_sql_count():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d, n=3)
        out = run(d, sql="SELECT COUNT(*) c FROM episode")
        assert out["ok"] is True and out["results"] == [{"c": 3}]

def test_query_anchors():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, anchors=True)
        assert out["ok"] is True
        assert isinstance(out["results"], list)
        assert len(out["results"]) >= 1
        assert "sn" in out["results"][0]

def test_query_missing_brain():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        out = run(d, text="anything")
        assert out["ok"] is False and "no such brain db" in out["error"]