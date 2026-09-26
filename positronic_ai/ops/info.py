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

"""Info verb — version, ENGRAM_TAG, brains, tiers (port of plugin info.ts)."""
import logging

from .. import __version__
from ..config import ENGRAM_TAG, load_config
from . import doctor

log = logging.getLogger(__name__)


def run(dir) -> dict:
    """Return {version, engram_tag, brains, tiers} for the project dir."""
    try:
        cfg = load_config(dir)
    except Exception:  # noqa: BLE001  (config absent → defaults)
        log.warning("info: config unreadable — defaults used")
        cfg = {"brains": {}, "engram_tag": ENGRAM_TAG}
    doc = doctor.run()
    return {
        "version": __version__,
        "engram_tag": cfg.get("engram_tag", ENGRAM_TAG),
        "brains": cfg.get("brains", {}),
        "tiers": doc.get("tiers", doc),
    }