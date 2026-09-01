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

"""Config verb — op wrapper over config.set_key (get mode masks remote_key)."""
import json

from ..config import load_config, set_key

_TRUE = {"true", "1", "yes", "on"}


def _mask(cfg: dict, show_secrets: bool) -> None:
    """Replace remote_key values with *** unless show_secrets (in place)."""
    if show_secrets:
        return
    if isinstance(cfg, dict):
        for k, v in list(cfg.items()):
            if k == "remote_key":
                cfg[k] = "***"
            else:
                _mask(v, show_secrets)
    elif isinstance(cfg, list):
        for item in cfg:
            _mask(item, show_secrets)


def run(dir, *, key=None, value=None, brain=None, confirm=False,
        show_secrets=False) -> dict:
    """Get (no key) or set one config key; returns a dict.

    Get mode deep-copies the config and masks remote_key unless
    show_secrets. Set mode blocks PII paths, gates profile=archival on
    confirm, coerces live booleans, then delegates to config.set_key
    returning {changed, before, after} (before/after masked unless
    show_secrets).
    """
    if key is None:
        cfg = json.loads(json.dumps(load_config(dir)))
        _mask(cfg, bool(show_secrets))
        return cfg
    if "*.db" in key or "memory.db" in key or "brain_henry" in key:
        raise ValueError("PII path blocked")
    if key == "live" and isinstance(value, str):
        value = value.strip().lower() in _TRUE
    if key == "profile" and value == "archival" and not confirm:
        before = json.loads(json.dumps(load_config(dir)))
        _mask(before, bool(show_secrets))
        return {"warning": "Retention archival never forgets — E7 55/55/35/7 vs balanced. Re-invoke with confirm:true",
                "before": before}
    out = set_key(dir, key, value, brain=brain)
    _mask(out["before"], bool(show_secrets))
    _mask(out["after"], bool(show_secrets))
    return out