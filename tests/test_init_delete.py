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