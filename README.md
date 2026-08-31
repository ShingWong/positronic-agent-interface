<!--
Licensed under the GNU General Public License, version 3 or later (GPL-3.0-or-later).
Copyright (C) 2026 Shing Wong. All Rights Reserved.
See LICENSE for the full license text.
-->

# positronic-agent-interface (PAI)

Polytemporal memory agent interface over `memeng`. Owns `.positronic/config.json`
and `.positronic/brains/{name}/memory.db`; exposes every operation as a code API
(`positronic_ai.*`) and a CLI verb (`positronic <verb>` / `python -m positronic_ai`).

License: GPL-3.0-or-later.