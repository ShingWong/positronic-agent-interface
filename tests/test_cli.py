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

"""CLI end-to-end (subprocess) + ops/config wrapper unit tests."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PY = sys.executable
ROOT = Path(__file__).resolve().parents[1]
ENGINE_SRC = "/usr/local/devel/positronic/positronic-engram/engine/src"


def _env():
    env = dict(os.environ)
    parts = [ENGINE_SRC, str(ROOT), env.get("PYTHONPATH", "")]
    env["PYTHONPATH"] = os.pathsep.join(p for p in parts if p)
    return env


def _run(dir_, *args):
    return subprocess.run([PY, "-m", "positronic_ai", *args], cwd=str(dir_),
                          env=_env(), capture_output=True, text=True)


def test_cli_init_creates_brain(tmp_path):
    r = _run(tmp_path, "init", "--brain", "kairos", "--profile", "balanced",
             "--embed", "lexical")
    assert r.returncode == 0, r.stderr
    assert (tmp_path / ".positronic" / "brains" / "kairos" / "memory.db").exists()


def test_cli_stats_json_contains_kairos(tmp_path):
    r = _run(tmp_path, "init", "--brain", "kairos", "--profile", "balanced",
             "--embed", "lexical")
    assert r.returncode == 0, r.stderr
    r = _run(tmp_path, "stats", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "kairos" in data["brains"]


def test_cli_config_live_true_regression(tmp_path):
    r = _run(tmp_path, "init", "--brain", "kairos", "--profile", "balanced",
             "--embed", "lexical")
    assert r.returncode == 0, r.stderr
    r = _run(tmp_path, "config", "live", "true", "--json")
    assert r.returncode == 0, r.stderr
    cfg = json.loads((tmp_path / ".positronic" / "config.json").read_text())
    assert cfg["live"] is True


def test_cli_unknown_verb_usage_on_stderr(tmp_path):
    r = _run(tmp_path, "badverb")
    assert r.returncode == 1
    assert "verbs" in r.stderr


def test_ops_config_get_masks_remote_key(tmp_path):
    from positronic_ai.ops.config import run as config_run
    config_run(tmp_path, key="remote_key", value="sk-secret")
    out = config_run(tmp_path)
    assert out["embed"]["remote_key"] == "***"


def test_ops_config_show_secrets_unmasks(tmp_path):
    from positronic_ai.ops.config import run as config_run
    config_run(tmp_path, key="remote_key", value="sk-secret")
    out = config_run(tmp_path, show_secrets=True)
    assert out["embed"]["remote_key"] == "sk-secret"


def test_ops_config_pii_path_blocked(tmp_path):
    from positronic_ai.ops.config import run as config_run
    with pytest.raises(ValueError):
        config_run(tmp_path, key="brain_henry/memory.db", value="x")


def test_ops_config_set_returns_changed(tmp_path):
    from positronic_ai.ops.config import run as config_run
    out = config_run(tmp_path, key="live", value="false")
    assert out["changed"] == ["live"]
    assert out["after"]["live"] is False