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

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).