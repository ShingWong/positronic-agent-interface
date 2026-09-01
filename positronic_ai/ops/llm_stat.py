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

"""LLM-stat verb — bge/llama tiers + pooling (port of plugin llmStat.ts).

pooling is "cls" when the bge tier is ok, else "unknown".
"""
from . import doctor


def run() -> dict:
    """Return {bge, llama, lexical, engram, pooling}."""
    t = doctor.run()["tiers"]
    return {
        "bge": t["bge"],
        "llama": t["llama"],
        "lexical": t["lexical"],
        "engram": t["engram"],
        "pooling": "cls" if t["bge"] == "ok" else "unknown",
    }