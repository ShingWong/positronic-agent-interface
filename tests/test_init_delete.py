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

from positronic_ai.config import load_config
from positronic_ai.ops.delete import run as delete_run
from positronic_ai.ops.init import run as init_run
from positronic_ai.wizard import init_run as wizard_init_run

BRAIN = {"name": "kairos", "profile": "balanced", "embed": "lexical"}


def test_init_creates_brain_db_and_config():
    with tempfile.TemporaryDirectory() as d:
        out = wizard_init_run(d, brains=[BRAIN])
        assert out["ok"] is True
        assert out["created"] == ["kairos"]
        assert (Path(d) / ".positronic" / "brains" / "kairos" / "memory.db").exists()
        assert "kairos" in load_config(d)["brains"]
        assert out["live"] is True


def test_init_existing_without_force_warns():
    with tempfile.TemporaryDirectory() as d:
        wizard_init_run(d, brains=[BRAIN])
        out = wizard_init_run(d, brains=[BRAIN])
        assert out["ok"] is False
        assert out["existing"] == ["kairos"]
        assert "OVERWRITTEN" in out["warning"]


def test_init_no_brains_returns_help():
    with tempfile.TemporaryDirectory() as d:
        out = wizard_init_run(d)
        assert out["ok"] is False
        assert "Pick how your brain remembers" in out["warning"]
        assert "balanced" in out["warning"]
        assert "lexical" in out["warning"]


def test_ops_init_delegates_to_wizard():
    with tempfile.TemporaryDirectory() as d:
        out = init_run(d, brains=[BRAIN])
        assert out["ok"] is True
        assert out["created"] == ["kairos"]
        assert (Path(d) / ".positronic" / "brains" / "kairos" / "memory.db").exists()


def test_delete_requires_force():
    with tempfile.TemporaryDirectory() as d:
        wizard_init_run(d, brains=[BRAIN])
        out = delete_run(d, brain="kairos")
        assert out["ok"] is False
        assert "PERMANENTLY delete" in out["warning"]


def test_delete_force_removes_brain():
    with tempfile.TemporaryDirectory() as d:
        wizard_init_run(d, brains=[BRAIN])
        out = delete_run(d, brain="kairos", force=True)
        assert out["ok"] is True
        assert out["deleted"] == "kairos"
        assert not (Path(d) / ".positronic" / "brains" / "kairos").exists()
        assert "kairos" not in load_config(d)["brains"]


def test_delete_no_brain_returns_help():
    with tempfile.TemporaryDirectory() as d:
        out = delete_run(d)
        assert out["ok"] is False
        assert "Usage: /positronic:delete" in out["warning"]


def test_delete_unknown_brain_warns():
    with tempfile.TemporaryDirectory() as d:
        out = delete_run(d, brain="ghost", force=True)
        assert out["ok"] is False
        assert "No brain named" in out["warning"]

def test_init_from_db_adopts_store_intact():
    """The adopted brain answers from the source's episodes, and the source
    file is untouched (copied, never moved)."""
    import os

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.query import run as query
    with tempfile.TemporaryDirectory() as d, \
            tempfile.TemporaryDirectory() as src:
        init_brain(src, "donor", "balanced", "lexical")
        from positronic_ai.ops.ingest import run as ingest
        ingest(src, "adopted brain probe event alpha")
        before = os.path.getsize(
            os.path.join(src, ".positronic", "brains", "donor", "memory.db"))
        out = wizard_init_run(d, brains=[{**BRAIN,
                                          "from_db": os.path.join(
                                              src, ".positronic", "brains",
                                              "donor", "memory.db")}])
        assert out["ok"] is True
        assert out["created"] == ["kairos"]
        after = os.path.getsize(
            os.path.join(src, ".positronic", "brains", "donor", "memory.db"))
        assert before == after
        q = query(d, text="adopted brain probe")
        assert q["hits"] >= 1


def test_init_from_db_rejects_non_store(tmp_path):
    """A random sqlite file must not become a brain that fails on first
    query: rejected at adopt time, with nothing registered."""
    import sqlite3

    bogus = tmp_path / "bogus.db"
    c = sqlite3.connect(str(bogus))
    c.execute("CREATE TABLE other(x)")
    c.commit()
    c.close()
    import pytest

    with pytest.raises(ValueError, match="no episode table"):
        wizard_init_run(str(tmp_path),
                        brains=[{**BRAIN, "from_db": str(bogus)}])
    from positronic_ai.config import load_config
    assert "kairos" not in load_config(str(tmp_path)).get("brains", {})


def test_init_from_db_rejects_missing_file(tmp_path):
    import pytest

    with pytest.raises(ValueError, match="not a readable sqlite"):
        wizard_init_run(str(tmp_path),
                        brains=[{**BRAIN,
                                 "from_db": str(tmp_path / "nope.db")}])
