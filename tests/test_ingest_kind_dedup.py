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

"""The message_id dedup is kind-independent: an id is an id, whatever kind of
event carries it.

History (fixed 2026-10-19; see docs patch note `2026-10-19-cve-ingest-dedup`):
`ops.ingest.run()` consulted `_dup_result` only when `kind == "message"`, but
`scripts/ingest_cve_brain.py` calls `run(..., kind="consolidation",
message_id=mid)` and depends on that dedup for idempotency. The id was
recorded in features_json and never checked: the 2026-10-11 production run
logged `new=156725 dup-skip=0 resumed-skip=32676` over 189,401 records -- the
brain dedup never fired once, and the brain accumulated 1,106 CVE ids present
twice. The gate is now `if mid:`; these tests pin it for both kinds.

The first test is the control (kind='message'); the second pins the CVE
ingest's kind ('consolidation'), which is the path that was broken.
"""

from __future__ import annotations

import tempfile


def _brain(d):
    from positronic_ai.brains import init_brain

    init_brain(d, "kairos", "balanced", "lexical")


def test_message_kind_dedupes_on_message_id():
    """Control: the dedup works -- for kind='message'."""
    from positronic_ai.ops.ingest import run

    with tempfile.TemporaryDirectory() as d:
        _brain(d)
        first = run(d, "hello world", message_id="<a@b.c>")
        assert first["encoded"] is True
        second = run(d, "hello world", message_id="<a@b.c>")
        assert second.get("duplicate") is True


def test_consolidation_kind_dedupes_on_message_id():
    """The CVE ingest's kind. message_id dedup must fire here too."""
    from positronic_ai.ops.ingest import run

    with tempfile.TemporaryDirectory() as d:
        _brain(d)
        first = run(d, "CVE-2024-0001 a summary.", kind="consolidation",
                    message_id="CVE-2024-0001@1")
        assert first["encoded"] is True
        second = run(d, "CVE-2024-0001 a summary.", kind="consolidation",
                     message_id="CVE-2024-0001@1")
        assert second.get("duplicate") is True
