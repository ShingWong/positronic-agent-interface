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

"""Polytemporal object dossier tests — sightings/digest must surface body_text
even when the legacy subject_norm column is NULL (early episodes stored text
in features_json.body_text only)."""


def _seed_object_with_null_subject(d):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine
    from positronic_ai.ops.ingest import run as ingest

    init_brain(d, "kairos", "balanced", "lexical")
    ingest(d, "08fcde5 README pitch tensor-grounded memory", brain="kairos",
           arousal=0.5)
    s, _e = open_engine(d, "kairos")
    # simulate an early episode: subject_norm NULL, text only in features_json
    row = s.conn.execute(
        "SELECT id FROM episode ORDER BY tau DESC LIMIT 1").fetchone()
    s.conn.execute(
        "UPDATE episode SET subject_norm=NULL, "
        "features_json=json_object('body_text', "
        "'polytemporal tensor-grounded pitch committed 08fcde5 on beta') "
        "WHERE id=?", (row["id"],))
    s.conn.commit()
    # the object the message linked to (entity extraction names it whatever
    # the body produced — here 'tensor-grounded')
    obj = s.conn.execute(
        "SELECT o.id FROM object_sighting os JOIN object o ON o.id=os.object_id "
        "WHERE os.episode_id=? LIMIT 1", (row["id"],)).fetchone()
    return s, row["id"], obj["id"]


def test_object_sightings_surfaces_body_text_when_subject_null():
    import tempfile

    from positronic_ai.objects import object_sightings
    with tempfile.TemporaryDirectory() as d:
        s, eid, oid = _seed_object_with_null_subject(d)
        sights = object_sightings(s, oid)
        assert any(x["episode_id"] == eid for x in sights)
        hit = next(x for x in sights if x["episode_id"] == eid)
        assert hit["subject_norm"] is None
        assert "08fcde5" in hit["body_text"]


def test_object_digest_latest_consolidation_uses_body_text():
    import tempfile

    from positronic_ai.objects import object_digest
    with tempfile.TemporaryDirectory() as d:
        s, eid, oid = _seed_object_with_null_subject(d)
        s.conn.execute(
            "UPDATE episode SET kind='consolidation' WHERE id=?", (eid,))
        s.conn.commit()
        digest = object_digest(s, oid)
        assert "08fcde5" in digest["latest_consolidation"]