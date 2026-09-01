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

"""Wake verb — orientation brief: top anchors + today's consolidations.

Reads the first configured brain (the live one); never imports the private
kairos_brain. Returns {brief: "<multi-line string>"}.
"""
from datetime import datetime, timezone
from pathlib import Path

from ..config import load_config
from ..engine import open_engine

_ANCHORS_SQL = ("SELECT substr(id,1,12) id, round(tau,2) tau, kind, "
                "subject_norm, substr(body_text,1,120) snippet "
                "FROM episode WHERE is_anchor=1 ORDER BY tau DESC LIMIT 3")
_CONSOLIDATE_SQL = ("SELECT round(tau,2) tau, subject_norm, "
                    "substr(body_text,1,160) snippet "
                    "FROM episode WHERE kind='consolidation' "
                    "AND substr(wall,1,10)=? ORDER BY tau DESC")

def run(dir) -> dict:
    """Assemble the orientation brief; {brief: str}."""
    cfg = load_config(dir)
    name = next(iter(cfg.get("brains", {})), None)
    if not name:
        return {"brief": "(no brains configured — run positronic init)"}
    db = Path(dir) / ".positronic" / "brains" / name / "memory.db"
    if not db.exists():
        return {"brief": "(no brain db — run positronic init)"}
    s, _e = open_engine(dir, name)
    anchors = [dict(r) for r in s.conn.execute(_ANCHORS_SQL).fetchall()]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cons = [dict(r) for r in s.conn.execute(
        _CONSOLIDATE_SQL, (today,)).fetchall()]

    lines = [f"μ orientation — {name}"]
    lines.append("anchors:")
    if anchors:
        for a in anchors:
            subj = a["subject_norm"] or a["snippet"] or "(untitled)"
            lines.append(f"  τ={a['tau']}  {subj}")
    else:
        lines.append("  (no anchors)")
    lines.append("consolidated today:")
    if cons:
        for c in cons:
            subj = c["subject_norm"] or c["snippet"] or "(untitled)"
            lines.append(f"  τ={c['tau']}  {subj}")
    else:
        lines.append("  (none)")
    return {"brief": "\n".join(lines)}