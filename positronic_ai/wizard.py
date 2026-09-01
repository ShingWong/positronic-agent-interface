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

"""Init wizard — help text + config merge (port of plugin wizard.ts)."""
import logging
from pathlib import Path

from .brains import init_brain
from .config import ENGRAM_TAG, load_config, save_config

log = logging.getLogger(__name__)

HELP = """Pick how your brain remembers:

**Name** — what to call this brain (default: kairos). Use one brain per project or one per concern (e.g. mail, research).

**Profile — how long to remember (retention):**
  • balanced — forgets stale stuff after weeks (good default; E7 keeps ~35% at horizon)
  • long_term — remembers months (good for mail/archive)
  • archival — never forgets (good for legal/knowledge base; grows forever)
  • short_term — forgets in days (good for experiments/scratch)

**Embed — how to find things:**
  • lexical — fast text search, no setup (works everywhere)
  • local — semantic search on your machine (needs BGE-M3 llama.cpp :8090)
  • remote — semantic search via API key (needs remote_url + key)

**Live — ingest this chat live (default: yes):**
  • --live (default) — every session message is remembered automatically (live ingestion)
  • --no-live — don't ingest; only manual /positronic:remember or brain-test writes

Examples:
  positronic init                                    # kairos, balanced, lexical, live=yes
  positronic init --brain mail --profile long_term --embed local
  positronic init --brain research --profile archival --embed remote --force
  positronic init --no-live                          # disable live ingestion (add --live to re-enable)

Next: run with a specific --brain/--profile/--embed to create. If a brain already exists you will be warned to add --force (data will be lost)."""


def _config_path(project_dir) -> Path:
    return Path(project_dir) / ".positronic" / "config.json"


def _existing_names(project_dir, answers: list) -> list:
    """Names whose brain dir + memory.db already exist on disk."""
    brains_dir = Path(project_dir) / ".positronic" / "brains"
    found = []
    for a in answers:
        db = brains_dir / a["name"] / "memory.db"
        if db.exists():
            found.append(a["name"])
    return found


def init_run(dir, *, brains=None, force=False, live=None,
             auto_consolidate=None, auto_prune=None) -> dict:
    """Run the init wizard; returns {ok, warning?, brains, created, existing, configPath, live?}.

    No brains → help text (no side-effects). Existing brain without force →
    warning. Otherwise init_brain per brain and merge config preserving keys.
    """
    answers = brains
    cfg_path = str(_config_path(dir))
    if not answers:
        return {
            "ok": False, "warning": HELP, "brains": {},
            "created": [], "existing": [], "configPath": cfg_path,
        }

    existing = _existing_names(dir, answers)
    if existing and not force:
        warning = (
            f"Existing brain(s) will be OVERWRITTEN and data will be LOST: "
            f"{', '.join(existing)}. Re-run with --force or confirm:true to proceed."
        )
        new_brains = {a["name"]: {"profile": a["profile"], "embed": a["embed"]} for a in answers}
        return {
            "ok": False, "warning": warning, "brains": new_brains,
            "created": [], "existing": existing, "configPath": cfg_path,
        }

    new_brains = {}
    for a in answers:
        init_brain(dir, a["name"], a["profile"], a["embed"])
        new_brains[a["name"]] = {"profile": a["profile"], "embed": a["embed"]}

    try:
        existing_cfg = load_config(dir)
    except Exception:  # noqa: BLE001  (config absent → fresh init)
        log.warning("init: config unreadable — starting fresh")
        existing_cfg = {}
    live_val = live if live is not None else existing_cfg.get("live", True)
    prev_auto = existing_cfg.get("auto") or {}
    auto = {
        "consolidate_every": auto_consolidate if auto_consolidate is not None
                              else prev_auto.get("consolidate_every", 0),
        "prune_every": auto_prune if auto_prune is not None
                        else prev_auto.get("prune_every", 0),
    }
    merged = {
        "brains": {**(existing_cfg.get("brains") or {}), **new_brains},
        "live": live_val,
        "embed": existing_cfg.get("embed") or {"local_url": "http://127.0.0.1:8090"},
        "engram_tag": existing_cfg.get("engram_tag") or ENGRAM_TAG,
        "auto": auto,
    }
    save_config(dir, merged)

    return {
        "ok": True, "brains": new_brains, "created": list(new_brains.keys()),
        "existing": existing, "configPath": cfg_path, "live": live_val,
        "auto": auto,
    }