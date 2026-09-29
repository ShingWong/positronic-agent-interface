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

import tempfile
from pathlib import Path

from positronic_ai.brains import init_brain
from positronic_ai.config import load_config, set_key
from positronic_ai.ops.ingest import run as ingest
from positronic_ai.ops.query import run as query

ROOT = Path(__file__).resolve().parents[1]


def _seed(dir):
    init_brain(dir, "kairos", "balanced", "lexical")


def test_config_defaults():
    with tempfile.TemporaryDirectory() as d:
        cfg = load_config(d)
        assert cfg["auto"] == {"consolidate_every": 0, "prune_every": 0}
        assert cfg["counters"] == {"since_consolidate": 0, "since_prune": 0}
        assert cfg["dedup"] is False


def test_set_key_auto_dedup():
    with tempfile.TemporaryDirectory() as d:
        set_key(d, "consolidate_every", 50)
        set_key(d, "prune_every", 400)
        set_key(d, "dedup", True)
        cfg = load_config(d)
        assert cfg["auto"]["consolidate_every"] == 50
        assert cfg["auto"]["prune_every"] == 400
        assert cfg["dedup"] is True


def test_ingest_dedup_skips_duplicate():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        set_key(d, "dedup", True)
        first = ingest(d, "the blue widget shipped on tuesday")
        assert first["encoded"] is True
        second = ingest(d, "the blue widget shipped on tuesday")
        assert second["duplicate"] is True and second["skipped"] is True
        distinct = ingest(d, "a totally different message")
        assert distinct["encoded"] is True
        rows = query(d, sql="SELECT COUNT(*) c FROM episode WHERE kind='message'")
        assert rows["results"][0]["c"] == 2


def test_ingest_no_dedup_without_flag():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        ingest(d, "repeat me")
        ingest(d, "repeat me")
        rows = query(d, sql="SELECT COUNT(*) c FROM episode WHERE kind='message'")
        assert rows["results"][0]["c"] == 2


def test_auto_consolidate_trigger_and_reset():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        set_key(d, "consolidate_every", 2)
        set_key(d, "prune_every", 0)
        ingest(d, "msg one")
        assert load_config(d)["counters"]["since_consolidate"] == 1
        ingest(d, "msg two")
        cfg = load_config(d)
        assert cfg["counters"]["since_consolidate"] == 0
        rows = query(d, sql="SELECT kind, COUNT(*) n FROM episode GROUP BY kind")
        kinds = {r["kind"]: r["n"] for r in rows["results"]}
        assert kinds.get("consolidation") == 1


def test_auto_prune_trigger_and_reset():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        set_key(d, "consolidate_every", 0)
        set_key(d, "prune_every", 2)
        ingest(d, "msg one")
        assert load_config(d)["counters"]["since_prune"] == 1
        ingest(d, "msg two")
        cfg = load_config(d)
        assert cfg["counters"]["since_prune"] == 0
        rows = query(d, sql="SELECT COUNT(*) c FROM episode WHERE kind='message'")
        assert rows["results"][0]["c"] == 2


def test_auto_disabled_at_zero():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        set_key(d, "consolidate_every", 0)
        set_key(d, "prune_every", 0)
        ingest(d, "msg one")
        cfg = load_config(d)
        assert cfg["counters"]["since_consolidate"] == 1
        assert cfg["counters"]["since_prune"] == 1


def test_init_sets_auto_flags():
    import os
    import subprocess
    import sys
    env = dict(os.environ)
    # Both positronic_ai and memeng are declared dependencies, so the inherited
    # environment already resolves them. Only this checkout is added, so the
    # subprocess exercises the tree under test. The two absolute entries this
    # replaces named one machine's checkout and sibling repo, and resolved to
    # nothing anywhere else.
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(ROOT), env.get("PYTHONPATH", "")) if p)
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run(
            [sys.executable, "-m", "positronic_ai", "init",
             "--brain", "kairos", "--profile", "balanced", "--embed", "lexical",
             "--auto-consolidate", "25", "--auto-prune", "500"],
            cwd=d, env=env, capture_output=True, text=True, check=False)
        assert r.returncode == 0, r.stderr
        cfg = load_config(d)
        assert cfg["auto"] == {"consolidate_every": 25, "prune_every": 500}

def test_ingest_role_tagged():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        ingest(d, "a user question", role="user")
        ingest(d, "an assistant answer", role="assistant")
        rows = query(d, sql="SELECT json_extract(features_json,'$.role') r FROM episode WHERE kind='message' ORDER BY tau")
        roles = [r["r"] for r in rows["results"]]
        assert roles == ["user", "assistant"]


def test_dedup_scoped_by_role():
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        set_key(d, "dedup", True)
        ingest(d, "same text", role="user")
        ingest(d, "same text", role="assistant")
        dup = ingest(d, "same text", role="user")
        assert dup["duplicate"] is True
        rows = query(d, sql="SELECT COUNT(*) c FROM episode WHERE kind='message'")
        assert rows["results"][0]["c"] == 2


def test_capture_user_default_off():
    with tempfile.TemporaryDirectory() as d:
        cfg = load_config(d)
        assert cfg["capture_user"] is False


def test_set_capture_user():
    with tempfile.TemporaryDirectory() as d:
        set_key(d, "capture_user", True)
        assert load_config(d)["capture_user"] is True
