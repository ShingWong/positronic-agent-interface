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

"""Delete verb — permanently remove a brain (port of plugin delete.ts)."""
import json
import logging
import shutil
from pathlib import Path

from ..config import load_config, save_config

log = logging.getLogger(__name__)


def _config_path(project_dir) -> Path:
    return Path(project_dir) / ".positronic" / "config.json"


def _load(project_dir) -> dict:
    try:
        return load_config(project_dir)
    except Exception:  # noqa: BLE001  (config absent → empty brains)
        log.warning("delete: config unreadable — empty brains assumed")
        return {"brains": {}}


def run(dir, *, brain=None, force=False) -> dict:
    """Delete a brain + its db; returns {ok, warning?, deleted?, before, after, dbPath}."""
    name = brain
    cfg_path = str(_config_path(dir))
    if not name:
        cfg = _load(dir)
        brains = list(cfg.get("brains", {}).keys())
        list_txt = ", ".join(brains) if brains else "(none)"
        help_text = (
            f"Usage: /positronic:delete --brain <name> [--force]\n"
            f"Brains here: {list_txt}\n"
            f"This will PERMANENTLY delete the brain and all its memories. Add --force to confirm."
        )
        return {"ok": False, "warning": help_text, "brains": brains}

    cfg = _load(dir)
    exists = bool(cfg.get("brains", {}).get(name))
    brain_dir = Path(dir) / ".positronic" / "brains" / name
    db = str(brain_dir / "memory.db")
    exists_on_disk = (brain_dir / "memory.db").exists() or brain_dir.exists()
    if not exists and not exists_on_disk:
        available = ", ".join(cfg.get("brains", {}).keys()) or "(none)"
        help_text = f'No brain named "{name}" here. Available: {available}'
        return {"ok": False, "warning": help_text}

    if not force:
        mem = "its" if exists_on_disk else "its config"
        warning = (
            f'This will PERMANENTLY delete brain "{name}" and all {mem} memories. '
            f"Data will be LOST. Re-run with --force or confirm:true to proceed."
        )
        return {
            "ok": False, "warning": warning, "brain": name,
            "configPath": cfg_path, "dbPath": db,
        }

    before = json.loads(json.dumps(cfg))
    shutil.rmtree(brain_dir, ignore_errors=True)
    if cfg.get("brains", {}).get(name):
        del cfg["brains"][name]
        save_config(dir, cfg)
    after = _load(dir)
    return {"ok": True, "deleted": name, "before": before, "after": after, "dbPath": db}