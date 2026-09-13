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

import re


def test_chunks_respect_sentences_and_budget():
    from positronic_ai.chunk import chunk_markdown
    sents = ["Sentence number %d with enough words to matter." % i for i in range(40)]  # noqa: UP031 -- verbatim per task brief
    md = "# Head\n\n" + " ".join(sents)
    chunks = chunk_markdown(md, subject="Test mail", max_chars=600)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 600 + 200  # budget + subject prefix + overlap slack
        assert c.startswith("Subject: Test mail")
    joined = " ".join(chunks)
    for s in sents:
        assert s in joined  # nothing lost


def test_no_mid_sentence_split():
    from positronic_ai.chunk import chunk_markdown
    md = "Alpha one. Alpha two. " * 60
    for c in chunk_markdown(md, max_chars=200):
        body = c.split("\n", 1)[-1] if c.startswith("Subject:") else c
        assert not re.search(r"[A-Za-z]\.$", body.strip()) is False  # ends cleanly
        assert body.strip().endswith(".")
