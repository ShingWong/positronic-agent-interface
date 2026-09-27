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
# proprietary Commercial License Waiver issued by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org/>.
# =====================================================================

# tests/test_isolation.py — brain isolation: one served brain, no fan-out.
# These guard the cross-brain leak fix: a read that reaches a second brain is
# the failure mode, and "no crash" style assertions would pass with the leak
# still present, so each test pins an observable cross-brain fact.
import json

import pytest
from fastapi.testclient import TestClient

from positronic_ai.brains import init_brain
from positronic_ai.engine import open_engine
from positronic_ai.ops import ask as ask_op
from positronic_ai.server import app as srv

MAIL = "postronic"
OTHER = "henry"


def _seed_object(project_dir: str, brain: str, name: str, marker: str) -> None:
    """Give one brain a same-named object whose sighting carries a marker.

    Rows are written directly (as tests/test_objects.py does) so the two brains
    hold byte-identical object names and only the marker differs — which is
    what makes a cross-brain sighting detectable.
    """
    from positronic_ai.ops.ingest import run as ingest

    ingest(project_dir, f"observation body {marker}", brain=brain)
    s, _ = open_engine(project_dir, brain)
    eid = s.conn.execute(
        "SELECT id FROM episode ORDER BY tau DESC LIMIT 1").fetchone()["id"]
    oid = s.conn.execute("SELECT lower(hex(randomblob(16)))").fetchone()[0]
    s.conn.execute(
        "INSERT INTO object(id, canonical_name, kind, domain_id, status, "
        "salience, first_seen_tau, last_seen_tau) "
        "VALUES (?, ?, 'entity', 1, 'active', 0.5, 10.0, 10.0)", (oid, name))
    s.conn.execute(
        "INSERT INTO object_sighting (object_id, episode_id, channel, "
        "confidence) VALUES (?, ?, 'extract', 1.0)", (oid, eid))
    s.conn.execute(
        "UPDATE episode SET features_json = json_set(features_json, "
        "'$.body_text', ?) WHERE id = ?", (marker, eid))
    s.conn.commit()


def _bodies(project_dir: str, brain: str) -> list[str]:
    s, _ = open_engine(project_dir, brain)
    return [json.loads(r["features_json"]).get("body_text")
            for r in s.conn.execute("SELECT features_json FROM episode "
                                    "WHERE kind='message'").fetchall()]


@pytest.fixture
def two_brains(tmp_path, monkeypatch):
    d = str(tmp_path)
    init_brain(d, MAIL, "balanced", "lexical")
    init_brain(d, OTHER, "balanced", "lexical")
    monkeypatch.setattr(srv, "PROJECT_DIR", d)
    monkeypatch.setattr(srv, "MAIL_BRAIN", MAIL, raising=False)
    monkeypatch.setattr(srv, "MAIL_BRAIN_MISCONFIGURED", False, raising=False)
    _seed_object(d, MAIL, "shared-object", "from-mail-brain")
    _seed_object(d, OTHER, "shared-object", "from-other-brain")
    return d


# --- the pin: /ask must not reach the second brain ------------------------

def test_ask_pinned_never_returns_the_other_brain(two_brains):
    client = TestClient(srv.app)
    r = client.post("/ask", json={"object_name": "shared-object"})
    assert r.status_code == 200
    out = r.json()
    assert out["found"] is True
    assert out["sightings"], "the served brain's own object must still resolve"
    bodies = " ".join(s.get("body_text") or "" for s in out["sightings"])
    assert "from-mail-brain" in bodies
    assert "from-other-brain" not in bodies


def test_ask_pinned_ignores_a_client_supplied_brain(two_brains):
    client = TestClient(srv.app)
    r = client.post("/ask", json={"object_name": "shared-object",
                                  "brains": [OTHER]})
    assert "from-other-brain" not in r.text


def test_other_brain_really_does_hold_the_marker(two_brains):
    """Guards the two tests above: if seeding broke, they would pass anyway."""
    assert "from-other-brain" in _bodies(two_brains, OTHER)
    assert "from-mail-brain" in _bodies(two_brains, MAIL)


# --- an empty brain list means "read none", not "read all" ----------------

def test_empty_brain_list_is_fail_closed(two_brains):
    out = ask_op.run(two_brains, "shared-object", brains=[])
    assert out["found"] is False
    assert out["sightings"] == []


def test_brains_none_still_means_no_filter(two_brains):
    """The unpinned path is unchanged: None searches every brain, an explicit
    list is a restriction. Only the mail brain has the object below."""
    _seed_object(two_brains, OTHER, "other-only-object", "from-other-brain")
    assert ask_op.run(two_brains, "other-only-object",
                      brains=None)["found"] is True
    assert ask_op.run(two_brains, "other-only-object",
                      brains=[MAIL])["found"] is False


# --- a pin that is set but unusable must not silently open every brain ----

@pytest.mark.parametrize("raw", ["---", "???", "   ", ""])
def test_misconfigured_pin_refuses_rather_than_fanning_out(two_brains,
                                                           monkeypatch, raw):
    monkeypatch.setattr(srv, "MAIL_BRAIN", None, raising=False)
    monkeypatch.setattr(srv, "MAIL_BRAIN_RAW", raw, raising=False)
    monkeypatch.setattr(srv, "MAIL_BRAIN_MISCONFIGURED", bool(raw),
                        raising=False)
    client = TestClient(srv.app)
    r = client.post("/ask", json={"object_name": "shared-object"})
    assert r.status_code == 200
    out = r.json()
    if raw:
        assert out["found"] is False
        assert "misconfigured" in out["error"]
        assert "from-other-brain" not in r.text
    else:
        # unset is a legitimate unpinned deployment: fan-out is intended
        assert out["found"] is True


@pytest.mark.parametrize("path,payload", [
    ("/recall", {"text": "shared"}),
    ("/query", {"text": "shared"}),
    ("/ask", {"object_name": "shared-object"}),
    ("/brain-test", {}),
])
def test_every_read_endpoint_refuses_a_misconfigured_pin(two_brains, monkeypatch,
                                                        path, payload):
    monkeypatch.setattr(srv, "MAIL_BRAIN", None, raising=False)
    monkeypatch.setattr(srv, "MAIL_BRAIN_MISCONFIGURED", True, raising=False)
    r = TestClient(srv.app).post(path, json=payload)
    assert r.status_code == 200
    assert r.json().get("error") == "mail brain misconfigured", path


@pytest.mark.parametrize("method,path", [("get", "/info"), ("get", "/stats")])
def test_disclosure_endpoints_refuse_a_misconfigured_pin(two_brains, monkeypatch,
                                                        method, path):
    monkeypatch.setattr(srv, "MAIL_BRAIN", None, raising=False)
    monkeypatch.setattr(srv, "MAIL_BRAIN_MISCONFIGURED", True, raising=False)
    r = getattr(TestClient(srv.app), method)(path)
    assert r.json().get("error") == "mail brain misconfigured", path
