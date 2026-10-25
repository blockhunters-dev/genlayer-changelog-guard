import copy
import json

import pytest

from conftest import CONTRACT, FIXTURE, ROOT, URL, VERDICT, mock_llm, mock_page

REAL_PAGE = (ROOT / "tests" / "fixtures" / "docs_changelog_page_trimmed.html").read_text()
from gltest.direct import load_contract_class


def test_submit_stores_verdict_and_latest(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("Bradbury-Phase2", "v0.6.0-rc.2", URL)

    rel = guard.get_release("bradbury-phase2", "0.6.0-rc.2")
    assert rel["mandatory"] is True and rel["breaking"] is True
    assert rel["deadline"] == "2026-10-22T14:00:00Z"
    assert rel["env_changes"] == ["genlayernode_rollup_genlayerchainrpckey"]
    assert rel["source_url"] == URL
    assert guard.get_latest("bradbury-phase2")["version"] == "0.6.0-rc.2"
    assert guard.get_latest("unknown-net") == {}


@pytest.mark.parametrize(
    "bad",
    [
        "http://docs.genlayer.com/x",
        "https://evil.example/docs.genlayer.com",
        "https://docs.genlayer.com@evil.example/x",
        "https://github.com/someoneelse/repo/releases",
        "https://github.com/genlayerlabs/../evil/x",
        "https://github.com/genlayerlabs/node/issues/1",
        "https://github.com/genlayerlabs/node/pull/1",
        "https://github.com/genlayerlabs/node/blob/abc123/CHANGELOG.md",
        "https://raw.githubusercontent.com/genlayerlabs/node/main/CHANGELOG.md",
        "https://docs.genlayer.com/validators/changelog?x=1",
        "https://docs.genlayer.com/validators/%2e%2e/x",
    ],
)
def test_rejects_disallowed_urls(direct_vm, guard, bad):
    with direct_vm.expect_revert("allowed source"):
        guard.submit("bradbury-phase2", "v0.6.0-rc.2", bad)


def test_rejects_duplicate_and_wrong_version(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    with direct_vm.expect_revert("already"):
        guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    direct_vm.clear_mocks()
    mock_page(direct_vm, body=FIXTURE + "\n# v0.7.0\nnotes\n")
    mock_llm(direct_vm, VERDICT)
    with direct_vm.expect_revert("different version"):
        guard.submit("bradbury-phase2", "v0.7.0", URL)


def test_latest_does_not_regress(direct_vm, guard):
    mock_page(direct_vm)
    for v in ("v0.6.0", "v0.5.9"):
        direct_vm.clear_mocks()
        mock_page(direct_vm, body="# v0.6.0\nnotes\n# v0.5.9\nnotes\n")
        mock_llm(direct_vm, {**VERDICT, "version": v})
        guard.submit("bradbury-phase2", v, URL)
    assert guard.get_latest("bradbury-phase2")["version"] == "0.6.0"


def _validator_agrees(direct_vm, guard, validator_verdict):
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    direct_vm.clear_mocks()
    mock_page(direct_vm)
    mock_llm(direct_vm, validator_verdict)
    return direct_vm.run_validator()


def test_validator_accepts_tolerable_difference(direct_vm, guard):
    other = copy.deepcopy(VERDICT)
    other["deadline"] = "2026-10-22T16:00:00+02:00"  # same instant, other offset
    other["config_changes"] = [k.upper() for k in VERDICT["config_changes"]]
    assert _validator_agrees(direct_vm, guard, other)


@pytest.mark.parametrize(
    "field,value",
    [
        ("breaking", False),
        ("mandatory", False),
        ("deadline", "2026-10-23T14:00:00Z"),
        ("config_changes", ["rollup.provider"]),  # Jaccard 1/3 < 0.8
    ],
)
def test_validator_rejects_material_difference(direct_vm, guard, field, value):
    other = {**VERDICT, field: value}
    assert not _validator_agrees(direct_vm, guard, other)


def test_validator_redoes_extraction_not_just_format(direct_vm, guard):
    """A leader result that is well-formed but contradicted by the page must fail."""
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    direct_vm.clear_mocks()
    mock_page(direct_vm)
    mock_llm(direct_vm, {**VERDICT, "breaking": False})
    assert not direct_vm.run_validator()


def test_accepts_tag_pinned_sources(direct_vm, guard):
    for u in (
        "https://github.com/genlayerlabs/genlayer-node/releases/tag/v0.6.0-rc.2",
        "https://raw.githubusercontent.com/genlayerlabs/genlayer-node/refs/tags/v0.6.0-rc.2/CHANGELOG.md",
    ):
        direct_vm.clear_mocks()
        mock_page(direct_vm, url=u, body="# v0.6.0\nnotes\n")
        mock_llm(direct_vm, {**VERDICT, "version": "0.6.0"})
        guard.submit(f"net-{len(u)}", "0.6.0", u)


@pytest.mark.parametrize("v", ["0.6", "0.6.0.0", "v0.6", "0.6.0-rc", "latest", ""])
def test_rejects_non_canonical_versions(direct_vm, guard, v):
    with direct_vm.expect_revert("version must look like"):
        guard.submit("bradbury-phase2", v, URL)


def test_actions_stored_as_bounded_free_text(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, {**VERDICT, "actions": ["  Set the  node password ", "x" * 500, 7, ""] + ["a"] * 30})
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    acts = guard.get_release("bradbury-phase2", "0.6.0-rc.2")["actions"]
    assert acts[0] == "Set the node password"
    assert len(acts[1]) == 200 and len(acts) == 20


def test_validator_does_not_compare_actions(direct_vm, guard):
    assert _validator_agrees(direct_vm, guard, {**VERDICT, "actions": ["reworded: download the manifest"]})


@pytest.mark.parametrize("field", ["mandatory", "breaking"])
@pytest.mark.parametrize("bad", ["false", "true", "False", "no", 0, 1, None, "missing"])
def test_rejects_non_boolean_safety_fields(direct_vm, guard, field, bad):
    verdict = dict(VERDICT)
    if bad == "missing":
        del verdict[field]
    else:
        verdict[field] = bad
    mock_page(direct_vm)
    mock_llm(direct_vm, verdict)
    with direct_vm.expect_revert("invalid LLM verdict"):
        guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0-rc.2") == {}


def test_rejects_unparseable_deadline(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, {**VERDICT, "deadline": "next tuesday"})
    with direct_vm.expect_revert("invalid LLM verdict"):
        guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)


def test_validator_rejects_leader_with_string_boolean(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert not direct_vm.run_validator(leader_result={**VERDICT, "breaking": "false"})


@pytest.mark.parametrize("out", ["I cannot help with that.", "", "{not json", "[1, 2]"])
def test_rejects_non_json_llm_output(direct_vm, guard, out):
    mock_page(direct_vm)
    direct_vm.mock_llm(r"RELEASE NOTES", out)
    with direct_vm.expect_revert():
        guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0-rc.2") == {}


def test_fenced_json_and_null_deadline(direct_vm, guard):
    mock_page(direct_vm)
    direct_vm.mock_llm(r"RELEASE NOTES", "```json\n" + json.dumps({**VERDICT, "deadline": None}) + "\n```")
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0-rc.2")["deadline"] is None


@pytest.mark.parametrize(
    "tamper",
    [
        {"extra_key": "payload"},
        {"source_url": "https://evil.example"},
        {"config_changes": ["Rollup.Provider", "consensus.chainid", "consensus.manifestpath"]},
        {"version": "v0.6.0-rc.2"},
        {"deadline": "2026-10-22T16:00:00+02:00"},
    ],
)
def test_validator_rejects_non_canonical_leader_result(direct_vm, guard, tamper):
    mock_page(direct_vm)
    mock_llm(direct_vm, VERDICT)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    canonical = guard.get_release("bradbury-phase2", "0.6.0-rc.2")
    canonical.pop("network"), canonical.pop("source_url")
    assert direct_vm.run_validator(leader_result=canonical)
    assert not direct_vm.run_validator(leader_result={**canonical, **tamper})


def test_stored_verdict_has_only_canonical_keys(direct_vm, guard):
    mock_page(direct_vm)
    mock_llm(direct_vm, {**VERDICT, "extra_key": "x"})
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert set(guard.get_release("bradbury-phase2", "0.6.0-rc.2")) == {
        "version", "mandatory", "deadline", "breaking", "config_changes",
        "env_changes", "actions", "network", "source_url",
    }


def test_oversized_page_is_truncated_before_prompting(direct_vm, guard):
    from conftest import mock_page as _mock_page

    _mock_page(direct_vm, body="# v0.6.0-rc.2\nHEADMARK " + "A" * 40000 + " TAILMARK")
    # Mock only matches prompts that kept the head and cut the tail.
    direct_vm.mock_llm(r"(?s)^(?=.*HEADMARK)(?!.*TAILMARK).*RELEASE NOTES", json.dumps(VERDICT))
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0-rc.2")["version"] == "0.6.0-rc.2"


def test_real_docs_page_reaches_llm_as_text(direct_vm, guard):
    """Trimmed real page: changelog starts after 31k chars of markup, as on the live docs site."""
    from conftest import ROOT

    page = (ROOT / "tests" / "fixtures" / "docs_changelog_page_trimmed.html").read_text()
    assert page.index("Check WebDriver rendering") > 30000  # raw truncation would lose it
    mock_page(direct_vm, body=page)
    # Only matches a prompt that has the real release text and no markup.
    direct_vm.mock_llm(
        r"(?s)^(?!.*<script)(?!.*<div)(?!.*<style).*RELEASE NOTES.*Check WebDriver rendering",
        json.dumps({**VERDICT, "version": "0.6.0-rc.2"}),
    )
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0-rc.2")["version"] == "0.6.0-rc.2"



def _prompt_probe(direct_vm, guard, body, needle_ok, needle_bad=None):
    """Submit `body` and assert the prompt the LLM saw contains needle_ok (and not needle_bad)."""
    mock_page(direct_vm, body=body)
    bad = f"(?!.*{needle_bad})" if needle_bad else ""
    direct_vm.mock_llm(rf"(?s)^{bad}.*RELEASE NOTES.*{needle_ok}", json.dumps(VERDICT))
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)


def test_markdown_body_is_not_stripped(direct_vm, guard):
    _prompt_probe(direct_vm, guard, "# v0.6.0-rc.2\nset `<NODE_PASSWORD>` when a < b and c > d", "<NODE_PASSWORD>")


def test_unclosed_script_and_comment_do_not_hang_or_leak(direct_vm, guard):
    body = "<!doctype html><html><h2>v0.6.0-rc.2</h2>" + "<script>x" * 20000 + "<!-- never closed"
    _prompt_probe(direct_vm, guard, body, "", needle_bad="<script")


def test_html_script_content_and_entities(direct_vm, guard):
    body = "<!DOCTYPE html><html><H2>v0.6.0-rc.2</H2><SCRIPT>evil()</SCRIPT><p>a &amp; b</p><style>p{}</style></html>"
    _prompt_probe(direct_vm, guard, body, "a & b", needle_bad="evil")


def test_raw_body_is_capped_before_parsing(direct_vm, guard):
    body = "<!doctype html><html><h2>v0.6.0-rc.2</h2>" + "<b>" * 600000 + " TAILMARK"
    _prompt_probe(direct_vm, guard, body, "", needle_bad="TAILMARK")


def test_env_changes_jaccard_boundary(direct_vm, guard):
    envs = ["A_ONE", "B_TWO", "C_THREE", "D_FOUR", "E_FIVE"]
    base = {**VERDICT, "env_changes": envs}
    mock_page(direct_vm)
    mock_llm(direct_vm, base)
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    # 5 shared of 6 total = 0.833 >= 0.8 -> agree; 4 of 6 = 0.667 -> disagree
    for other, expected in ((envs + ["F_SIX"], True), (envs[:4] + ["F_SIX", "G_SEVEN"], False)):
        direct_vm.clear_mocks()
        mock_page(direct_vm)
        mock_llm(direct_vm, {**VERDICT, "env_changes": other})
        assert direct_vm.run_validator() is expected


def test_length_changing_lowercase_does_not_misalign_script_stripping(direct_vm, guard):
    # "İ".lower() is two characters; indices into a lowercased copy would drift.
    body = "<!doctype html><html><h2>v0.6.0-rc.2</h2>" + "İ" * 50 + "<script>LEAKED_PAYLOAD()</script><p>kept text</p></html>"
    _prompt_probe(direct_vm, guard, body, "kept text", needle_bad="LEAKED_PAYLOAD")


def test_watchtower_api_copy_is_pinned_source_revision():
    """Copy == pinned hash == genlayer-watchtower docs/API.md at commit ef0e47f (not HEAD)."""
    import hashlib
    import subprocess

    from conftest import ROOT

    pin_sha = "2cc5b6a14a570fbc1aea249b755bf4f237023e43df36b9efbbb1d29764222dba"
    pin_commit = "ef0e47f4fe7c56325afce7d4ebaba503801d0b03"
    repo = "../watchlayer"
    copy = (ROOT / "docs" / "WATCHTOWER_API.md").read_bytes()
    assert hashlib.sha256(copy).hexdigest() == pin_sha
    src = subprocess.run(
        ["git", "-C", repo, "show", f"{pin_commit}:docs/API.md"], capture_output=True
    )
    if src.returncode != 0:
        pytest.skip("watchtower repo not available here")
    assert src.stdout == copy


# ------------------------------------------------------------- release section trimming (real page)

def test_section_trimming_picks_requested_version(direct_vm, guard):
    """Real docs page: the prompt holds only the asked version's section, not its neighbours."""
    mock_page(direct_vm, body=REAL_PAGE)
    # rc.2 section: its own text, nothing from rc.1 ("v0.6 is a breaking release") or nav markup.
    direct_vm.mock_llm(
        r"(?s)^(?!.*v0\.6 is a breaking release)(?!.*Welcome to GenLayer)(?!.*<h2).*RELEASE NOTES.*Check WebDriver rendering",
        json.dumps({**VERDICT, "version": "0.6.0-rc.2"}),
    )
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    # v0.5.14 is a two-line section further down; neither 0.6 release may leak in.
    direct_vm.clear_mocks()
    mock_page(direct_vm, body=REAL_PAGE)
    direct_vm.mock_llm(
        r"(?s)^(?!.*Check WebDriver rendering)(?!.*v0\.6 is a breaking release).*RELEASE NOTES \(0\.5\.14\) ---\s*v0\.5\.14 Bug fixes",
        json.dumps({**VERDICT, "version": "0.5.14", "mandatory": False, "breaking": False, "deadline": None,
                    "config_changes": [], "env_changes": []}),
    )
    guard.submit("bradbury-phase2", "v0.5.14", URL)
    assert guard.get_release("bradbury-phase2", "0.5.14")["breaking"] is False


def test_section_trimming_markdown_stops_at_next_version(direct_vm, guard):
    body = "# Changelog\n## v0.6.0\nKEEP_SIX\n### Steps\nKEEP_STEPS\n## [v0.5.9](https://x)\nDROP_FIVE\n"
    mock_page(direct_vm, body=body)
    direct_vm.mock_llm(r"(?s)^(?!.*DROP_FIVE).*RELEASE NOTES.*KEEP_SIX.*KEEP_STEPS", json.dumps({**VERDICT, "version": "0.6.0"}))
    guard.submit("bradbury-phase2", "v0.6.0", URL)
    assert guard.get_release("bradbury-phase2", "0.6.0")["version"] == "0.6.0"


def test_missing_version_reverts_with_clear_error(direct_vm, guard):
    mock_page(direct_vm, body=REAL_PAGE)
    mock_llm(direct_vm, VERDICT)
    with direct_vm.expect_revert("version 0.9.9 is not on the page"):
        guard.submit("bradbury-phase2", "v0.9.9", URL)
    assert guard.get_release("bradbury-phase2", "0.9.9") == {}


def test_validator_agrees_on_trimmed_real_fixture(direct_vm, guard):
    """Leader and validator trim the same real page the same way; tolerable LLM variance still agrees."""
    leader = {**VERDICT, "version": "v0.6.0-rc.2", "env_changes": ["A_ONE", "B_TWO", "C_THREE", "D_FOUR", "E_FIVE"]}
    mock_page(direct_vm, body=REAL_PAGE)
    direct_vm.mock_llm(r"(?s)RELEASE NOTES \(0\.6\.0-rc\.2\).*Check WebDriver rendering", json.dumps(leader))
    guard.submit("bradbury-phase2", "v0.6.0-rc.2", URL)
    for validator_view, expected in (
        ({**leader, "env_changes": leader["env_changes"] + ["F_SIX"], "actions": ["other words"]}, True),
        ({**leader, "mandatory": False}, False),
    ):
        direct_vm.clear_mocks()
        mock_page(direct_vm, body=REAL_PAGE)
        direct_vm.mock_llm(r"(?s)RELEASE NOTES \(0\.6\.0-rc\.2\).*Check WebDriver rendering", json.dumps(validator_view))
        assert direct_vm.run_validator() is expected
