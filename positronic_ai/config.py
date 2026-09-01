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
               "local_url", "remote_url", "remote_key", "engram_tag",
               "consolidate_every", "prune_every", "dedup",
               "since_consolidate", "since_prune", "capture_user"}
_DEFAULT = {"brains": {}, "live": True,
            "embed": {"local_url": "http://127.0.0.1:8090"}, "engram_tag": ENGRAM_TAG,
            "auto": {"consolidate_every": 0, "prune_every": 0},
            "counters": {"since_consolidate": 0, "since_prune": 0},
            "dedup": False, "capture_user": False}

def _config_path(project_dir) -> Path:
    return Path(project_dir) / ".positronic" / "config.json"

def _merge_defaults(cfg: dict) -> dict:
    for k, v in _DEFAULT.items():
        if k not in cfg:
            cfg[k] = json.loads(json.dumps(v))
        elif isinstance(v, dict) and isinstance(cfg[k], dict):
            for kk, vv in v.items():
                cfg[k].setdefault(kk, json.loads(json.dumps(vv)))
    return cfg

def load_config(project_dir) -> dict:
    p = _config_path(project_dir)
    if not p.exists():
        return json.loads(json.dumps(_DEFAULT))
    data = json.loads(p.read_text())
    _merge_defaults(data)
    _validate(data)
    return data

def _validate(cfg: dict) -> None:
    for b in cfg.get("brains", {}).values():
        prof = b.get("profile")
        if prof and prof not in ALLOWED_PROFILES:
            raise ValueError(f"unknown retention profile: {prof}")
        emb = b.get("embed")
        if emb and emb not in ALLOWED_EMBEDS:
            raise ValueError(f"unknown embed choice: {emb}")
    live = cfg.get("live")
    if live is not None and not isinstance(live, bool):
        raise ValueError("live must be a boolean")
    auto = cfg.get("auto") or {}
    for k in ("consolidate_every", "prune_every"):
        v = auto.get(k, 0)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"auto.{k} must be a non-negative integer")
    counters = cfg.get("counters") or {}
    for k in ("since_consolidate", "since_prune"):
        v = counters.get(k, 0)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"counters.{k} must be a non-negative integer")
    dedup = cfg.get("dedup")
    if dedup is not None and not isinstance(dedup, bool):
        raise ValueError("dedup must be a boolean")
    capture_user = cfg.get("capture_user")
    if capture_user is not None and not isinstance(capture_user, bool):
        raise ValueError("capture_user must be a boolean")

def save_config(project_dir, cfg: dict) -> None:
    _validate(cfg)
    _merge_defaults(cfg)
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
    elif key in ("consolidate_every", "prune_every"):
        cfg.setdefault("auto", {})[key] = int(value)
    elif key == "dedup":
        cfg["dedup"] = bool(value)
    elif key == "capture_user":
        cfg["capture_user"] = bool(value)
    elif key in ("since_consolidate", "since_prune"):
        cfg.setdefault("counters", {})[key] = int(value)
    else:
        raise ValueError(f"unknown key {key}")
    save_config(project_dir, cfg)
    return {"changed": [key], "before": before, "after": load_config(project_dir)}