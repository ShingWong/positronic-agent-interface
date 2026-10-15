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

"""Engine open helper — resolve a project brain DB to (store, engine)."""
import pathlib

from memeng.engine import MemoryEngine
from memeng.store import SQLiteStore

import json

from .config import load_config


def open_engine(project_dir, brain: str) -> tuple[SQLiteStore, MemoryEngine]:
    db = pathlib.Path(project_dir) / ".positronic" / "brains" / brain / "memory.db"
    if not db.exists():
        raise FileNotFoundError(f"no such brain db: {db}")
    s = SQLiteStore(str(db))
    cfg = load_config(project_dir)
    bcfg = (cfg.get("brains", {}) or {}).get(brain, {}) or {}
    engine_cfg = brain_engine_config(bcfg)
    e = MemoryEngine(s, engine_cfg or None)
    if bcfg.get("embed") == "local":
        e.bind_embedder(embedder_for(brain, bcfg, cfg, s))
    return s, e


def close_engine(store) -> None:
    """Commit and close a store opened by open_engine.

    SQLite holds a write transaction until commit, and an unclosed connection
    holds it for good: the next open in the same process then dies inside
    SQLiteStore.__init__ (executescript DDL) with `sqlite3.OperationalError:
    database is locked`. Auto-prune hit exactly that — ingest held the brain,
    prune opened it a second time, and the query that followed could not
    create its tables (tests/test_auto.py::test_auto_prune_trigger_and_reset,
    red on CI and locally).

    One verb per process hides the leak — the CLI and the opencode plugin both
    spawn a fresh interpreter per call — so anything that runs two ops in one
    process (the test suite, the HTTP server, a long-lived embedding worker)
    is where it surfaces. Read-only ops are exempt: SELECTs autocommit and
    leave no write transaction behind.
    """
    try:
        store.conn.commit()
    finally:
        store.conn.close()


# -- embedding profile -------------------------------------------------------
#
# A brain's embedding model is stamped into its OWN meta table, and the
# query path reads the stamp rather than the config. That makes a mismatch
# structurally impossible instead of a config mistake: editing config.json,
# or swapping a model under an existing brain, cannot silently leave the
# brain querying a vector space it was never embedded into.

EMBED_PROFILE_KEY = "embed_profile"


def _existing_embed_dim(store) -> int | None:
    row = store.conn.execute(
        "SELECT body_embed FROM episode WHERE body_embed IS NOT NULL LIMIT 1"
    ).fetchone()
    return len(row[0]) // 4 if row else None


def _stamp_or_verify(store, brain: str, profile: dict) -> None:
    """Record the profile on first embed; refuse a silent change thereafter.

    With no vectors yet there is nothing to corrupt, so the profile may be
    freely set -- that is the setup-before-ingest case. Once vectors exist,
    changing model under them raises rather than silently corrupting
    retrieval.
    """
    want = json.dumps(profile, sort_keys=True)
    row = store.conn.execute(
        "SELECT v FROM meta WHERE k=?", (EMBED_PROFILE_KEY,)).fetchone()
    if row is None:
        store.conn.execute(
            "INSERT INTO meta(k, v) VALUES(?, ?)", (EMBED_PROFILE_KEY, want))
        store.conn.commit()
        return
    if row[0] == want:
        return
    if _existing_embed_dim(store) is None:
        store.conn.execute(
            "UPDATE meta SET v=? WHERE k=?", (want, EMBED_PROFILE_KEY))
        store.conn.commit()
        return
    raise ValueError(
        f"brain {brain!r} was embedded as {row[0]} but is now configured "
        f"as {want}. Changing model under existing vectors silently breaks "
        f"retrieval; use a separate brain, or re-embed from scratch with "
        f"the old vectors cleared first.")


def embedder_for(brain: str, bcfg: dict, cfg: dict, store):
    """Build the document-side embedder for one brain.

    `embed_model` is the single knob; the task-prompt style is derived from
    it in embed.py so the two cannot drift apart.
    """
    from .embed import (DEFAULT_EMBED_MODEL, EMBED_MODELS, embed_one,
                        known_models, model_dim)
    model = bcfg.get("embed_model") or DEFAULT_EMBED_MODEL
    spec = EMBED_MODELS.get(model)
    if spec is None:
        raise ValueError(f"unknown embed_model {model!r} for brain {brain!r}; "
                         f"known: {known_models()}")
    embed_cfg = cfg.get("embed") or {}
    url = embed_cfg.get(spec["url_key"]) or embed_cfg.get(
        "local_url", "http://127.0.0.1:8090")
    dim = model_dim(model)
    have = _existing_embed_dim(store)
    if have is not None and dim is not None and have != dim:
        # FlatVectorIndex also refuses a dim mismatch at add() time, but that
        # fires only once a second dimension appears -- i.e. after some rows
        # are already wrong. Catching it here fails before any write.
        raise ValueError(
            f"brain {brain!r} already holds {have}-dim vectors but "
            f"embed_model {model!r} produces {dim}-dim.")
    _stamp_or_verify(store, brain,
                     {"model": model, "prompts": spec["prompts"], "dim": dim})
    return lambda text: embed_one(text, url, role="document", model=model)[0]


def embed_profile(store) -> dict | None:
    """The profile this brain's vectors were written with, or None."""
    row = store.conn.execute(
        "SELECT v FROM meta WHERE k=?", (EMBED_PROFILE_KEY,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (TypeError, ValueError):
        return None


def brain_engine_config(brain_cfg: dict) -> dict:
    """Translate a brain's config block into memeng engine knobs.

    The brain may set either a nested `engine` dict (the general case) or the
    legacy flat `threshold` key. The flat key predates this function and was
    written to config but never read, because every MemoryEngine was built
    without config -- so anyone who set it got silence. It is honoured here.

    Returns only keys memeng actually reads; `config._validate` rejects the
    rest, so a typo is loud rather than inert.
    """
    out: dict = {}
    nested = brain_cfg.get("engine") or {}
    if isinstance(nested, dict):
        out.update(nested)
    if brain_cfg.get("threshold") is not None:
        out.setdefault("threshold", float(brain_cfg["threshold"]))
    return out
