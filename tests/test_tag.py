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

"""Tag verb round-trip on temp brains — synthetic data only."""
import json
import tempfile

from positronic_ai.brains import init_brain
from positronic_ai.ops import ingest, tag


def _features(d, brain, eid):
    import sqlite3
    db = f"{d}/.positronic/brains/{brain}/memory.db"
    c = sqlite3.connect(db)
    row = c.execute("SELECT features_json FROM episode WHERE id=?",
                    (eid,)).fetchone()
    c.close()
    return json.loads(row[0])


def test_ingest_auto_tags_scam_and_manual_corrects():
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        out = ingest.run(d, "You are the beneficiary of an inheritance. "
                            "Wire transfer fee required.",
                         subject="Inheritance claim",
                         sender="prince@unknown.example",
                         message_id="scam-1@t")
        assert out.get("threat", {}).get("tag") == "scam"
        feat = _features(d, "kairos", out["episode_id"])
        assert feat["threat_tag"] == "scam"
        fixed = tag.run(d, brain="kairos", episode_id=out["episode_id"],
                        tag="clean")
        assert fixed["ok"] is True
        assert _features(d, "kairos", out["episode_id"])["threat_tag"] == "clean"


def test_tag_by_message_id_and_rejects_bad_tag():
    with tempfile.TemporaryDirectory() as d:
        init_brain(d, "kairos", "balanced", "lexical")
        out = ingest.run(d, "Quarterly report draft attached.",
                         subject="Q3 report", sender="boss@company.com",
                         message_id="ok-1@t", threat=False)
        assert "threat" not in out
        bad = tag.run(d, brain="kairos", message_id="ok-1@t", tag="malware")
        assert bad["ok"] is False
        good = tag.run(d, brain="kairos", message_id="ok-1@t", tag="spam")
        assert good["ok"] is True and good["tag"] == "spam"
        missing = tag.run(d, brain="kairos", message_id="nope@t", tag="spam")
        assert missing["ok"] is False
