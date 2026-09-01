<!--
Licensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later).
Copyright (C) 2026 Shing Wong. All Rights Reserved.
See LICENSE for the full license text.
-->

# AGENTS.md — positronic-agent-interface

Python package `positronic_ai` (PAI): polytemporal memory agent interface over
`memeng` (positronic-engram, pinned `ENGRAM_TAG=v0.2.0`). Exposes every
operation as a code API (`positronic_ai.*`) and a CLI verb (`positronic` /
`python -m positronic_ai`).

## Layout

- `positronic_ai/config.py` — full-key config op (`profile|embed|threshold`
  per brain; `live|local_url|remote_url|remote_key|engram_tag` top-level).
- `positronic_ai/engine.py` — memeng engine helper.
- `positronic_ai/ops/` — one module per verb; each exports `run(...) -> dict`.
- `positronic_ai/cli.py` — verb dispatch (console script `positronic`).
- `positronic_ai/__main__.py` — `python -m positronic_ai` entry.
- `tests/` — pytest.

## Brain access

```bash
python -m positronic_ai init --brain demo
python -m positronic_ai ingest "hello"
python -m positronic_ai recall "hello"
```

## State paths

- `.positronic/config.json` — global config.
- `.positronic/brains/{name}/memory.db` — per-brain memory store.

**PII firewall** — `.positronic/` holds user memory and secrets; it is
gitignored and must never be committed.

## Commands

```bash
pytest -q                # testpaths = ["tests"]; memeng + PAI editable-installed
ruff check positronic_ai/ tests/
```

Every `.py` file carries the GPL-3.0-or-later header; `pyproject.toml` carries
`license = "GPL-3.0-or-later"`. No MCP anywhere.

## Note

The opencode plugin (`positronic-opencode-plugin`) and claude-code integrations
route agent-facing memory access into this interface.