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

"""Prune verb — run decay pruning on the live brain (parity with plugin prune.ts)."""
from dataclasses import asdict

from ..config import load_config
from ..engine import open_engine


def run(dir, *, brain=None, tau_now=None, decay_axis="tau",
        wall_now=None) -> dict:
    """Prune expired/merged episodes; returns PruneReport as dict.

    Skips when cfg.live is False (parity with plugin prune.ts).
    decay_axis selects the clock: "tau" (default, unchanged) or "wall".
    On "wall", strengths read as day-scale horizons with no re-denomination
    (balanced 30d, long_term 120d, short_term 6d) -- the volume-independent
    axis for log brains, where a week's ingest accrues 136k tau but 7 days.
    An unknown axis fails loud: silently pruning on the wrong clock would
    expire what the caller meant to keep, with no error anywhere.
    """
    if decay_axis not in ("tau", "wall"):
        raise ValueError(
            f"unknown decay_axis {decay_axis!r}; known: ['tau', 'wall']")
    cfg = load_config(dir)
    if cfg.get("live") is False:
        return {"_note": "live=false — pruning disabled"}
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name:
        raise ValueError("no brains configured — run positronic init")
    _s, e = open_engine(dir, name)
    rep = e.prune(tau_now=tau_now, decay_axis=decay_axis, wall_now=wall_now)
    return asdict(rep)