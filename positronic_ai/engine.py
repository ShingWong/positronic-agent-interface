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

"""Engine open helper — resolve a project brain DB to (store, engine)."""
import pathlib

from memeng.engine import MemoryEngine
from memeng.store import SQLiteStore

from .config import load_config


def open_engine(project_dir, brain: str) -> tuple[SQLiteStore, MemoryEngine]:
    db = pathlib.Path(project_dir) / ".positronic" / "brains" / brain / "memory.db"
    if not db.exists():
        raise FileNotFoundError(f"no such brain db: {db}")
    s = SQLiteStore(str(db))
    e = MemoryEngine(s)
    cfg = load_config(project_dir)
    if (cfg.get("brains", {}).get(brain, {}) or {}).get("embed") == "local":
        from .embed import embed_one
        local_url = (cfg.get("embed") or {}).get("local_url", "http://127.0.0.1:8090")
        e.bind_embedder(lambda text: embed_one(text, local_url)[0])
    return s, e
