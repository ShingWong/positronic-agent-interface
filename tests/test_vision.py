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

import os

import pytest

from positronic_ai import vision

needs_vision = pytest.mark.skipif(
    os.environ.get("POSITRONIC_VISION_URL", "on") == "off",
    reason="no vision server")


def _vision_skip() -> bool:
    import urllib.request
    url = os.environ.get("POSITRONIC_VISION_TEST_URL", "http://127.0.0.1:8080")
    try:
        urllib.request.urlopen(url + "/health", timeout=5).read()
        return False
    except Exception:  # noqa: BLE001
        return True


def test_detector_pipe_table():
    t = "| Q | A |\n| Q1 | 5 |\n| Q2 | 7 |"
    assert vision.looks_like_table(t) is True


def test_detector_plain_text():
    assert vision.looks_like_table("Hello world, this is a normal email.") is False
    assert vision.looks_like_table("") is False


def test_detector_aligned_columns():
    t = ("Name    Total  Paid\nJohn    $30.00  $25.00\n"
         "Mary    $40.00  $40.00\nBob     $22.50  $20.00")
    assert vision.looks_like_table(t) is True


def test_url_list_same_as_embed():
    assert vision._as_url_list("http://a:8080, http://b:8081") == \
        ["http://a:8080", "http://b:8081"]
    assert vision._as_url_list(["http://a:8080"]) == ["http://a:8080"]


def test_passthrough_non_table():
    text, was = vision.maybe_restructure("plain mail body", "http://127.0.0.1:9")
    assert (text, was) == ("plain mail body", False)


@pytest.mark.skipif(_vision_skip(), reason="no vision server on :8080")
def test_live_restructure():
    url = os.environ.get("POSITRONIC_VISION_TEST_URL", "http://127.0.0.1:8080")
    t = "| Q | A | B |\n| Q1 | 1200 | 800 |\n| Q2 | 1500 | 950 |"
    out = vision.restructure_table(t, url)
    assert "1200" in out and "1500" in out


def test_vision_url_config_roundtrip():
    import tempfile

    from positronic_ai.config import load_config, set_key
    with tempfile.TemporaryDirectory() as d:
        set_key(d, "vision_url", "http://127.0.0.1:8080, http://192.168.4.20:8081")
        cfg = load_config(d)
        assert cfg["embed"]["vision_url"] == \
            "http://127.0.0.1:8080, http://192.168.4.20:8081"
