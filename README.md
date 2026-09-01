<!--
Licensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later).
Copyright (C) 2026 Shing Wong. All Rights Reserved.
See LICENSE for the full license text.
-->

# positronic-agent-interface (PAI)

Polytemporal memory agent interface over `memeng` (positronic-engram). Owns
`.positronic/config.json` and `.positronic/brains/{name}/memory.db`; exposes
every operation as a code API (`positronic_ai.*`) and a CLI verb (`positronic`
/ `python -m positronic_ai`).

## Install

```bash
pip install "git+https://github.com/ShingWong/positronic-agent-interface.git"
```

This installs the `positronic` console script plus the `positronic_ai` package
(`memeng` is pulled in at `v0.2.0`).

## Get a brain running in 30 seconds

```bash
positronic init --brain demo           # creates .positronic/config.json + brain db
positronic ingest "first memory here"
positronic recall "first memory"       # federated recall across all brains
positronic stats                       # per-brain episode counts
```

## Verbs

| Verb | Purpose |
|------|---------|
| `init` | create `.positronic/config.json` + brains (`--brain NAME`, `--profile`, `--embed lexical\|local\|remote`, `--live/--no-live`, `--force`) |
| `info` | version, `ENGRAM_TAG`, brains, tiers |
| `stats` | per-brain episode counts (`--brain NAME`) |
| `config` | get/set config keys (`config KEY [VALUE]`, `--brain NAME`, `--value`, `--show-secrets`) |
| `brain-test` | smoke probe `new_event -> activate` on a brain (`--brain NAME`, `--k N`) |
| `llm-stat` | bge/llama tier health |
| `llm-setup` | tier guide (`--tier 1\|2\|3`) |
| `update` | deferred engine update (`--check`, `--status`, `--tail N`, `--pin TAG`) |
| `delete` | delete a brain (`--brain NAME`, `--force`) |
| `query` | query a brain: text, `--sql`, `--cue`, `--anchors`, `--objects`, `--sightings` (`--k N`) |
| `prune` | prune a brain's memory (`--brain NAME`) |
| `consolidate` | consolidate episodes (`--arousal F`, `--brain NAME`) |
| `ingest` | ingest an event into a brain (`--arousal F`, `--brain NAME`) |
| `recall` | fused recall across federated brains (`--k N`) |
| `ask` | answer a question from brain memory |
| `wake` | trigger a consolidation marker + prune sweep |
| `doctor` | `{ lexical, bge, llama, engram }` tier check |

Every verb works as `positronic <verb>` or `python -m positronic_ai <verb>`.

## Config keys

`.positronic/config.json`:

- Per-brain (`brains.<name>`): `profile` (retention), `embed`
  (`lexical` \| `local` \| `remote`), `threshold`.
- Top-level: `live` (bool), `local_url`, `remote_url`, `remote_key`,
  `engram_tag`.
- Lifecycle: `auto.consolidate_every`, `auto.prune_every` (episode counts,
  `0` = disabled — the default), `counters.since_consolidate`,
  `counters.since_prune` (running tallies), `dedup` (bool, skip exact-repeat
  messages).

## Memory lifecycle: compaction-driven by default

Forgetting and summarization are wired to the agent's **compaction event**,
not to a timer or a prompt counter. When an agent session compacts — opencode
fires `session.compacted`; Claude Code fires `PreCompact` — the plugin:

1. **prunes** the brain (τ-decay demote/expire per the retention profile), and
2. writes a **consolidation marker** (a `kind='consolidation'` episode).

That is the primary lifecycle. It costs nothing when nothing compacts, and it
fires exactly when old context is being summarized away — the natural moment
to forget and to write a summary.

**Why the counters are off by default.** The counter-based auto-triggers
(`auto.consolidate_every` / `auto.prune_every`) are an *opt-in fallback* for
sessions that never compact: long-running, low-churn context where no era
boundary ever fires. They advance on every non-duplicate message ingest and
run the same `consolidate` / `prune` operations at a fixed cadence. They are
**disabled by default** (`0`) because:

- a compaction-driven lifecycle already covers the common case, and
- a blind counter (e.g. every 300/1000 prompts) would fire regardless of
  whether the context actually reached an era boundary, writing redundant
  markers or pruning too eagerly on a quiet session.

To enable, either set them at init or via the config command:

```bash
positronic init --brain kairos --auto-consolidate 300 --auto-prune 1000
positronic config consolidate_every 300
positronic config prune_every 1000
```

`0` disables a trigger. `counters.since_consolidate` / `since_prune` track
messages since the last run and reset when a trigger fires (or when a
compaction-driven prune/consolidate runs via a hook).

**Dedup.** `dedup: true` makes `ingest` skip a message whose `body_text`
matches the most recent episode (string compare), returning
`{duplicate: true, skipped: true}` without writing or advancing counters.
Claude Code enables this per-call (`--dedup` on its `UserPromptSubmit` hook)
because a repeated prompt must not re-ingest itself; opencode leaves it off
since its `chat.message` capture records distinct turns.

## JSON output

Pass `--json` to any verb for machine-readable output:

```bash
positronic stats --json
positronic doctor --json
```

## Federated recall

```bash
positronic recall "topic"
```

`recall` fuses hits across every configured brain and returns ranked memories.
Use `ask` for a natural-language answer over that memory.

## Wire it into your agent (CLAUDE.md / AGENTS.md)

The memory is only worth something if the agent actually reaches for it. The
single highest-leverage setup step is a **one-rule instruction in your
agent's config file**: *query the brain before you re-derive.* Retrieval is
single-digit milliseconds; re-reading a codebase from scratch is not. In our
own repo this rule is the difference between a 3ms recall that surfaces last
week's decisions and a full re-read of the same files.

**opencode** — add to your project's `AGENTS.md`:

```markdown
## Dogfooding: recall before resuming (mandatory)

Before resuming work in this repo — a new task, a follow-up edit, or an
executing-plans session — run the brain first to ground in prior decisions:

```bash
positronic recall "<topic>" --json     # or python -m positronic_ai recall ...
```

Retrieval is fast (single-digit ms) and surfaces the session decisions live
ingestion already captured, saving the re-read. This rule binds the main
agent and every subagent: query/recall before you re-derive.
```

**Claude Code** — add the same rule to your project's `CLAUDE.md` (or rely on
the `memory` skill bundled with the claude-code plugin, which teaches the
model to run `recall`/`query`/`ask` when it needs prior context):

```markdown
## Memory

This project has a polytemporal memory brain (`.positronic/`). Before
answering about prior work, decisions, or history, run
`python -m positronic_ai recall "<topic>" --json` and use the results.
Don't guess from scratch — recall is milliseconds.
```

Key points to convey:

- **Recall, don't re-read.** Ingestion is automatic (live hooks per session);
  retrieval is the cheap operation.
- **Bind every agent.** State the rule so it also applies to subagents —
  a main agent that recalls but whose subagents re-derive wastes the setup.
- **Plan docs too.** Long-running work should carry a recall step in its
  plan (e.g. "before Task 0, `positronic recall "<feature>"` to surface prior
  decisions"). The umbrella `AGENTS.md` in the positronic monorepo is a
  working example of all of the above.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).