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

def test_defaults():
    import tempfile

    from positronic_ai.config import load_config
    with tempfile.TemporaryDirectory() as d:
        cfg = load_config(d)
        assert cfg["live"] is True and cfg["engram_tag"] == "v0.2.0"

def test_set_live_roundtrip():
    import tempfile

    from positronic_ai.config import load_config, set_key
    with tempfile.TemporaryDirectory() as d:
        set_key(d, "live", False)
        assert load_config(d)["live"] is False

def test_unknown_key_rejected():
    import tempfile

    import pytest

    from positronic_ai.config import set_key
    with tempfile.TemporaryDirectory() as d, pytest.raises(ValueError):
        set_key(d, "nope", 1)

def test_bad_profile_rejected():
    import tempfile

    import pytest

    from positronic_ai.config import set_key
    with tempfile.TemporaryDirectory() as d:
        set_key(d, "profile", "balanced", brain="kairos") if False else None  # no brain yet
        with pytest.raises(ValueError):
            set_key(d, "profile", "bogus", brain="missing")