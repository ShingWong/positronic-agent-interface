<!--
Licensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later).
Copyright (C) 2026 Shing Wong. All Rights Reserved.
See LICENSE for the full license text.
-->

# AGENTS.md — positronic-agent-interface

Python package `positronic_ai` (PAI): polytemporal memory agent interface over
`memeng` (positronic-engram, pinned `ENGRAM_TAG=v0.2.0`). State paths stay
identical: `.positronic/config.json`, `.positronic/brains/{name}/memory.db`
(PII firewall — never commit `.positronic/`).

## Layout

- `positronic_ai/config.py` — full-key config op (profile|embed|threshold,
  live|local_url|remote_url|remote_key|engram_tag) with validation.
- `positronic_ai/ops/` — one module per verb; each exports `run(...) -> dict`.
- `positronic_ai/cli.py` — verb dispatch (console script `positronic`).
- `tests/` — pytest.

## Commands

```bash
python3 -m pytest tests/ -q
```

Every `.py` file carries the GPL-3.0-or-later header. No MCP anywhere.