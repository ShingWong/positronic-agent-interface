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

"""Prune verb — run tau-decay pruning on the live brain (parity with plugin prune.ts)."""
from dataclasses import asdict

from ..config import load_config
from ..engine import open_engine

def run(dir, *, brain=None, tau_now=None) -> dict:
    """Prune expired/merged episodes; returns PruneReport as dict.

    Skips when cfg.live is False (parity with plugin prune.ts).
    """
    cfg = load_config(dir)
    if cfg.get("live") is False:
        return {"_note": "live=false — pruning disabled"}
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name:
        raise ValueError("no brains configured — run positronic init")
    s, e = open_engine(dir, name)
    rep = e.prune(tau_now=tau_now)
    return asdict(rep)