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

"""Init verb — delegate to the wizard (port of plugin init.ts)."""
from .. import wizard

def run(dir, *, brains=None, force=False, live=None,
        auto_consolidate=None, auto_prune=None) -> dict:
    return wizard.init_run(dir, brains=brains, force=force, live=live,
                           auto_consolidate=auto_consolidate,
                           auto_prune=auto_prune)