"""Embedding profiles: a brain picks its model, and cannot drift out of sync.

Two properties are load-bearing and both are asserted here rather than
assumed:

1. The DEFAULT preserves today's behaviour exactly. `bge-m3` takes no task
   prompts, so existing brains embed byte-for-byte as before and published
   benchmark numbers stay comparable.
2. A brain cannot end up querying a vector space it was not embedded into.
   The profile is stamped into the brain's own meta table and read back by
   the query path, and a mismatch raises instead of silently degrading --
   which would otherwise look like a weak model rather than a config error.
"""
import struct

import pytest

from positronic_ai.embed import (DEFAULT_EMBED_MODEL, EMBED_MODELS,
                                 known_models, model_dim, prompt_prefix)
from positronic_ai.engine import (EMBED_PROFILE_KEY, embedder_for,
                                  embed_profile)
from memeng.store import SQLiteStore


def test_default_model_is_bge_m3():
    """Back-compat: the default must not change any existing brain."""
    assert DEFAULT_EMBED_MODEL == "bge-m3"


def test_default_model_takes_no_prompts():
    assert prompt_prefix("bge-m3", "document") == ""
    assert prompt_prefix("bge-m3", "query") == ""


def test_eg2_uses_the_searchquery_document_pair():
    """EG2 is trained on this pair; getting it wrong looks like a weak model."""
    assert prompt_prefix("eg2", "document") == "Document: "
    assert prompt_prefix("eg2", "query") == "SearchQuery: "


def test_prompt_is_derived_from_the_model_not_configured_separately():
    """One knob. Two keys would be two chances to mismatch the pair."""
    assert set(known_models()) == set(EMBED_MODELS)
    assert model_dim("bge-m3") == 1024
    assert model_dim("eg2") == 768
    assert model_dim("nope") is None


def test_dimensions_differ_between_models():
    assert model_dim("bge-m3") != model_dim("eg2")


def _store_with_vectors(path, dim, n=1):
    store = SQLiteStore(path)
    row = b"".join(struct.pack("<f", 0.0) for _ in range(dim))
    for i in range(n):
        # Bypass the engine; we are testing the guard, not the write path.
        # stream/mono/salience/strength are NOT NULL with no default.
        store.conn.execute(
            "INSERT INTO episode(id, stream, kind, wall, mono, tau, "
            "salience, strength, body_embed) "
            "VALUES(?, 's', 'message', '2026-01-01T00:00:00Z', ?, ?, 0.0, "
            "1.0, ?)",
            (f"e{i}", i, float(i), row))
    store.conn.commit()
    return store


def test_profile_is_stamped_on_first_use(tmp_path):
    store = SQLiteStore(str(tmp_path / "a.db"))
    assert embed_profile(store) is None
    embedder_for("b", {"embed": "local"}, {"embed": {}}, store)
    prof = embed_profile(store)
    assert prof == {"model": "bge-m3", "prompts": "none", "dim": 1024}
    store.conn.execute("SELECT v FROM meta WHERE k=?", (EMBED_PROFILE_KEY,))


def test_stamp_is_idempotent(tmp_path):
    store = SQLiteStore(str(tmp_path / "b.db"))
    embedder_for("b", {"embed": "local"}, {"embed": {}}, store)
    first = embed_profile(store)
    embedder_for("b", {"embed": "local"}, {"embed": {}}, store)
    assert embed_profile(store) == first


def test_eg2_brain_stamps_the_eg2_profile(tmp_path):
    store = SQLiteStore(str(tmp_path / "c.db"))
    embedder_for("b", {"embed": "local", "embed_model": "eg2"},
                 {"embed": {}}, store)
    assert embed_profile(store) == {"model": "eg2", "prompts": "eg2", "dim": 768}


def test_unknown_model_raises(tmp_path):
    store = SQLiteStore(str(tmp_path / "d.db"))
    with pytest.raises(ValueError, match="unknown embed_model"):
        embedder_for("b", {"embed": "local", "embed_model": "gpt9"},
                     {"embed": {}}, store)


def test_dimension_mismatch_is_refused_before_any_write(tmp_path):
    """FlatVectorIndex would also refuse, but only once a second dimension
    appears -- i.e. after some rows are already wrong. Fail earlier."""
    store = _store_with_vectors(str(tmp_path / "e.db"), dim=1024)
    with pytest.raises(ValueError, match="already holds 1024-dim"):
        embedder_for("b", {"embed": "local", "embed_model": "eg2"},
                     {"embed": {}}, store)


def test_model_change_under_existing_vectors_is_refused(tmp_path):
    """Swapping model silently corrupts retrieval; it must raise, not warn.

    The dim guard catches the cross-dimension case first, so this reaches the
    profile guard specifically by perturbing the stamp to a same-dimension
    profile -- as a stale or hand-edited stamp would look.
    """
    store = _store_with_vectors(str(tmp_path / "f.db"), dim=1024)
    store.conn.execute(
        "INSERT OR REPLACE INTO meta(k, v) VALUES('embed_profile', ?)",
        ('{"model": "bge-m3-legacy", "prompts": "none", "dim": 1024}',))
    store.conn.commit()
    with pytest.raises(ValueError, match="was embedded as"):
        embedder_for("b", {"embed": "local"}, {"embed": {}}, store)


def test_eg2_brain_without_vectors_may_still_be_reconfigured(tmp_path):
    """Nothing embedded yet means nothing to corrupt -- allow the change."""
    store = SQLiteStore(str(tmp_path / "g.db"))
    embedder_for("b", {"embed": "local"}, {"embed": {}}, store)
    embedder_for("b", {"embed": "local", "embed_model": "eg2"},
                 {"embed": {}}, store)
    assert embed_profile(store)["model"] == "eg2"


def test_prompt_prefix_is_role_sensitive_only_for_pair_models():
    """The two roles must differ for a pair-trained model, or the pairing
    is pointless."""
    assert prompt_prefix("eg2", "document") != prompt_prefix("eg2", "query")
