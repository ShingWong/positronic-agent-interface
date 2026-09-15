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

    # Every brain gets a UUID at creation (stable identity; the human
    # name stays as the label). Existing brains keep working — the UUID
    # is added on first init that lacks one.
    import uuid as _uuid
    brain_uuid = str(_uuid.uuid7() if hasattr(_uuid, "uuid7") else _uuid.uuid4())
    s.conn.execute(
        "INSERT OR IGNORE INTO meta(k, v) VALUES('brain_uuid', ?)",
        (brain_uuid,))
    s.conn.commit()

    # update config
    cfg = load_config(project_dir)
    existing = (cfg.get("brains") or {}).get(name) or {}
    # Keep a stable UUID: reuse the stored one, else the new DB one.
    import sqlite3 as _sql
    stored = existing.get("uuid")
    if not stored:
        try:
            _c = _sql.connect(str(db_path))
            stored = _c.execute(
                "SELECT v FROM meta WHERE k='brain_uuid'").fetchone()
            stored = stored[0] if stored else brain_uuid
            _c.close()
        except Exception:  # noqa: BLE001 (fresh DB already has it)
            stored = brain_uuid
    cfg["brains"][name] = {"profile": profile, "embed": embed,
                           "uuid": stored}
    if threshold is not None:
        cfg["brains"][name]["threshold"] = threshold
    save_config(project_dir, cfg)

    return str(db_path)