"""Multimodal embedding client.

These are unit-level and need no server: they pin the request SHAPE, which is
where this breaks silently. The end-to-end path needs llama-server started
with --mmproj, and that failure is loud and expected until then.
"""
import base64
import json

import pytest

from positronic_ai.embed import (embed_with_image, guess_mime, image_part,
                                 prompt_prefix, text_part)


def test_guess_mime():
    assert guess_mime("a.PNG") == "image/png"
    assert guess_mime("scan.JPEG") == "image/jpeg"
    assert guess_mime("animation.webp") == "image/webp"
    assert guess_mime("noext") == "image/png"  # unknown falls back


def test_text_part_shape():
    assert text_part("hello") == {"type": "text", "text": "hello"}


def test_image_part_is_an_inline_data_url():
    blob = b"\x89PNG-fake"
    part = image_part(blob, "image/png")
    assert part["type"] == "image_url"
    url = part["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    payload = url.split(",", 1)[1]
    assert base64.b64decode(payload) == blob


def test_prompt_goes_on_the_text_part_only(monkeypatch):
    """The image half takes no task prompt -- only the text is pair-trained."""
    seen = {}

    def fake_post(parts, url, timeout=300):
        seen["parts"] = parts
        return [0.0] * 768

    monkeypatch.setattr("positronic_ai.embed._post_multimodal", fake_post)
    embed_with_image("a log line", "http://x", image=b"img",
                     mime="image/png", role="query", model="eg2")
    parts = seen["parts"]
    assert parts[0] == {"type": "text", "text": "SearchQuery: a log line"}
    assert parts[1]["type"] == "image_url"


def test_no_prompt_for_bge_model(monkeypatch):
    seen = {}

    def fake_post(parts, url, timeout=300):
        seen["parts"] = parts
        return [0.0] * 1024

    monkeypatch.setattr("positronic_ai.embed._post_multimodal", fake_post)
    embed_with_image("a log line", "http://x", model="bge-m3")
    assert seen["parts"][0] == {"type": "text", "text": "a log line"}


def test_text_only_still_uses_the_content_array(monkeypatch):
    """A caller may use this unconditionally without the two paths
    diverging on prompt handling."""
    seen = {}

    def fake_post(parts, url, timeout=300):
        seen["parts"] = parts
        return [0.0] * 768

    monkeypatch.setattr("positronic_ai.embed._post_multimodal", fake_post)
    embed_with_image("only text", "http://x", model="eg2", role="document")
    assert len(seen["parts"]) == 1
    assert seen["parts"][0]["text"] == "Document: only text"


def test_request_body_is_the_oai_content_array(monkeypatch):
    """Pin the wire shape: input[] of one item holding a content[] array.

    Getting this wrong yields a text-only vector with no error, which is
    exactly the silent failure this whole change exists to avoid.
    """
    captured = {}

    class _Resp:
        def read(self):
            return json.dumps({"data": [{"embedding": [0.5, 0.25]}]}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=300):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        return _Resp()

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    vec = embed_with_image("hello", "http://host:8091", image=b"xx",
                           mime="image/jpeg", model="eg2")
    assert vec == [0.5, 0.25]
    assert captured["url"] == "http://host:8091/v1/embeddings"
    item = captured["body"]["input"][0]
    assert set(item) == {"content"}
    types = [p["type"] for p in item["content"]]
    assert types == ["text", "image_url"]
    assert item["content"][0]["text"] == "Document: hello"
    assert item["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,")


def test_role_still_selects_the_pair():
    assert prompt_prefix("eg2", "document") != prompt_prefix("eg2", "query")
