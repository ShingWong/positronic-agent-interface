# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

"""Config for .positronic/config.json — full key set, zod-equivalent validation."""
import json
from pathlib import Path

ALLOWED_PROFILES = {"balanced", "archival", "long_term", "short_term"}
ALLOWED_EMBEDS = {"lexical", "local", "remote"}
ENGRAM_TAG = "v0.3.1"
CONFIG_KEYS = {"profile", "embed", "threshold", "live",
               "local_url", "remote_url", "remote_key", "engram_tag",
               "vision_url",
               "consolidate_every", "prune_every", "dedup",
               "since_consolidate", "since_prune", "capture_user"}
_DEFAULT = {"brains": {}, "live": True,
            "embed": {"local_url": "http://127.0.0.1:8090",
                      "vision_url": "http://127.0.0.1:8080"}, "engram_tag": ENGRAM_TAG,
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
    from memeng.engine import MemoryEngine
    engine_knobs = set(MemoryEngine.default_config())
    for name, b in cfg.get("brains", {}).items():
        prof = b.get("profile")
        if prof and prof not in ALLOWED_PROFILES:
            raise ValueError(f"unknown retention profile: {prof}")
        emb = b.get("embed")
        if emb and emb not in ALLOWED_EMBEDS:
            raise ValueError(f"unknown embed choice: {emb}")
        # Per-brain engine knobs. Rejecting unknown names is the whole point:
        # memeng silently ignores a key it does not read, so a typo would
        # otherwise be a setting that appears to work and does not.
        nested = b.get("engine") or {}
        if not isinstance(nested, dict):
            raise ValueError(  # noqa: TRY004 (CLI catches ValueError)
                f"brains.{name}.engine must be an object")
        unknown = sorted(set(nested) - engine_knobs)
        if unknown:
            raise ValueError(
                f"brains.{name}.engine has unknown knob(s): {unknown}. "
                f"Known knobs: {sorted(engine_knobs)}")
        thr = b.get("threshold")
        if thr is not None and not (0.0 <= float(thr) <= 1.0):
            raise ValueError(f"brains.{name}.threshold must be in [0,1]")
        if b.get("threat") is not None:
            from .threat import validate_spec_override
            validate_spec_override(b["threat"], brain=name)
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
    if key in ("profile", "embed", "threshold", "engine", "threat"):
        if not brain:
            raise ValueError(
                "brain required for per-brain key: "
                "profile|embed|threshold|engine|threat")
        if brain not in cfg["brains"]:
            raise ValueError(f"unknown brain {brain}")
        if key == "profile" and value not in ALLOWED_PROFILES:
            raise ValueError(f"unknown profile {value}")
        if key == "embed" and value not in ALLOWED_EMBEDS:
            raise ValueError(f"unknown embed choice {value}")
        if key == "threshold":
            value = float(value)
        if key == "engine":
            # Merge, so setting one knob does not erase the others.
            patch = value or {}
            if not isinstance(patch, dict):
                raise ValueError("engine must be an object of knob -> value")
            cfg["brains"][brain].setdefault("engine", {}).update(patch)
        if key == "threat":
            cfg["brains"][brain]["threat"] = value
            value = cfg["brains"][brain]["threat"]
        cfg["brains"][brain][key] = value
    elif key == "live":
        cfg["live"] = bool(value)
    elif key == "local_url":
        cfg.setdefault("embed", {})["local_url"] = value
    elif key == "vision_url":
        cfg.setdefault("embed", {})["vision_url"] = value
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