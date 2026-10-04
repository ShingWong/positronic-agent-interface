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

def _seed(dir, n=3):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    events = [
        ("deploy positronic query engine v0", 0.4),
        ("epsilon anchor memory marker persists", 1.0),
        ("gamma followup event", 0.5),
    ]
    for text, arousal in events[:n]:
        ingest(dir, text, arousal=arousal)
    return events[:n]

def test_query_text_returns_hit():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, text="epsilon")
        assert out["ok"] is True and out["brain"] == "kairos"
        assert out["hits"] == 1 and isinstance(out["ms"], float)
        assert out["results"][0]["episode_id"]

def test_query_sql_count():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d, n=3)
        out = run(d, sql="SELECT COUNT(*) c FROM episode")
        assert out["ok"] is True and out["results"] == [{"c": 3}]

def test_query_anchors():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d)
        out = run(d, anchors=True)
        assert out["ok"] is True
        assert isinstance(out["results"], list)
        assert len(out["results"]) >= 1
        assert "sn" in out["results"][0]

def test_query_missing_brain():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        out = run(d, text="anything")
        assert out["ok"] is False and "no such brain db" in out["error"]
def _seed_object(d):
    """Two episodes about one session identity, via the engine directly:
    PAI ingest writes no objects, and recall_object needs one to find."""
    from datetime import datetime, timezone

    from memeng.models import Event

    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine
    init_brain(d, "kairos", "balanced", "lexical")
    _s, e = open_engine(d, "kairos")
    # Maximally distinct: near-identical texts would be gate-rejected on
    # novelty, which is correct gate behavior and not this test's subject.
    for i, txt in enumerate(("zebra invoice reconciled at midnight",
                             "quarry siren tested before dawn")):
        e.new_event(Event(
            stream="kairos:in", kind="message",
            wall=datetime(2026, 5, 1 + i, tzinfo=timezone.utc),
            persons=[], objects=[("session", "s:1")],
            features={"subject_norm": txt, "body_text": txt,
                      "arousal": 0.0}))

def test_query_object_life_oldest_first():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_object(d)
        out = run(d, object_ref="session:s:1")
        assert out["ok"] is True and out["found"] is True
        assert out["canonical"] == "s:1"
        assert len(out["episodes"]) == 2
        assert out["episodes"][0]["wall"] < out["episodes"][1]["wall"]
        assert "2 episodes" in out["human"]

def test_query_object_unknown_is_fact_not_error():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_object(d)
        out = run(d, object_ref="message:queue:NOPE")
        assert out["ok"] is True and out["found"] is False
        assert out["episodes"] == []
        assert "unknown identity" in out["human"]

def test_query_object_bare_name_rejected():
    """No kind means guessing which dossier to open -- fail loud."""
    import tempfile

    import pytest

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_object(d)
        with pytest.raises(ValueError, match="kind:canonical"):
            run(d, object_ref="bare-name-with-no-kind")

def test_query_range_window_and_bounds():
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed(d, n=3)
        out = run(d, range_=True)
        assert out["ok"] is True and len(out["results"]) == 3
        walls = [r["wall"] for r in out["results"]]
        assert walls == sorted(walls), "a window is a narrative: oldest first"
        assert run(d, range_=True, since="2999-01-01")["results"] == []
        assert run(d, range_=True, until="2000-01-01")["results"] == []


def _seed_aliases(d):
    """Two similarly-named sessions plus an unrelated one, all distinct
    enough to encode side by side."""
    from datetime import datetime, timezone

    from memeng.models import Event

    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine
    init_brain(d, "kairos", "balanced", "lexical")
    _s, e = open_engine(d, "kairos")
    notes = (("backup-mx1", "zebra invoice reconciled at midnight"),
             ("backup-mx2", "quarry siren tested before dawn"),
             ("lighthouse-log", "harbor manifest sealed at noon"))
    for i, (canon, txt) in enumerate(notes):
        e.new_event(Event(
            stream="kairos:in", kind="message",
            wall=datetime(2026, 5, 1 + i, tzinfo=timezone.utc),
            persons=[], objects=[("session", canon)],
            features={"subject_norm": txt, "body_text": txt,
                      "arousal": 0.0}))

def test_query_object_substring_resolves_single(tmp_path):
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_aliases(d)
        out = run(d, object_ref="session:lighthouse")
        assert out["ok"] is True and out["found"] is True
        assert out["canonical"] == "lighthouse-log"
        assert out["resolved_from"] == "session:lighthouse"
        assert "resolved" in out["human"]

def test_query_object_ambiguous_lists_candidates(tmp_path):
    """Two matches open neither dossier: the caller picks, the tool lists."""
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_aliases(d)
        out = run(d, object_ref="session:backup")
        assert out["ok"] is True and out["found"] is False
        got = {(c["kind"], c["canonical"]) for c in out["candidates"]}
        assert got == {("session", "backup-mx1"),
                       ("session", "backup-mx2")}
        assert "did you mean" in out["human"]
        assert out["episodes"] == []

def test_query_object_wrong_kind_suggests_across_kinds(tmp_path):
    """The kind itself may be misremembered: no message matches, but the
    session does -- suggest it, still open nothing."""
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_aliases(d)
        out = run(d, object_ref="message:backup-mx1")
        assert out["ok"] is True and out["found"] is False
        assert any(c == {"kind": "session", "canonical": "backup-mx1"}
                   for c in out["candidates"])
        assert "did you mean" in out["human"]

def test_query_object_midword_never_matches(tmp_path):
    """'ack' must not hit 'backup-mx1': the boundary rule holds for the
    candidate list exactly as for resolve_object."""
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_aliases(d)
        out = run(d, object_ref="session:ack")
        assert out["found"] is False
        assert out.get("candidates") == []


def test_query_object_pid_suffix_resolves(tmp_path):
    """Log identities are ident:pid; the pid after the colon IS the token
    operators search by, so ':' must be a boundary. Tightening the boundary
    back to whitespace-only silently breaks the primary diagnostic lookup."""
    import tempfile

    from positronic_ai.ops.query import run
    with tempfile.TemporaryDirectory() as d:
        _seed_object(d)
        out = run(d, object_ref="session:s:1")
        assert out["ok"] is True and out["found"] is True
        out2 = run(d, object_ref="session:1")
        assert out2["ok"] is True and out2["found"] is True
        assert out2["canonical"] == "s:1"
        assert out2["resolved_from"] == "session:1"
