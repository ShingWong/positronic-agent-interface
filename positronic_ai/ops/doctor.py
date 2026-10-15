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

The bge tier probes the server the embedder actually uses: the project's
`embed.local_url` from `.positronic/config.json` (comma/space-separated lists
are probed in order, like the embedder's own URL fallback). It only falls back
to the localhost default for a project with no config, so a brain pointed at a
LAN embedding server no longer reports "down" while encoding fine.
`$POSITRONIC_BGE_URL` overrides the probe for tests and ad-hoc checks.
"""
import json
import logging
import os
import shutil
import urllib.request
from pathlib import Path

from ..config import load_config
from ..embed import _as_url_list

log = logging.getLogger(__name__)

DEFAULT_LOCAL_URL = "http://127.0.0.1:8090"
BGE_URL = DEFAULT_LOCAL_URL + "/health"
BGE_TIMEOUT = 2
BGE_ENV = "POSITRONIC_BGE_URL"
# llama-server is an optional local model server, so it is never on PATH by
# default and cannot be assumed to exist. The old LLAMA_FALLBACK constant
# hardcoded one developer's ~/.tmp build tree: a username in shipped public
# package code, pointing at a directory that disappears on any rebuild. Probe
# PATH plus whatever POSITRONIC_LLAMA_SERVER names instead.
LLAMA_ENV = "POSITRONIC_LLAMA_SERVER"

def run(dir=None) -> dict:
    """Probe each tier; returns {tiers: {engram, bge, llama, lexical}}.

    `dir` is the project directory. Pass it (the CLI already has the cwd) so
    the bge probe reads that project's `embed.local_url`.
    """
    return {
        "tiers": {
            "engram": _engram(),
            "bge": _bge(dir),
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

def _bge_base_urls(dir=None) -> list[str]:
    """Base URLs the embedder would use for this project.

    Order: $POSITRONIC_BGE_URL (tests / ad-hoc override), else the project's
    `embed.local_url`, else the localhost default for a project with no config.
    """
    env = os.environ.get(BGE_ENV)
    if env and env.strip().lower() != "off":
        urls = _as_url_list(env)
        if urls:
            return urls
    if dir is None:
        return [DEFAULT_LOCAL_URL]
    try:
        cfg = load_config(dir)
    except Exception:  # noqa: BLE001  (config absent/unreadable → default probe)
        log.warning("doctor: config unreadable — probing %s", DEFAULT_LOCAL_URL)
        return [DEFAULT_LOCAL_URL]
    raw = (cfg.get("embed") or {}).get("local_url") or DEFAULT_LOCAL_URL
    return _as_url_list(raw) or [DEFAULT_LOCAL_URL]

def _health_url(base: str) -> str:
    url = str(base).strip().rstrip("/")
    return url if url.endswith("/health") else url + "/health"

def _bge(dir=None) -> str:
    """Probe every configured embedding URL; ok when any answers /health."""
    for base in _bge_base_urls(dir):
        url = _health_url(base)
        try:
            with urllib.request.urlopen(url, timeout=BGE_TIMEOUT) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
            if body.get("status") == "ok":
                return "ok"
        except Exception:  # noqa: BLE001  (health probe — any probe failure = down)
            log.warning("doctor: bge health probe failed (%s)", url)
    return "down"

def _llama() -> str:
    exe = os.environ.get(LLAMA_ENV) or "llama-server"
    if shutil.which(exe) or Path(exe).is_file():
        return "ok"
    return "missing"