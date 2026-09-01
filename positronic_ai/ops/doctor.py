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

"""Doctor verb — health tiers (engram/bge/llama/lexical), port of plugin doctor.ts.

Each tier is probed the same way the TS command does: engram via PYTHONPATH
import of memeng.store, bge via a 2s urllib health probe, llama via binary
existence, lexical always ok (FTS5).
"""
import json
import logging
import shutil
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

ENGINE_SRC = Path("/usr/local/devel/positronic/positronic-engram/engine/src")
BGE_URL = "http://127.0.0.1:8090/health"
BGE_TIMEOUT = 2
LLAMA_FALLBACK = "/home/swong/dls/.tmp/beellama-check/build-hip/bin/llama-server"

def run() -> dict:
    """Probe each tier; returns {tiers: {engram, bge, llama, lexical}}."""
    return {
        "tiers": {
            "engram": _engram(),
            "bge": _bge(),
            "llama": _llama(),
            "lexical": "ok",  # FTS5 always works
        }
    }

def _engram() -> str:
    if not (ENGINE_SRC / "memeng" / "store.py").exists():
        return "missing"
    try:
        import memeng.store  # noqa: F401
        return "ok"
    except Exception:  # noqa: BLE001  (health probe — any import failure = missing)
        log.warning("doctor: memeng import failed")
        return "missing"

def _bge() -> str:
    try:
        with urllib.request.urlopen(BGE_URL, timeout=BGE_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        return "ok" if body.get("status") == "ok" else "down"
    except Exception:  # noqa: BLE001  (health probe — any probe failure = down)
        log.warning("doctor: bge health probe failed")
        return "down"

def _llama() -> str:
    if shutil.which("llama-server") or Path(LLAMA_FALLBACK).exists():
        return "ok"
    return "missing"