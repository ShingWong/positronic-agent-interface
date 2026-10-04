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

"""ingest-log verb tests: file -> brain under a validated schema."""
import datetime
from datetime import timezone


def _fixture(dir_):
    """60 syslog lines across 3 pids x 3 classes; validates 8/8 clean."""
    lines = []
    t = datetime.datetime(2026, 9, 27, 3, 27, 45, tzinfo=timezone.utc)
    msgs = ["connect from unknown[1.2.3.4]",
            "disconnect from unknown[1.2.3.4]",
            "warning: host[5.6.7.8]: SASL LOGIN authentication failed"]
    for i in range(60):
        t += datetime.timedelta(seconds=7)
        lines.append(
            f"{t.strftime('%b %d %H:%M:%S')} mx1 postfix/smtpd"
            f"[{101 + i % 3}]: {msgs[i % 3]}")
    log = dir_ / "mini.log"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sch = dir_ / "mini_schema.yaml"
    sch.write_text(
        "software: postfix-mini\n"
        "identity_key: pid\n"
        "time_field: stamp\n"
        "record_layers:\n"
        "  envelope:\n"
        "    - {path: stamp, role: context, type: datetime, meaning: when}\n"
        "    - {path: pid, role: identity, type: integer, meaning: process}\n"
        "    - {path: ident, role: context, type: string, meaning: daemon}\n"
        "  payload:\n"
        "    - {path: message, role: content, type: string, meaning: line}\n"
        "classes:\n"
        "  - {name: connect, template: \"connect from <HOST>\", meaning: m,"
        " normal: true, retention: keep}\n"
        "  - {name: disconnect, template: \"disconnect from <HOST>\","
        " meaning: m, normal: true, retention: demote}\n"
        "  - {name: sasl, template: \"warning SASL LOGIN authentication"
        " failed\", meaning: m, normal: false, retention: keep-extended}\n",
        encoding="utf-8")
    return str(log), str(sch)


def test_ingest_log_dry_run_writes_nothing(tmp_path):
    from positronic_ai.ops.ingest_log import run
    log, sch = _fixture(tmp_path)
    out = run(str(tmp_path), schema=sch, file=log, dry_run=True)
    assert out["ok"] is True and out["dry_run"] is True
    assert out["records_in_window"] == 60
    assert out["coverage"]["records_unclassified"] == 0
    assert not (tmp_path / ".positronic").exists()


def test_ingest_log_wet_run_stores_episodes(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine
    from positronic_ai.ops.ingest_log import run
    log, sch = _fixture(tmp_path)
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    out = run(str(tmp_path), schema=sch, file=log, brain="kairos")
    assert out["ok"] is True
    assert out["ingest"]["ingested"] > 0
    assert out["ingest"]["records_seen"] == 60
    s, _e = open_engine(str(tmp_path), "kairos")
    n = s.conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
    assert n == out["ingest"]["ingested"]


def test_ingest_log_window_slices_time(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest_log import run
    log, sch = _fixture(tmp_path)
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    out = run(str(tmp_path), schema=sch, file=log, brain="kairos",
              since="2026-09-27T03:30:00", until="2026-09-27T03:32:00")
    assert out["ok"] is True
    assert 0 < out["records_in_window"] < 60


def test_ingest_log_bad_schema_writes_nothing(tmp_path):
    """Validation runs before any write: a schema whose classes match
    nothing fails here, not halfway through the ingest."""
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine
    from positronic_ai.ops.ingest_log import run
    log, sch = _fixture(tmp_path)
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    with open(sch, "a", encoding="utf-8") as f:
        f.write('  - {name: phantom, template: "wording in no log line",'
                ' meaning: m, normal: true, retention: keep}\n')
    out = run(str(tmp_path), schema=sch, file=log, brain="kairos")
    assert out["ok"] is False and out["stage"] == "validate"
    s, _e = open_engine(str(tmp_path), "kairos")
    n = s.conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
    assert n == 0


def test_ingest_log_requires_schema_and_file(tmp_path):
    import pytest

    from positronic_ai.ops.ingest_log import run
    with pytest.raises(ValueError, match="--schema"):
        run(str(tmp_path), schema=None, file="/x")
    with pytest.raises(ValueError, match="--file"):
        run(str(tmp_path), schema="/y", file=None)


def test_ingest_log_skip_validate_ingests_quiet_window(tmp_path):
    """A valid schema on a quiet window: validation fails (rare classes
    absent) but --skip-validate ingests anyway, because the schema was
    proven elsewhere and the window is merely quiet."""
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest_log import run
    log, sch = _fixture(tmp_path)
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    with open(sch, "a", encoding="utf-8") as f:
        f.write('  - {name: phantom, template: "wording in no log line",'
                ' meaning: m, normal: true, retention: keep}\n')
    out = run(str(tmp_path), schema=sch, file=log, brain="kairos",
              skip_validate=True)
    assert out["ok"] is True and out["skipped_validation"] is True
    assert out["validated"] is False
    assert out["ingest"]["ingested"] > 0
