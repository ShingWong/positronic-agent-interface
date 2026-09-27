<!-- =====================================================================
Project Positronic — Polytemporal Cognitive Engram Memory Substrate
Copyright (C) 2026 Shing Wong. All Rights Reserved.
=====================================================================
This program is DUAL-LICENSED. You may redistribute and/or modify it 
under the terms of the GNU Affero General Public License as published by the 
Free Software Foundation, either version 3 of the License, or (at your 
option) any later version.

Alternatively, commercial entities, multi-tenant instances, and Managed 
Service Providers (MSPs) may utilize this program under a separate, 
proprietary Commercial License Waiver issued directly by the copyright 
holder, completely exempt from the network-use copyleft restrictions of 
the AGPLv3 Section 13.

This program is distributed in the hope that it will be useful, but 
WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License 
along with this program. If not, see <https://gnu.org>.
===================================================================== -->

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
- `positronic_ai/extract/` — attachment/body extraction (`html`, `pdf`, `office`, `mail`, `attach`).
- `positronic_ai/server/` — optional FastAPI transport (`app.py`; `python -m positronic_ai.server`).
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

Every `.py` file carries the AGPL dual-license header; `pyproject.toml` carries
`license = "AGPL-3.0-or-later OR LicenseRef-Commercial"`. No MCP anywhere.

## Note

The opencode plugin (`positronic-opencode-plugin`) and claude-code integrations
route agent-facing memory access into this interface.