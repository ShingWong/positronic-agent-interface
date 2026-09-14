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

import xml.etree.ElementTree as ET
import zipfile


def test_html_to_markdown_keeps_structure():
    from positronic_ai.extract.html import html_to_markdown
    html = "<h1>Q3 Results</h1><p>Revenue up 12%.</p><ul><li>Apples</li><li>Oranges</li></ul>"
    md = html_to_markdown(html)
    assert "Q3 Results" in md
    assert "Revenue up 12%" in md
    assert "Apples" in md and "Oranges" in md
    assert "<h1>" not in md and "<li>" not in md

def test_html_drops_script_style():
    from positronic_ai.extract.html import html_to_markdown
    md = html_to_markdown("<style>.x{color:red}</style><script>var t=1;</script><p>Hi</p>")
    assert "color" not in md and "var t" not in md and "Hi" in md

def test_md_normalize_collapses_whitespace():
    from positronic_ai.extract.md import md_normalize
    assert md_normalize("# T\n\n\nBody   with   spaces\n\n\n") == "# T\n\nBody with spaces"

def _mk_docx(path, paras):
    import zipfile
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paras)
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    ctype = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ctype)
        z.writestr("word/document.xml", doc)

def test_office_docx_paragraphs(tmp_path):
    from positronic_ai.extract.office import office_to_markdown
    p = tmp_path / "t.docx"
    _mk_docx(str(p), ["Hello world", "Second para"])
    md = office_to_markdown(str(p))
    assert "Hello world" in md and "Second para" in md


def _mk_xlsx(path, sheets):
    """sheets: {sheet_name: [[cell, ...], ...]}"""
    import openpyxl
    wb = openpyxl.Workbook()
    first = True
    for name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(name)
        first = False
        ws.title = name
        for row in rows:
            ws.append(row)
    wb.save(str(path))
    return str(path)


def _mk_odt_ods(kind, path, blocks):
    """kind: 'odt' or 'ods'. blocks: list of table row-lists."""
    NS = "urn:oasis:names:tc:opendocument:xmlns:{}"
    if kind == "odt":
        table_ns, text_ns = "table:1.0", "text:1.0"
        row_tag, cell_tag = "table-row", "table-cell"
        p_tag = "p"
    else:
        table_ns = "table:1.0"
        text_ns = "text:1.0"
        row_tag, cell_tag = "table-row", "table-cell"
        p_tag = "p"
    root = ET.Element(f"{{{NS.format(table_ns)}}}document")
    body = ET.SubElement(root, f"{{{NS.format(text_ns)}}}body")
    table_el = ET.SubElement(body, f"{{{NS.format(table_ns)}}}table")
    for rows in blocks:
        for row in rows:
            tr = ET.SubElement(table_el, f"{{{NS.format(table_ns)}}}{row_tag}")
            for cell in row:
                tc = ET.SubElement(tr, f"{{{NS.format(table_ns)}}}{cell_tag}")
                p = ET.SubElement(tc, f"{{{NS.format(text_ns)}}}{p_tag}")
                p.text = str(cell)
    xml = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    ctype = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats'
             '.org/package/2006/content-types"/>')
    with zipfile.ZipFile(str(path), "w") as z:
        z.writestr("[Content_Types].xml", ctype)
        z.writestr("content.xml", xml)
    return str(path)


def test_office_xlsx_rows(tmp_path):
    from positronic_ai.extract.office import office_to_markdown
    p = _mk_xlsx(str(tmp_path / "t.xlsx"),
                 {"Sheet1": [["a", "b"], ["1", "2"], ["3", "4"]]})
    md = office_to_markdown(str(p))
    assert "a | b" in md and "1 | 2" in md and "3 | 4" in md


def test_office_ods_rows(tmp_path):
    from positronic_ai.extract.office import office_to_markdown
    p = _mk_odt_ods("ods", str(tmp_path / "t.ods"), [[["a", "b"], ["1", "2"]]])
    md = office_to_markdown(str(p))
    assert "a | b" in md and "1 | 2" in md


def test_office_odt_paragraphs(tmp_path):
    from positronic_ai.extract.office import office_to_markdown
    p = _mk_odt_ods("odt", str(tmp_path / "t.odt"), [[["Hello world"], ["Second para"]]])
    md = office_to_markdown(str(p))
    assert "Hello world" in md and "Second para" in md



def test_office_unknown_suffix_raises(tmp_path):
    import pytest

    from positronic_ai.extract.office import office_to_markdown
    with pytest.raises(ValueError):
        office_to_markdown(str(tmp_path / "t.funky"))
