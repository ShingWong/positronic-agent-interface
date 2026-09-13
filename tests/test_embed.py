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

import io
import json
import os
import urllib.error
import urllib.request

import pytest

needs_bge = pytest.mark.skipif(
    os.environ.get("POSITRONIC_BGE_URL", "http://127.0.0.1:8090") == "off",
    reason="no bge server")

URL = os.environ.get("POSITRONIC_BGE_URL", "http://127.0.0.1:8090")


@needs_bge
def test_embed_one_mean_pools_chunks():
    from positronic_ai.embed import embed_one
    vec, n = embed_one("Alpha one. " * 800, url=URL)
    assert len(vec) == 1024 and n > 1


@needs_bge
def test_embed_halves_on_500():
    from positronic_ai.embed import _embed_halving
    big = "word " * 20000  # ~20k tokens, over the 2048 ceiling
    vec = _embed_halving(big, url=URL)
    assert len(vec) == 1024  # halved until it fits, no exception


@needs_bge
def test_embed_one_short_text_single_chunk():
    from positronic_ai.embed import embed_one
    vec, n = embed_one("short text", url=URL)
    assert len(vec) == 1024 and n == 1


def _http_error(code, msg):
    return urllib.error.HTTPError("http://x/embedding", code, msg, {}, io.BytesIO(
        json.dumps({"error": {"message": msg}}).encode()))


def test_non_size_http_error_is_loud_runtime_error(monkeypatch):
    import positronic_ai.embed as em

    def boom(req, timeout=None):
        raise _http_error(503, "model loading")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError, match="embedding HTTP 503"):
        em._post_embedding("hello", "http://127.0.0.1:8090")


def test_still_too_large_after_max_halvings_is_loud(monkeypatch):
    import positronic_ai.embed as em

    def boom(req, timeout=None):
        raise _http_error(500, "input too large to process")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    big = "word " * 20000
    with pytest.raises(RuntimeError, match="too large after"):
        em._embed_halving(big, "http://127.0.0.1:8090")


def test_embed_one_surfaces_failure_loudly(monkeypatch):
    import positronic_ai.embed as em

    def boom(req, timeout=None):
        raise _http_error(500, "input too large to process")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(RuntimeError):
        em.embed_one("Alpha one. " * 800, "http://127.0.0.1:8090")


def test_open_engine_binds_embedder_for_local_brain(tmp_path, monkeypatch):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine

    bound = []
    monkeypatch.setattr("memeng.engine.MemoryEngine.bind_embedder",
                        lambda self, fn: bound.append(fn))
    init_brain(str(tmp_path), "mail", "balanced", "local")
    open_engine(str(tmp_path), "mail")
    assert len(bound) == 1


def test_open_engine_no_bind_for_lexical_brain(tmp_path, monkeypatch):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine

    bound = []
    monkeypatch.setattr("memeng.engine.MemoryEngine.bind_embedder",
                        lambda self, fn: bound.append(fn))
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    open_engine(str(tmp_path), "kairos")
    assert bound == []


def test_ingest_reports_embedded_and_reason(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run

    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    out = run(str(tmp_path), "hello world")
    assert out["embedded"] is False
    assert "embed" in out["embed_reason"]
