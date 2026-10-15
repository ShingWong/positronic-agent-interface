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

"""Doctor verb — the bge tier must probe the project's embed.local_url.

The tier used to hardcode http://127.0.0.1:8090/health, so a brain pointed at
a LAN embedding server reported "down" while every encode worked. These tests
pin the probe to the configured URL, the localhost default, the multi-URL
fallback list and the POSITRONIC_BGE_URL override.
"""
import json

import positronic_ai
from positronic_ai.ops import doctor

HEALTH_OK = json.dumps({"status": "ok"}).encode()


class _Resp:
    def __init__(self, payload: bytes = HEALTH_OK):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _project(tmp_path, local_url: str):
    """A real project: init a brain, then point embed.local_url at `local_url`."""
    from positronic_ai.brains import init_brain
    init_brain(tmp_path, "sure-mail", "long_term", "local")
    cfg_path = tmp_path / ".positronic" / "config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["embed"]["local_url"] = local_url
    cfg_path.write_text(json.dumps(cfg))
    return cfg


def _record(monkeypatch, ok=True):
    """Patch urlopen to log every probed URL; answer ok or refuse."""
    seen: list[str] = []

    def fake(url, timeout=None, *args, **kwargs):
        seen.append(url)
        if not ok:
            raise OSError("connection refused")
        return _Resp()

    monkeypatch.setattr(doctor.urllib.request, "urlopen", fake)
    return seen


def test_bge_probes_configured_local_url(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    _project(tmp_path, "http://10.0.0.19:8090")
    seen = _record(monkeypatch)
    assert doctor.run(tmp_path)["tiers"]["bge"] == "ok"
    assert seen == ["http://10.0.0.19:8090/health"]


def test_bge_down_when_configured_server_is_down(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    _project(tmp_path, "http://10.0.0.19:8091")
    _record(monkeypatch, ok=False)
    assert doctor._bge(tmp_path) == "down"


def test_bge_walks_the_configured_url_list(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    _project(tmp_path, "http://10.0.0.19:8091, http://10.0.0.19:8090")
    seen: list[str] = []
    answers = {"http://10.0.0.19:8091/health": False, "http://10.0.0.19:8090/health": True}

    def fake(url, timeout=None, *args, **kwargs):
        seen.append(url)
        if not answers.get(url):
            raise OSError("connection refused")
        return _Resp()

    monkeypatch.setattr(doctor.urllib.request, "urlopen", fake)
    assert doctor._bge(tmp_path) == "ok"
    assert seen == ["http://10.0.0.19:8091/health", "http://10.0.0.19:8090/health"]


def test_bge_defaults_to_localhost_without_a_project(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    seen = _record(monkeypatch)
    assert doctor.run(None)["tiers"]["bge"] == "ok"
    assert seen == ["http://127.0.0.1:8090/health"]


def test_bge_env_override_wins(tmp_path, monkeypatch):
    _project(tmp_path, "http://10.0.0.19:8090")
    monkeypatch.setenv("POSITRONIC_BGE_URL", "http://elsewhere:9090")
    seen = _record(monkeypatch)
    assert doctor._bge(tmp_path) == "ok"
    assert seen == ["http://elsewhere:9090/health"]


def test_bge_health_url_keeps_an_explicit_health_path(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    _project(tmp_path, "http://10.0.0.19:8090/health")
    seen = _record(monkeypatch)
    assert doctor._bge(tmp_path) == "ok"
    assert seen == ["http://10.0.0.19:8090/health"]


def test_llm_stat_reads_the_project_config(tmp_path, monkeypatch):
    monkeypatch.delenv("POSITRONIC_BGE_URL", raising=False)
    _project(tmp_path, "http://10.0.0.19:8090")
    seen = _record(monkeypatch)
    out = positronic_ai.ops.llm_stat.run(tmp_path)
    assert set(out) == {"bge", "llama", "lexical", "engram", "pooling"}
    assert out["bge"] == "ok"
    assert out["pooling"] == "cls"
    assert seen == ["http://10.0.0.19:8090/health"]
