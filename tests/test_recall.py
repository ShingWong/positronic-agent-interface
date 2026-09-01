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

def _seed_two_brains(dir):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    init_brain(dir, "research", "balanced", "lexical")
    ingest(dir, "alpha memory incident", brain="kairos", arousal=0.5)
    ingest(dir, "beta memory incident", brain="research", arousal=0.5)

def test_recall_alpha_hits_kairos():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_two_brains(d)
        out = run(d, "alpha")
        assert any(h["brain"] == "kairos" for h in out["results"])
        hit = next(h for h in out["results"] if h["brain"] == "kairos")
        assert hit["episode_id"] and hit["tau"] is not None
        assert "rrf_score" in hit and "snippet" in hit

def test_recall_consolidation_mode():
    import tempfile

    from positronic_ai.brains import init_brain
    from positronic_ai.ops.consolidate import run as consolidate
    from positronic_ai.ops.ingest import run as ingest
    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        ingest(d, "memory alpha incident details", brain="kairos", arousal=0.5)
        consolidate(d, "alpha incident summary", brain="kairos", arousal=0.5)
        # 'only' → just the consolidation episode, no live message
        out = run(d, "alpha", consolidation="only")
        kinds = {h.get("kind") for h in out["results"]}
        assert kinds == {"consolidation"}
        assert any("summary" in (h.get("snippet") or "") for h in out["results"])
        # default → live message present (freshness wins), mode off by default
        outd = run(d, "alpha")
        kinds_d = {h.get("kind") for h in outd["results"]}
        assert "message" in kinds_d


def test_recall_beta_hits_research():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_two_brains(d)
        out = run(d, "beta")
        assert any(h["brain"] == "research" for h in out["results"])


def test_recall_shared_word_fuses_both_brains():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_two_brains(d)
        out = run(d, "memory")
        brains = {h["brain"] for h in out["results"]}
        assert brains == {"kairos", "research"}
        scores = [h["rrf_score"] for h in out["results"]]
        assert scores == sorted(scores, reverse=True)

def test_recall_brains_filter_and_empty():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_two_brains(d)
        out = run(d, "memory", brains=["research"])
        assert {h["brain"] for h in out["results"]} == {"research"}
        assert run(d, "") == {"results": []}

def _seed_ask(dir):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    ingest(dir, "deployed memory.db into the agent interface", arousal=0.5)

def test_ask_object_dossier():
    import tempfile

    from positronic_ai.ops.ask import run
    with tempfile.TemporaryDirectory() as d:
        _seed_ask(d)
        out = run(d, "memory.db")
        assert out["found"] is True
        assert out["object"]["canonical_name"] == "memory.db"
        assert len(out["sightings"]) >= 1
        assert out["sightings"][0]["episode_id"]

def test_ask_unknown_object():
    import tempfile

    from positronic_ai.ops.ask import run
    with tempfile.TemporaryDirectory() as d:
        _seed_ask(d)
        assert run(d, "nonexistent-xyz") == {"object": None,
                                             "sightings": [], "found": False}

def _seed_wake(dir):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.consolidate import run as consolidate
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    ingest(dir, "epsilon anchor memory marker persists", arousal=1.0)
    consolidate(dir, "session compacted de9a2c", arousal=0.4)

def test_wake_brief():
    import tempfile

    from positronic_ai.ops.wake import run
    with tempfile.TemporaryDirectory() as d:
        _seed_wake(d)
        out = run(d)
        assert out["brief"] and isinstance(out["brief"], str)
        assert "anchors:" in out["brief"]
        assert "consolidated today:" in out["brief"]


def _seed_recall_digest(dir):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.consolidate import run as consolidate
    from positronic_ai.ops.ingest import run as ingest
    init_brain(dir, "kairos", "balanced", "lexical")
    ingest(dir, "deployed memory.db into the agent interface", arousal=0.5)
    consolidate(dir, "digest: memory.db deploy shipped and verified", arousal=0.4)

def test_recall_matching_cue_returns_polytemporal_digest():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_recall_digest(d)
        out = run(d, "memory.db")
        assert out["results"]                       # live episodes still present
        obj = out["object"]
        assert obj["canonical_name"] == "memory.db"
        v = obj["versions"]
        assert v["sighting_count"] >= 2
        assert v["tau_span"][0] < v["tau_span"][1]
        assert v["oldest_tau"] == v["tau_span"][0]
        assert "memory.db" in v["latest_consolidation"]

def test_recall_nonmatching_cue_has_no_object_block():
    import tempfile

    from positronic_ai.ops.recall import run
    with tempfile.TemporaryDirectory() as d:
        _seed_recall_digest(d)
        out = run(d, "zzz-nonexistent-qqq")
        assert "object" not in out