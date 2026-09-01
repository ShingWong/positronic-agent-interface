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

"""CLI — verb dispatch over ops.*; console script entry is `main`."""
import json
import os
import sys

from . import ops

OPS = {
    "init": ops.init.run,
    "info": ops.info.run,
    "stats": ops.stats.run,
    "config": ops.config.run,
    "brain-test": ops.brain_test.run,
    "llm-stat": ops.llm_stat.run,
    "llm-setup": ops.llm_setup.run,
    "update": ops.update.run,
    "delete": ops.delete.run,
    "query": ops.query.run,
    "prune": ops.prune.run,
    "consolidate": ops.consolidate.run,
    "ingest": ops.ingest.run,
    "recall": ops.recall.run,
    "ask": ops.ask.run,
    "wake": ops.wake.run,
    "doctor": ops.doctor.run,
}

USAGE = "positronic <verb> [args]\nverbs: " + " | ".join(OPS)

_VALUE_FLAGS = {"brain", "k", "sql", "cue", "text", "arousal", "tier",
                "status", "tail", "pin", "value", "key", "profile", "embed",
                "auto-consolidate", "auto-prune", "role"}


def _parse(argv):
    args, flags = [], {}
    i, n = 0, len(argv)
    while i < n:
        a = argv[i]
        if not a.startswith("--"):
            args.append(a)
            i += 1
            continue
        name = a[2:]
        if "=" in name:
            k, v = name.split("=", 1)
            if k == "brain":
                flags.setdefault("brain", []).append(v)
            else:
                flags[k] = v
        elif name == "brain":
            if i + 1 < n and not argv[i + 1].startswith("--"):
                flags.setdefault("brain", []).append(argv[i + 1])
                i += 1
            else:
                flags.setdefault("brain", []).append("")
        elif name in _VALUE_FLAGS:
            if i + 1 < n and not argv[i + 1].startswith("--"):
                flags[name] = argv[i + 1]
                i += 1
            else:
                flags[name] = None
        else:
            flags[name] = True
        i += 1
    return args, flags


def _brain(flags):
    names = flags.get("brain") or []
    return names[-1] if names else None


def _flag(flags, name):
    v = flags.get(name)
    if isinstance(v, str):
        return v.lower() not in ("false", "0", "no", "off", "")
    return bool(v)


def _int(flags, name, default=None):
    v = flags.get(name)
    return default if v in (None, True, False) else int(v)


def _float(flags, name, default=None):
    v = flags.get(name)
    return default if v in (None, True, False) else float(v)


def _text(args, flags):
    t = flags.get("text")
    if t not in (None, True, False):
        return t
    return " ".join(args) or None


def _run(verb, dir, args, flags):
    if verb == "init":
        names = flags.get("brain") or []
        profile = flags.get("profile") or "balanced"
        embed = flags.get("embed") or "lexical"
        brains = [{"name": n, "profile": profile, "embed": embed} for n in names]
        live = None
        if "live" in flags:
            live = _flag(flags, "live")
        elif _flag(flags, "no-live"):
            live = False
        ac = _int(flags, "auto-consolidate", None)
        ap = _int(flags, "auto-prune", None)
        return OPS["init"](dir, brains=brains, force=_flag(flags, "force"),
                           live=live, auto_consolidate=ac, auto_prune=ap)
    if verb == "info":
        return OPS["info"](dir)
    if verb == "wake":
        return OPS["wake"](dir)
    if verb == "stats":
        return OPS["stats"](dir, brain=_brain(flags))
    if verb == "config":
        key = flags.get("key") or (args[0] if args else None)
        value = flags.get("value")
        if value is None and len(args) > 1:
            value = args[1]
        return OPS["config"](dir, key=key, value=value, brain=_brain(flags),
                             confirm=_flag(flags, "confirm"),
                             show_secrets=_flag(flags, "show-secrets"))
    if verb == "brain-test":
        return OPS["brain-test"](dir, brain=_brain(flags) or "kairos",
                                 k=_int(flags, "k", 3))
    if verb == "llm-stat":
        return OPS["llm-stat"]()
    if verb == "llm-setup":
        tier = flags.get("tier") or (args[0] if args else "3")
        return OPS["llm-setup"](tier)
    if verb == "update":
        return OPS["update"](check=_flag(flags, "check"), pin=flags.get("pin"),
                             status=flags.get("status"),
                             tail=_int(flags, "tail"), dir=dir)
    if verb == "delete":
        return OPS["delete"](dir, brain=_brain(flags),
                             force=_flag(flags, "force"))
    if verb == "query":
        return OPS["query"](dir, brain=_brain(flags), text=_text(args, flags),
                            sql=flags.get("sql"), cue=flags.get("cue"),
                            objects=_flag(flags, "objects"),
                            anchors=_flag(flags, "anchors"),
                            sightings=_flag(flags, "sightings"),
                            k=_int(flags, "k", 8))
    if verb == "prune":
        return OPS["prune"](dir, brain=_brain(flags))
    if verb == "consolidate":
        return OPS["consolidate"](dir, _text(args, flags), brain=_brain(flags),
                                  arousal=_float(flags, "arousal", 0.4))
    if verb == "ingest":
        role = flags.get("role")
        if role in (None, True, False):
            role = "assistant"
        return OPS["ingest"](dir, _text(args, flags), brain=_brain(flags),
                             arousal=_float(flags, "arousal", 0.5),
                             dedup=(_flag(flags, "dedup") if "dedup" in flags else None),
                             role=role)
    if verb == "recall":
        return OPS["recall"](dir, _text(args, flags), k=_int(flags, "k", 8))
    if verb == "ask":
        return OPS["ask"](dir, " ".join(args) or flags.get("text") or "")
    if verb == "doctor":
        return OPS["doctor"]()
    raise ValueError(f"unhandled verb {verb}")


def _emit(out, use_json):
    if use_json:
        print(json.dumps(out, indent=2, default=str))
    elif isinstance(out, dict) and isinstance(out.get("human"), str):
        print(out["human"])
    else:
        print(json.dumps(out, indent=2, default=str))


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 1
    verb = argv[0]
    if verb not in OPS:
        print(USAGE, file=sys.stderr)
        return 1
    args, flags = _parse(argv[1:])
    try:
        out = _run(verb, os.getcwd(), args, flags)
    except Exception as ex:
        print(f"{verb}: {ex}", file=sys.stderr)
        return 1
    _emit(out, bool(flags.get("json")))
    return 0