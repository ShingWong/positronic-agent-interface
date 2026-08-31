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

"""Config for .positronic/config.json — full key set, zod-equivalent validation."""
import json
from pathlib import Path

ALLOWED_PROFILES = {"balanced", "archival", "long_term", "short_term"}
ALLOWED_EMBEDS = {"lexical", "local", "remote"}
ENGRAM_TAG = "v0.2.0"
CONFIG_KEYS = {"profile", "embed", "threshold", "live",
               "local_url", "remote_url", "remote_key", "engram_tag"}
_DEFAULT = {"brains": {}, "live": True,
            "embed": {"local_url": "http://127.0.0.1:8090"}, "engram_tag": ENGRAM_TAG}

def _config_path(project_dir) -> Path:
    return Path(project_dir) / ".positronic" / "config.json"

def load_config(project_dir) -> dict:
    p = _config_path(project_dir)
    if not p.exists():
        return json.loads(json.dumps(_DEFAULT))
    data = json.loads(p.read_text())
    for k, v in _DEFAULT.items():
        data.setdefault(k, v)
    _validate(data)
    return data

def _validate(cfg: dict) -> None:
    for name, b in cfg.get("brains", {}).items():
        prof = b.get("profile")
        if prof and prof not in ALLOWED_PROFILES:
            raise ValueError(f"unknown retention profile: {prof}")
        emb = b.get("embed")
        if emb and emb not in ALLOWED_EMBEDS:
            raise ValueError(f"unknown embed choice: {emb}")
    live = cfg.get("live")
    if live is not None and not isinstance(live, bool):
        raise ValueError("live must be a boolean")

def save_config(project_dir, cfg: dict) -> None:
    _validate(cfg)
    for k, v in _DEFAULT.items():
        cfg.setdefault(k, v)
    p = _config_path(project_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2))

def get_brains(project_dir) -> dict:
    return load_config(project_dir).get("brains", {})

def set_key(project_dir, key: str, value, *, brain: str | None = None) -> dict:
    """Set one config key; returns {changed, before, after}."""
    cfg = load_config(project_dir)
    before = json.loads(json.dumps(cfg))
    if key in ("profile", "embed", "threshold"):
        if not brain:
            raise ValueError("brain required for per-brain key: profile|embed|threshold")
        if brain not in cfg["brains"]:
            raise ValueError(f"unknown brain {brain}")
        if key == "profile" and value not in ALLOWED_PROFILES:
            raise ValueError(f"unknown profile {value}")
        if key == "embed" and value not in ALLOWED_EMBEDS:
            raise ValueError(f"unknown embed choice {value}")
        if key == "threshold":
            value = float(value)
        cfg["brains"][brain][key] = value
    elif key == "live":
        cfg["live"] = bool(value)
    elif key == "local_url":
        cfg.setdefault("embed", {})["local_url"] = value
    elif key == "remote_url":
        cfg.setdefault("embed", {})["remote_url"] = value
    elif key == "remote_key":
        cfg.setdefault("embed", {})["remote_key"] = value
    elif key == "engram_tag":
        cfg["engram_tag"] = value
    else:
        raise ValueError(f"unknown key {key}")
    save_config(project_dir, cfg)
    return {"changed": [key], "before": before, "after": load_config(project_dir)}