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

"""Multi-brain DB init (federation) — port of the plugin's brains.py shim.

Consumes memeng (SQLiteStore, MemoryEngine) via PYTHONPATH; config update
goes through positronic_ai.config. No hardcoded sys.path.
"""
from pathlib import Path

from memeng.engine import MemoryEngine
from memeng.store import SQLiteStore

from .config import (
    ALLOWED_EMBEDS,
    ALLOWED_PROFILES,
    load_config,
    save_config,
)


def init_brain(project_dir, name: str, profile: str, embed: str = "lexical", threshold=None) -> str:
    """Validate retention_profile, create .positronic/brains/{name}/memory.db and register domain.

    Also updates .positronic/config.json brains dict and ensures engram_tag pin.
    Returns path to memory.db as string.
    """
    if profile not in ALLOWED_PROFILES:
        raise ValueError(f"unknown retention profile: {profile}")
    if embed not in ALLOWED_EMBEDS:
        raise ValueError(f"unknown embed choice: {embed}")

    p = Path(project_dir) / ".positronic" / "brains" / name
    p.mkdir(parents=True, exist_ok=True)
    db_path = p / "memory.db"
    s = SQLiteStore(str(db_path))
    e = MemoryEngine(s)
    e.init_database()
    e.register_domain(name, retention_profile=profile)
    e.attach_stream(f"positronic:{name}", name)

    # update config
    cfg = load_config(project_dir)
    cfg["brains"][name] = {"profile": profile, "embed": embed}
    if threshold is not None:
        cfg["brains"][name]["threshold"] = threshold
    save_config(project_dir, cfg)

    return str(db_path)