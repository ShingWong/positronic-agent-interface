# Findings: two signals that report health while stale (2026-10-08)

Discovered during the web2 upgrade from memeng v0.2.0 to v0.3.0.
No code changed yet; these are reports, not fixes.

## 1. update --check reports "behind: 0" on the hosts most likely to be stale

Symptom (web2, before upgrade):

    $ positronic update --check --json
    {"behind": 0, "engramTagDiff": null, "npmOutdated": false, "logTail": []}

Reality: .positronic/config.json pinned engram_tag v0.2.0 while the remote
tag was v0.3.0, and the pip PAI copy was a 2026-09-14 snapshot. The host has
no engram checkout (the tier probe itself reported "engram: missing"), so the
checker had nothing to compare and returned success instead of "cannot
determine". A blind check and a clean check are the same JSON.

Evidence: web2, 2026-10-08, git ls-remote shows refs/tags/v0.3.0; pip
direct_url.json showed requested_revision v0.2.0 before the upgrade.

Direction: on pip-engine hosts, compare importlib.metadata (or pip
direct_url.json requested_revision) against git ls-remote tags. When no
engine source is resolvable, report status "unknown" with exit code 0 only
if explicitly asked to; never report behind: 0 for an undeterminable state.

## 2. doctor reports "bge: down" while the service answers

Symptom (web2):

    $ positronic info --json   # tiers: {"bge": "down"}
    doctor: bge health probe failed

Reality: GET http://10.0.0.19:8090/v1/models returns HTTP 200 with
{"models":[{"name":".../bge-m3-Q8_0.gguf", ...}]}. The service is up and the
model is loaded; the probe disagrees with the endpoint it probes.

Evidence: web2, 2026-10-08, curl -s -m 5 returned the model list above.

Direction: state which endpoint and which success criterion the probe uses,
and disclose it in output (the rule from TEST_HYGIENE: a measurement that
cannot be re-derived is an anecdote). If /v1/models is the liveness check,
a 200 must count as up.

## Related: same-version pip upgrade silently skipped PAI

    pip3 install --user --upgrade git+...positronic-agent-interface.git@main
    -> "Successfully installed ... memeng positronic-logschema" (PAI absent)

PAI stayed at the 2026-09-14 feat/pai snapshot because its version string
(0.1.0) matched; direct_url.json still showed requested_revision feat/pai
afterwards. Needed --force-reinstall --no-deps. Either version strings bump
with meaningful changes, or the documented upgrade path forces reinstall.

Cross-reference (engram repo): engine/pyproject.toml at tag v0.3.0 says
version = "0.2.1". The tag and the package version disagree, which is one
more reason a version-based check cannot be trusted as-is.
