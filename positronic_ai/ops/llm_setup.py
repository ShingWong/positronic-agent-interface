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

"""LLM-setup verb — tier guide from docs/llama.md (port of plugin llmSetup.ts)."""
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_DOC = Path(__file__).resolve().parents[2] / "docs" / "llama.md"
_GUIDE_LEN = 500

def run(tier="3") -> dict:
    """Return {tier, guide} where guide is the first 500 chars of docs/llama.md."""
    try:
        md = _DOC.read_text("utf-8")
    except Exception:  # noqa: BLE001  (missing doc → fallback text)
        log.warning("llm-setup: docs/llama.md unreadable")
        md = "see docs/llama.md"
    return {"tier": str(tier), "guide": md[:_GUIDE_LEN]}