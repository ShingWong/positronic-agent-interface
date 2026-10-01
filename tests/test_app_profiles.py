"""Per-application knobs: brain-scoped engine config and threat specs."""
import pytest

from positronic_ai.config import load_config, set_key
from positronic_ai.engine import brain_engine_config
from positronic_ai.threat import merge_spec, score_threat, spec_from_config


# The inert-knob bug: a per-brain threshold was written to config and never
# read, because every MemoryEngine was built without config.
def test_brain_threshold_reaches_the_engine(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine

    dirpath = str(tmp_path)
    init_brain(dirpath, "b1", profile="archival")
    set_key(dirpath, "threshold", 0.9, brain="b1")
    cfg = load_config(dirpath)
    assert cfg["brains"]["b1"]["threshold"] == 0.9, "written to config"
    _, e = open_engine(dirpath, "b1")
    assert e.base_cfg["threshold"] == 0.9, \
        "and now actually reaches the engine"


def test_two_brains_can_hold_different_thresholds(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.engine import open_engine

    dirpath = str(tmp_path)
    init_brain(dirpath, "loose", profile="balanced")
    init_brain(dirpath, "strict", profile="balanced")
    set_key(dirpath, "threshold", 0.2, brain="loose")
    set_key(dirpath, "threshold", 0.9, brain="strict")
    _, loose = open_engine(dirpath, "loose")
    _, strict = open_engine(dirpath, "strict")
    assert loose.base_cfg["threshold"] == 0.2
    assert strict.base_cfg["threshold"] == 0.9


def test_nested_engine_block_is_honoured():
    got = brain_engine_config({"engine": {"w_novelty": 0.2, "induce_after": 7}})
    assert got == {"w_novelty": 0.2, "induce_after": 7}


def test_nested_wins_over_legacy_flat_threshold():
    got = brain_engine_config({"threshold": 0.7,
                               "engine": {"threshold": 0.1}})
    assert got["threshold"] == 0.1


def test_unknown_engine_knob_is_rejected_not_ignored(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.config import save_config

    dirpath = str(tmp_path)
    init_brain(dirpath, "b2", profile="balanced")
    cfg = load_config(dirpath)
    cfg["brains"]["b2"]["engine"] = {"w_noveltyy": 0.3}   # typo
    with pytest.raises(ValueError, match="unknown knob"):
        save_config(dirpath, cfg)


# A new category must need config only -- no code, no release.
def test_new_category_from_config_only():
    override = {"categories": [{
        "tag": "policy", "priority": 95, "threshold": 1.0,
        "signals": [{"id": "policy-lexicon", "kind": "lexicon",
                     "weight": 1.0,
                     "terms": ["material nonpublic", "insider trading"]}],
    }]}
    spec = merge_spec(override)
    hit = score_threat("a@corp.com", "Heads up",
                       "this contains material nonpublic information",
                       5, spec=spec)
    assert hit["tag"] == "policy"
    assert "policy-lexicon" in hit["reasons"]
    # The pre-existing categories must survive the merge untouched. The link
    # host must differ from the sender domain, or there is no foreign link to
    # find -- sender evil.com linking to evil.com is legitimately clean.
    phish = score_threat("e@evil.com", "Sign in to Adobe",
                         "https://phish.example/login", 0, spec=spec)
    assert phish["tag"] == "phishing", "override must not disturb defaults"


def test_consumer_and_enterprise_differ_only_by_config():
    enterprise = merge_spec({"categories": [{
        "tag": "policy", "priority": 95, "threshold": 1.0,
        "signals": [{"id": "policy-lexicon", "kind": "lexicon",
                     "weight": 1.0,
                     "terms": ["material nonpublic"]}]}]})
    consumer = merge_spec(None)
    mail = ("a@corp.com", "FY", "material nonpublic guidance", 5)
    assert score_threat(*mail, spec=enterprise)["tag"] == "policy"
    assert score_threat(*mail, spec=consumer)["tag"] == "clean"


def test_disabled_threat_scores_everything_clean():
    spec = spec_from_config({"threat": False})
    assert spec.get("disabled") is True
    assert score_threat("e@evil.com", "Sign in",
                        "https://evil.com/login", 0, spec=spec)["tag"] == "clean"


def test_bad_threat_config_is_rejected_with_a_useful_message():
    from positronic_ai.threat import validate_spec_override
    with pytest.raises(ValueError, match="needs a pattern"):
        validate_spec_override({"categories": [{
            "tag": "x", "priority": 1, "threshold": 1.0,
            "signals": [{"id": "x", "kind": "custom_text"}]}]})
    with pytest.raises(ValueError, match="unknown signal kind"):
        validate_spec_override({"categories": [{
            "tag": "x", "priority": 1, "threshold": 1.0,
            "signals": [{"id": "x", "kind": "telepathy"}]}]})
    with pytest.raises(ValueError, match="duplicate"):
        validate_spec_override({"categories": [
            {"tag": "x", "priority": 1, "threshold": 1.0,
             "signals": [{"id": "a", "kind": "new_sender"}]},
            {"tag": "x", "priority": 2, "threshold": 1.0,
             "signals": [{"id": "b", "kind": "new_sender"}]}]})
