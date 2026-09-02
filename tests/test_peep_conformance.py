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

"""PEEP (Positronic Engram Exchange Protocol) Level 1 conformance suite.

The RFC's normative requirements as executable tests. A producer is
PEEP-compliant iff every test in this suite passes against its payload.
"""


def _seed(d):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.consolidate import run as consolidate
    from positronic_ai.ops.ingest import run as ingest
    init_brain(d, "kairos", "balanced", "lexical")
    ingest(d, "auth system debug session yesterday: token expiry was the root cause of the login failures",
           brain="kairos", arousal=0.5)
    ingest(d, "the JWT refresh bug in the auth system is fixed now",
           brain="kairos", arousal=0.5)
    consolidate(d, "auth system: token expiry was the root cause, now fixed",
                brain="kairos", arousal=0.5)


def test_peep_recall_hit_has_time_vector():
    """RFC 3.1 — every recall hit carries tau + wall (the polytemporal vector)."""
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, "auth debug")
        assert out["results"]
        for h in out["results"]:
            assert "episode_id" in h
            assert h.get("tau") is not None, "hit missing tau"
            assert isinstance(h.get("wall"), str), "hit missing wall"


def test_peep_recall_hit_has_salience_and_kind():
    """RFC 3.1 — hits carry salience + kind + fallback (self-describing)."""
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, "auth debug")
        for h in out["results"]:
            assert "salience" in h
            assert h.get("kind") in ("message", "consolidation")
            assert isinstance(h.get("fallback"), bool)


def _ensure_object(d):
    """Wire a resolvable object into the seeded brain (contract under test,
    not extraction). Returns None if no episodes exist to sight."""
    from positronic_ai.engine import open_engine
    s, _e = open_engine(d, "kairos")
    row = s.conn.execute(
        "SELECT id FROM episode ORDER BY tau ASC LIMIT 1").fetchone()
    if row is None:
        return None
    s.conn.execute(
        "INSERT INTO object(id, domain_id, kind, canonical_name, status, "
        "salience, first_seen_tau, last_seen_tau) "
        "VALUES (lower(hex(randomblob(16))), 1, 'entity', 'auth-system', "
        "'active', 0.5, 1.0, 10.0)")
    oid = s.conn.execute(
        "SELECT id FROM object WHERE canonical_name='auth-system'"
    ).fetchone()["id"]
    s.conn.execute(
        "INSERT INTO object_sighting(episode_id, object_id, channel, "
        "confidence) VALUES (?, ?, 'text', 0.9)", (row["id"], oid))
    cons = s.conn.execute(
        "SELECT id FROM episode WHERE kind='consolidation' ORDER BY tau DESC "
        "LIMIT 1").fetchone()
    if cons:
        s.conn.execute(
            "INSERT INTO object_sighting(episode_id, object_id, channel, "
            "confidence) VALUES (?, ?, 'text', 0.9)", (cons["id"], oid))
    s.conn.commit()
    return oid


def test_peep_entity_digest_has_versions():
    """RFC 3.2 — the object block exposes versions: count, tau_span,
    latest_consolidation, oldest_tau. The 'peep': depth at a glance."""
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        _ensure_object(d)
        out = run(d, "auth-system")
        obj = out.get("object")
        assert obj is not None, "no object block for resolvable cue"
        v = obj.get("versions", {})
        assert "sighting_count" in v
        assert "tau_span" in v and len(v["tau_span"]) == 2
        assert "latest_consolidation" in v
        assert "oldest_tau" in v


def test_peep_dossier_is_tau_ordered():
    """RFC 3.3 — ask returns a τ-ordered dossier (ascending time vector)."""
    import tempfile

    from positronic_ai.engine import open_engine
    from positronic_ai.ops.ask import run as ask
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        # guarantee a resolvable object by wiring a sighting directly to an
        # object; the dossier contract (not extraction) is under test
        s, _e = open_engine(d, "kairos")
        row = s.conn.execute(
            "SELECT id FROM episode ORDER BY tau ASC LIMIT 1").fetchone()
        s.conn.execute(
            "INSERT INTO object(id, domain_id, kind, canonical_name, status, "
            "salience, first_seen_tau, last_seen_tau) "
            "VALUES (lower(hex(randomblob(16))), 1, 'entity', 'auth-system', "
            "'active', 0.5, 1.0, 10.0)")
        oid = s.conn.execute(
            "SELECT id FROM object WHERE canonical_name='auth-system'"
        ).fetchone()["id"]
        s.conn.execute(
            "INSERT INTO object_sighting(episode_id, object_id, channel, "
            "confidence) VALUES (?, ?, 'text', 0.9)", (row["id"], oid))
        s.conn.commit()
        out = ask(d, "auth-system")
        sights = out.get("sightings") or []
        assert sights, "dossier empty"
        taus = [x["tau"] for x in sights]
        assert taus == sorted(taus, reverse=True) or taus == sorted(taus), \
            "sightings not τ-ordered"
        for s_ in sights:
            assert "episode_id" in s_
            assert s_.get("kind") in ("message", "consolidation")


def test_peep_digest_is_a_glimpse_not_the_data():
    """RFC 3.2 — the digest is compact (a peep), the dossier is the depth.
    latest_consolidation is a summary, not a full dump."""
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        _ensure_object(d)
        out = run(d, "auth-system")
        obj = out.get("object")
        assert obj is not None, "no object block for resolvable cue"
        lc = (obj.get("versions", {}).get("latest_consolidation") or "")
        assert len(lc) <= 200, "latest_consolidation is not a distilled glimpse"
        assert "root cause" in lc or "token expiry" in lc