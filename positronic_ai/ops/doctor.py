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

"""Doctor verb — health tiers (engram/bge/llama/lexical), port of plugin doctor.ts.

Each tier is probed the same way the TS command does: engram via PYTHONPATH
import of memeng.store, bge via a 2s urllib health probe, llama via binary
existence, lexical always ok (FTS5).
"""
import json
import logging
import os
import shutil
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

BGE_URL = "http://127.0.0.1:8090/health"
BGE_TIMEOUT = 2
# llama-server is an optional local model server, so it is never on PATH by
# default and cannot be assumed to exist. The old LLAMA_FALLBACK constant
# hardcoded one developer's ~/.tmp build tree: a username in shipped public
# package code, pointing at a directory that disappears on any rebuild. Probe
# PATH plus whatever POSITRONIC_LLAMA_SERVER names instead.
LLAMA_ENV = "POSITRONIC_LLAMA_SERVER"

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
    # memeng is a declared dependency, so the import *is* the test — it works
    # from a wheel, a venv or a source checkout at any path. This used to be
    # gated on a hardcoded ENGINE_SRC/memeng/store.py existing first, which
    # reported "missing" on any machine where memeng was installed correctly
    # but not at that one absolute path, and "ok" where the import would have
    # failed anyway. The module docstring already said this was a PYTHONPATH
    # import probe; the path check contradicted it.
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
    exe = os.environ.get(LLAMA_ENV) or "llama-server"
    if shutil.which(exe) or Path(exe).is_file():
        return "ok"
    return "missing"