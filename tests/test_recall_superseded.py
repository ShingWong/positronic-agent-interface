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

"""Recall honors the dedup reconcile mark: superseded episodes are not
retrievable, and the coverage count (total = top-k of how many FTS matches)
only counts live rows.

The 2026-10-19 CVE reconcile marked 1,877 legacy duplicate copies
(features_json.superseded_by) without deleting them — archival never
forgets. Marked copies share near-identical text with their canonical
row, so unfiltered recall burns top-k slots on dead copies: k=3 with two
dead copies left one informative hit. Measured on the live iStrix-cve
brain; pinned here at the recall surface.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile


def _brain(d):
    from positronic_ai.brains import init_brain
    init_brain(d, "kairos", "balanced", "lexical")


def _seed_pair(d):
    """Two near-identical consolidation episodes; mark the second dead."""
    from positronic_ai.ops.ingest import run as ingest
    live = ingest(d, "zanzibar quokka finding summary",
                  kind="consolidation", message_id="m1")
    dead = ingest(d, "zanzibar quokka finding summary stale copy",
                  kind="consolidation", message_id="m2")
    db = sqlite3.connect(f"{d}/.positronic/brains/kairos/memory.db")
    db.execute(
        "UPDATE episode SET features_json=json_set(features_json,"
        "'$.superseded_by',?) WHERE id=?",
        (live["episode_id"], dead["episode_id"]))
    db.commit()
    db.close()
    return live["episode_id"], dead["episode_id"]


def test_recall_excludes_superseded_and_counts_live_only():
    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _brain(d)
        live_id, dead_id = _seed_pair(d)
        out = run(d, "zanzibar quokka")
        ids = [h["episode_id"] for h in out["results"]]
        assert dead_id not in ids
        assert live_id in ids
        assert out["total"] == 1


def test_exhaustive_merge_excludes_superseded():
    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _brain(d)
        live_id, dead_id = _seed_pair(d)
        out = run(d, "zanzibar quokka", exhaustive=True)
        ids = [h["episode_id"] for h in out["results"]]
        assert dead_id not in ids
        assert live_id in ids
