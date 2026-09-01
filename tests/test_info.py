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

def test_info_shape():
    import tempfile
    import positronic_ai
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.info import run
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        out = run(d)
        assert out["version"] == positronic_ai.__version__
        assert out["engram_tag"] == "v0.2.0"
        assert "kairos" in out["brains"]
        assert set(out["tiers"].keys()) == {"engram", "bge", "llama", "lexical"}

def test_llm_stat_shape():
    from positronic_ai.ops.llm_stat import run
    out = run()
    assert set(out.keys()) == {"bge", "llama", "lexical", "engram", "pooling"}
    assert out["pooling"] in ("cls", "unknown")