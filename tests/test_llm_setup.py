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

def test_llm_setup_guide_default():
    from pathlib import Path

    from positronic_ai.ops.llm_setup import run
    doc = Path(__file__).resolve().parents[1] / "docs" / "llama.md"
    out = run()
    assert out["tier"] == "3"
    assert out["guide"] == doc.read_text("utf-8")[:500]
    assert out["guide"].startswith("# Llama Setup")

def test_llm_setup_tier():
    from positronic_ai.ops.llm_setup import run
    assert run("2")["tier"] == "2"