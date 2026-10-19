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

"""The message_id dedup is gated on kind, and the CVE ingest uses another kind.

`ops.ingest.run()` only consults `_dup_result` when `kind == "message"`:

    mid = normalize_message_id(message_id)
    if kind == "message" and mid:
        dup = _dup_result(s.conn, mid)

but `scripts/ingest_cve_brain.py` calls `run(..., kind="consolidation",
message_id=mid)` and depends on that dedup for idempotency -- its own comment
says passing the id "is what actually records it and **arms `_dup_result`**".
It records the id in features_json; it never checks it.

Measured on the production brain (`iStrix-cve`, 2026-10-11 run): the ingest
logged `new=156725 dup-skip=0 resumed-skip=32676` over 189,401 records -- the
brain dedup never fired once. The only dedup that worked was the done-file
ledger, and the script's safety argument for it ("a crash must leave the DB
AHEAD of the done-file (resume re-attempts and **dedupes**), never behind it")
therefore does not hold: a crash between `commit_batch()` and the ledger write
duplicates up to `--batch` (64) records.

The brain shows the accumulated cost: 191,280 episodes for 189,401 records,
34,155 of them with no `message_id` at all (the pre-2026-10-11 code path
shelled out to `consolidate`, which "takes no message_id ... so it was
silently dropped and never stored"), and 1,106 CVE ids present twice -- once
without a message_id and once with. Those pairs are invisible to
`_dup_result`, which can only match rows that have one.

The second test is the control: it proves the dedup works for
`kind="message"`, so the gap is the kind gate and not the query.
"""

from __future__ import annotations

import tempfile

import pytest


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


@pytest.mark.xfail(
    strict=True,
    reason="DEFECT: kind='consolidation' bypasses _dup_result; fix, then drop xfail",
)
def test_consolidation_kind_does_not_dedupe_on_message_id():
    """The CVE ingest's kind. It records message_id and never checks it."""
    from positronic_ai.ops.ingest import run

    with tempfile.TemporaryDirectory() as d:
        _brain(d)
        first = run(d, "CVE-2024-0001 a summary.", kind="consolidation",
                    message_id="CVE-2024-0001@1")
        assert first["encoded"] is True
        second = run(d, "CVE-2024-0001 a summary.", kind="consolidation",
                     message_id="CVE-2024-0001@1")
        assert second.get("duplicate") is True
