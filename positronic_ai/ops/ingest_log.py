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

"""ingest-log verb — a log file into a brain under a validated schema.

The path today's forensics hand-rolled per case (detect -> read -> classify
-> ingest_records), as one command with a dry-run. Validation runs BEFORE
anything is written: an unvalidated schema fails here, not halfway through
a 300k-line ingest. Dry-run writes nothing at all (no brain needed) and
reports what WOULD happen: records in window, class coverage, retention
drop counts -- the numbers that decide whether the schema fits the file.
"""
import logging

from memeng.ingest import ingest_records

from ..config import load_config
from ..engine import open_engine

log = logging.getLogger(__name__)


def run(dir, *, schema, file, brain=None, domain=None, stream=None,
        since=None, until=None, limit=None, dry_run=False,
        skip_validate=False) -> dict:
    from logschema.classify import build_classifier
    from logschema.substrate import detect, read
    from logschema.validate import load_schema, validate

    if not schema:
        raise ValueError("--schema is required (path to a schema.yaml)")
    if not file:
        raise ValueError("--file is required (path to the log file)")
    cfg = load_config(dir)
    name = brain or next(iter(cfg.get("brains", {})), None)
    if not name and not dry_run:
        raise ValueError("no brains configured — run positronic init")

    schema_d = load_schema(schema)
    tf = schema_d.get("time_field")
    batch = []
    for r in read(detect(file), limit=(limit or 400_000)):
        if limit is not None and len(batch) >= limit:
            break
        # Window on the schema's clock, ISO-lexicographic: one file, one
        # stamp format, so string order IS time order. Mixed offsets would
        # break this silently -- logschema stamps are normalized at read,
        # which is what makes the comparison honest.
        stamp = r.get(tf) if tf else None
        if since is not None and (stamp is None or stamp < since):
            continue
        if until is not None and (stamp is None or stamp > until):
            continue
        batch.append(r)

    rep = validate(schema_d, batch, schema_path=str(schema),
                   path=str(file))
    # Validation is a property of (schema, corpus), proven at authoring time
    # -- this schema passes 8/8 on the real 300k-line maillog. Re-proving it
    # per WINDOW conflates "wrong schema" with "quiet window": 10 of 73
    # classes legitimately match nothing in a 4-minute slice (rare bounces),
    # and refusing the ingest on those grounds is the gate misfiring.
    # --skip-validate is the operator asserting the schema was proven
    # elsewhere; it is explicit because silent unvalidated ingest is how a
    # typo'd retention becomes policy. Coverage still reports what the
    # window actually contains either way.
    if not rep.ok and not skip_validate:
        return {"ok": False, "stage": "validate",
                "failures": [r.as_dict() for r in rep.failures],
                "human": "schema does not fit this file: "
                         + "; ".join(f.name for f in rep.failures)}
    classify, coverage = build_classifier(schema_d, batch)

    if dry_run:
        return {"ok": True, "dry_run": True, "brain": name,
                "records_in_window": len(batch), "coverage": coverage,
                "validated": bool(rep.ok), "skipped_validation": skip_validate,
                "human": (f"{len(batch)} records in window, "
                          f"{coverage['records_classified']} classified "
                          f"({coverage['records_unclassified']} unclassified, "
                          f"{coverage['classes_claimed']} classes claim)")} 

    _s, e = open_engine(dir, name)
    dom = domain or name
    e.register_domain(dom, retention_profile="balanced")
    stream_name = stream or f"{dom}:maillog"
    try:
        e.attach_stream(stream_name, dom)
    except Exception:  # noqa: BLE001 -- re-ingest into a live stream
        log.debug("ingest-log: stream %s already attached", stream_name)
    ing = ingest_records(e, schema_d, batch, stream=stream_name,
                         classify=classify)
    out = {"ok": True, "brain": name, "domain": dom, "stream": stream_name,
           "records_in_window": len(batch), "coverage": coverage,
           "validated": bool(rep.ok), "skipped_validation": skip_validate,
           "ingest": ing.as_dict()}
    out["human"] = (f"{ing.ingested}/{len(batch)} events to gate "
                    f"({ing.dropped} retention-dropped) on {stream_name}")
    return out
