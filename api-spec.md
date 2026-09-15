# API Specification v0

All verbs live in `positronic_ai.ops.<verb>.run(...) -> dict`, invoked as
`python -m positronic_ai <verb>` (console script `positronic`). Every return
is JSON-serializable and is the direct plugin/tool contract. `dir` is the
project directory owning `.positronic/`.

---

## `init(dir, *, brains=None, force=False, live=None, auto_consolidate=None, auto_prune=None) -> dict`

Create brains + config. No `brains` → returns wizard help text (no side
effects). Existing brain without `force` → warning. Otherwise `init_brain`
per brain, merge config preserving keys.

**Returns**: `{ok, brains, created, existing, configPath, live?, auto?}`
(or `{ok: False, warning}` for help / overwrite gate).

## `info(dir) -> dict`

**Returns**: `{version, engram_tag, brains, tiers}` — `tiers` from doctor.

## `stats(dir, *, brain=None) -> dict`

Per-brain episode counts + profile/embed help. Missing dbs are skipped.

**Returns**: `{brains: {name: {episodes, profile, profileHelp, embed, embedHelp}}}`.

## `config(dir, *, key=None, value=None, brain=None, confirm=False, show_secrets=False) -> dict`

Get (no key) → deep-copied config with `remote_key` masked. Set → blocks PII
paths, gates `profile=archival` on `confirm`, delegates to `config.set_key`.

**Returns**: get: full config dict; set: `{changed, before, after}`; archival
gate: `{warning, before}`.

## `brain_test(dir, *, brain="kairos", k=3) -> dict`

Smoke probe: encode a probe event, time encode + recall.

**Returns**: `{ok, encode_ms, recall_ms, hits, fallback, rrf_score}`.

## `doctor() -> dict`

Probe engram/bge/llama/lexical tiers; each is best-effort.

**Returns**: `{tiers: {engram, bge, llama, lexical}}`.

## `llm_stat() -> dict`

**Returns**: `{bge, llama, lexical, engram, pooling}` (`pooling` = `"cls"`
when bge is ok, else `"unknown"`).

## `llm_setup(tier="3") -> dict`

**Returns**: `{tier, guide}` — first 500 chars of `docs/llama.md`.

## `update(*, check=False, pin=None, status=None, tail=None, dir=None) -> dict`

Deferred self-update. `check` → git-behind probe; `status` → job log read;
`tail` → last N log lines; else spawn detached job.

**Returns**: check: `{behind, engramTagDiff, npmOutdated, logTail}`;
status: `{jobId, status, exitCode, logTail, logPath}`; else `{jobId, status, logPath}`.

## `delete(dir, *, brain=None, force=False) -> dict`

Permanently remove a brain + db. `brain` absent → usage/help. `force` absent
→ warning. Blocked brain paths handled at config level.

**Returns**: `{ok, warning?, deleted?, before, after, dbPath}`.

## `query(dir, *, brain="kairos", text=None, sql=None, cue=None, objects=False, anchors=False, sightings=False, k=8) -> dict`

Brain read ops. `sql` → raw rows; `anchors`/`sightings`/`objects` → curated
SQL; `cue`/`text` → `activate` fuzzy recall (text returns `{ms, hits}`).

**Returns**: text: `{ok, brain, ms, hits, results, human}`; others:
`{ok, brain, results, human}`; no args: `{ok, help, usage, human}`.

## `prune(dir, *, brain=None, tau_now=None) -> dict`

Run τ-decay `engine.prune()`. Skips when `live=false`.

**Returns**: `PruneReport` as dict: `{scanned, day_merged, week_merged,
expired, residues, objects_dormant, objects_forgotten}`.

## `consolidate(dir, text, *, brain=None, arousal=0.4) -> dict`

Write a `kind='consolidation'` event (the distilled summary of a session).

**Returns**: `{ok, tau, encoded, episode_id}`.

## `ingest(dir, text, *, brain=None, kind="message", arousal=0.5, subject=None, dedup=None, role="assistant", sender=None, date=None, message_id=None) -> dict`

Write a raw observation. Consecutive-body `dedup` (per role) applies only when
no `message_id` is given; a normalized RFC `message_id` (angle brackets
stripped, via `normalize_message_id`) dedupes hard across the whole brain
regardless of intervening events. `sender` / `date` / `message_id` are stored
in `features_json` when truthy (mail metadata). `role` tags `user`/`assistant`
(gated by `capture_user` config).

**Returns**: `{tau, encoded, episode_id, embedded, embed_reason?}` (or
`{duplicate, skipped, tau, episode_id?, by?}` — `by: "message_id"` when the
hard message-id gate fired).

## `recall(dir, text, *, k=8, brains=None) -> dict`

Federated fuzzy recall across configured brains, RRF-fused, each hit tagged
with its source brain. When the cue fuzzy-matches an object, attaches a
polytemporal **digest**.

**Returns**: `{results: [{brain, episode_id, tau, snippet, rrf_score, ...}],
object?: {canonical_name, kind, status, salience, first_seen_tau,
last_seen_tau, versions: {sighting_count, tau_span, latest_consolidation,
oldest_tau}}}`.

## `ask(dir, object_name) -> dict`

Object dossier — the dig-deeper verb. First brain with a fuzzy canonical-name
match wins.

**Returns**: `{object, sightings: [{episode_id, channel, confidence, tau,
wall, subject_norm, kind}], found}`.

## `wake(dir) -> dict`

Orientation brief for session start: top anchors + today's consolidations.

**Returns**: `{brief: "<multi-line string>"}`.

---

## Objects helpers (`positronic_ai/objects.py`)

Shared by `recall` and `ask`; the polytemporal contract lives here.

- `resolve_object(store, name) -> dict | None` — fuzzy canonical-name lookup.
- `object_sightings(store, object_id) -> list[dict]` — full τ-ordered dossier.
- `object_digest(store, object_id) -> dict` — `{sighting_count, tau_span,
  latest_consolidation, oldest_tau}`.

## Unit-test contract (see tests/)

- init creates brains + config; delete warns without force and wipes with it.
- config get masks `remote_key`; set gates archival on confirm; PII paths blocked.
- ingest writes an event; dedup skips consecutive identical bodies.
- ingest persists `sender` / `date` / `message_id`; re-ingest of the same
  normalized `message_id` returns `{duplicate, by: "message_id"}`.
- recall fuses across brains; object digest attaches on fuzzy match; non-match
  returns live results only.
- ask returns full dossier; unknown object → `found: False`.
- wake brief contains anchors + consolidations.
- prune returns a PruneReport; skips when `live=false`.
- brain-test writes + recalls a probe event.
- auto lifecycle: consolidate/prune fire on counters reaching `auto.*`.

---

## HTTP server (`positronic_ai.server`, optional)

`python -m positronic_ai.server` starts a FastAPI transport over the same verbs
(`positronic_ai/server/app.py`) — a thin REST wrapper for browser clients
(e.g. the Thunderbird email plugin). No new logic: every route delegates to the
matching `ops.<verb>.run`.

Env: `POSITRONIC_PROJECT_DIR` (default CWD), `POSITRONIC_SERVER_HOST`
(default `0.0.0.0`), `POSITRONIC_SERVER_PORT` (default `8080`),
`POSITRONIC_MAIL_BRAIN` (pins the instance to one brain — see isolation).

**Brain isolation:** when `POSITRONIC_MAIL_BRAIN` is set, the instance
serves exactly that brain. Client-supplied brain names are ignored on
every endpoint (`ingest`, `recall`, `query`, `tag`, `brain-test`,
`info`, `stats`). Mail brains can never cross into each other or
into session brains like kairos. Manual cross-brain access happens
only outside the pinned server, with explicit approval.

| Route | Body | Verb |
|-------|------|------|
| `GET /health` | — | liveness + project dir |
| `GET /info` | — | `info` |
| `GET /stats` | — | `stats` |
| `POST /ingest` | `IngestMailRequest` | `ingest` (per-user `brain`, auto-provisioned) |
| `POST /recall` | `{text, k, brains?, ...}` | `recall` |
| `POST /query` | `QueryRequest` | `query` |
| `POST /ask` | `{object_name}` | `ask` |
| `POST /brain-test` | `{brain?, k?}` | `brain_test` |

`POST /ingest` accepts `{subject, body, sender, date, messageId, brain?,
attachments?}`. The `brain` field is sanitized (`sanitize_brain`: lowercase,
non-alphanumerics → `_`, max 40 chars) and the brain is auto-provisioned
(`balanced`/`lexical`) on first use, so a mail client can route per account
without pre-creating brains. An empty body is stored honestly (not replaced by
the subject); the response adds `brain` + `body_chars` so clients can warn.

The `server` extra needs `fastapi` + `uvicorn` (not in core deps).
