# { "Depends": "py-genlayer:babwp9t37jw9g4j2bccgn14g6x7x9s1f7dsmh7emvz735pz4zxa0" }
import genlayer
from genlayer import *

# Bradbury nodes (v0.6, GenVM v0.6.0-rc10) only ship the executor v0.3 runner pinned above. SDK v0.3 is a flat
# module (`import genlayer as gl`, `gl.contract.Contract`, `gl.vm.run_nondet`); the local direct-mode tests run
# on SDK v0.2.16 (`from genlayer import *` gives `gl`, `gl.Contract`, `gl.vm.run_nondet_unsafe`). Same semantics:
# the leader result is accepted only if validator_fn returns True.
_SDK_V02 = hasattr(genlayer, "gl")
if _SDK_V02:
    _Contract = gl.Contract
else:
    import genlayer as gl
    from genlayer.storage import TreeMap

    _Contract = gl.contract.Contract

import json
import re
from datetime import datetime, timezone

# Only pages the project itself publishes may produce a verdict; otherwise anyone
# could mint a "mandatory upgrade" verdict from a page they control.
SOURCE_PATTERNS = (
    re.compile(r"^https://docs\.genlayer\.com/[A-Za-z0-9._/-]*$"),
    re.compile(r"^https://github\.com/genlayerlabs/[A-Za-z0-9._-]+/releases/tag/[A-Za-z0-9._-]+$"),
    re.compile(r"^https://raw\.githubusercontent\.com/genlayerlabs/[A-Za-z0-9._-]+/refs/tags/[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$"),
)
MAX_PAGE_CHARS = 30000
MAX_RAW_CHARS = 1000000  # cap before any parsing; the real docs page is ~440k
JACCARD_MIN = 0.8
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-[a-z]+\.\d+)?$")
MAX_ACTIONS = 20
MAX_ACTION_CHARS = 200  # actions are free text (spec): stored, never compared, so bound them
NETWORK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

PROMPT = """You extract an upgrade verdict for node operators from the release notes of ONE node release.
Release version: {version}
Network: {network}

Return ONLY one JSON object, no prose and no code fences, with exactly these keys and types:
{{"version": string, "mandatory": boolean, "deadline": string or null, "breaking": boolean,
  "config_changes": [string], "env_changes": [string], "actions": [string]}}

Rules (use only what this section states; do not infer):
- "version": "{version}".
- "mandatory": true only if the section explicitly says operators/validators must upgrade (for example
  "mandatory", "must upgrade", "all validators upgrade together") or states an upgrade deadline; else false.
- "deadline": the upgrade deadline stated in the section as ISO-8601 UTC (e.g. 2026-10-22T14:00:00Z), else null.
- "breaking": true only if the section explicitly calls the release breaking, or says operators must change
  config.yaml, .env or node data for the node to keep working; else false.
- "config_changes": config.yaml keys explicitly named in this section as new, removed, renamed or required to
  change; list only keys explicitly named in this section, lowercase dot notation as written
  (e.g. "consensus.manifestpath"); [] if none.
- "env_changes": environment variable names explicitly named in this section as new, removed or required to
  change; list only names explicitly named in this section, lowercase with underscores kept; [] if none.
- "actions": short plain-text sentences describing what operators must do (informational only).

--- RELEASE NOTES ({version}) ---
{page}
"""


# ---------------------------------------------------------------- pure helpers


def parse_source_url(url: str) -> bool:
    """True only for docs pages, release-tag pages, or raw files pinned to a tag.

    No query strings, fragments, percent-encoding, userinfo, ports or `..`.
    Issues, PRs, discussions, blobs and branches are not accepted.
    """
    if not isinstance(url, str) or ".." in url:
        return False
    return any(p.match(url) for p in SOURCE_PATTERNS)


def normalize_version(v) -> str:
    return str(v).strip().lower().lstrip("v")


def version_key(v: str):
    """Orderable key: numeric core, and a release sorts after its own rc/beta."""
    core, _, pre = normalize_version(v).partition("-")
    nums = tuple(int(x) for x in re.findall(r"\d+", core)) or (0,)
    if not pre:
        return (nums, 1, ())
    return (nums, 0, tuple(int(x) for x in re.findall(r"\d+", pre)))


def normalize_deadline(d):
    if d is None or str(d).strip().lower() in ("", "null", "none"):
        return None
    try:
        dt = datetime.fromisoformat(str(d).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_keys(items) -> list:
    if not isinstance(items, list):
        return []
    return sorted({str(i).strip().lower() for i in items if str(i).strip()})


def require_bool(raw: dict, field: str) -> bool:
    """Only real JSON booleans; bool("false") is True, so never coerce."""
    value = raw.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a JSON boolean, got {value!r}")
    return value


def normalize_actions(raw) -> list:
    """Free text per the spec: informational only, bounded, never compared."""
    if not isinstance(raw, list):
        return []
    out = [" ".join(a.split())[:MAX_ACTION_CHARS] for a in raw if isinstance(a, str)]
    return [a for a in out if a][:MAX_ACTIONS]


def normalize_verdict(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("verdict must be a JSON object")
    deadline = normalize_deadline(raw.get("deadline"))
    if deadline is None and str(raw.get("deadline") or "").strip().lower() not in ("", "null", "none"):
        raise ValueError(f"unparseable deadline {raw.get('deadline')!r}")
    return {
        "version": normalize_version(raw.get("version", "")),
        "mandatory": require_bool(raw, "mandatory"),
        "deadline": deadline,
        "breaking": require_bool(raw, "breaking"),
        "config_changes": normalize_keys(raw.get("config_changes")),
        "env_changes": normalize_keys(raw.get("env_changes")),
        "actions": normalize_actions(raw.get("actions")),
    }


def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def verdicts_equivalent(leader: dict, mine: dict) -> bool:
    """Decision fields exact; key lists within Jaccard tolerance; actions not compared."""
    for field in ("version", "mandatory", "breaking", "deadline"):
        if leader[field] != mine[field]:
            return False
    for field in ("config_changes", "env_changes"):
        if jaccard(leader[field], mine[field]) < JACCARD_MIN:
            return False
    return True


_ENTITIES = (("&nbsp;", " "), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&amp;", "&"))


_ASCII_LOWER = {c: c + 32 for c in range(ord("A"), ord("Z") + 1)}


def looks_like_html(body: str) -> bool:
    head = body[:2000].translate(_ASCII_LOWER)
    return "<!doctype html" in head or "<html" in head


def html_to_text(body: str) -> str:
    """Single linear pass that drops scripts, styles, comments and tags from HTML pages.

    Non-HTML bodies (e.g. raw markdown) are returned unchanged. The input is capped first
    so the work is bounded.
    """
    body = body[:MAX_RAW_CHARS]
    if not looks_like_html(body):
        return body
    return strip_html(body)


def strip_html(body: str) -> str:
    """The linear tag/script/style/comment stripper behind html_to_text (no HTML detection)."""
    low = body.translate(_ASCII_LOWER)  # same length as body; str.lower() can change it
    out = []
    i, n = 0, len(body)
    while i < n:
        lt = body.find("<", i)
        if lt < 0:
            out.append(body[i:])
            break
        out.append(body[i:lt])
        if body.startswith("<!--", lt):
            end = body.find("-->", lt + 4)
            i = n if end < 0 else end + 3
        elif low.startswith(("<script", "<style"), lt):
            name = "</script" if low.startswith("<script", lt) else "</style"
            close = low.find(name, lt + 1)
            end = body.find(">", close) if close >= 0 else -1
            i = n if end < 0 else end + 1
        else:
            end = body.find(">", lt + 1)
            i = n if end < 0 else end + 1
        out.append(" ")
    text = "".join(out)
    for entity, char in _ENTITIES:
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()


# Version headings: <h1>-<h6> in HTML (inner text bounded so an unclosed tag cannot make this quadratic),
# `#` lines in markdown. A heading is a version heading if its text starts with something like v1.2 / 1.2.3-rc.4.
_HTML_HEADING_RE = re.compile(r"<h([1-6])\b[^>]{0,500}>(.{0,500}?)</h\1\s*>", re.S | re.I)
_MD_HEADING_RE = re.compile(r"^#{1,6}[ \t]+([^\n]{0,500})$", re.M)
_VERSION_TOKEN_RE = re.compile(r"^\[?(v?\d+\.\d+(?:\.\d+)?[0-9A-Za-z.-]*)")


def _heading_version(text: str):
    m = _VERSION_TOKEN_RE.match(" ".join(text.split()))
    return normalize_version(m.group(1)) if m else None


def release_section(body: str, version: str) -> str:
    """Text of the requested version's section: from its heading to the next version heading.

    Deterministic (same input -> same output on leader and validators). Raises ValueError when the
    page has no heading for `version`.
    """
    body = body[:MAX_RAW_CHARS]
    is_html = looks_like_html(body)
    if is_html:
        heads = [(m.start(), _heading_version(strip_html(m.group(2)))) for m in _HTML_HEADING_RE.finditer(body)]
    else:
        heads = [(m.start(), _heading_version(m.group(1))) for m in _MD_HEADING_RE.finditer(body)]
    heads = [(pos, v) for pos, v in heads if v]
    for i, (pos, v) in enumerate(heads):
        if v == version:
            end = heads[i + 1][0] if i + 1 < len(heads) else len(body)
            chunk = body[pos:end]
            return strip_html(chunk) if is_html else chunk.strip()
    raise ValueError(f"version {version} is not on the page")


def parse_llm_json(out) -> dict:
    if isinstance(out, dict):
        return out
    text = str(out).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in LLM output")
    return json.loads(text[start : end + 1])


# -------------------------------------------------------------------- contract


class ChangelogGuard(_Contract):
    releases: TreeMap[str, str]  # "network:version" -> canonical verdict JSON
    latest: TreeMap[str, str]  # network -> newest version string

    def __init__(self):
        pass

    @gl.public.write
    def submit(self, network: str, version: str, url: str) -> None:
        network = network.strip().lower()
        version = normalize_version(version)
        if not NETWORK_RE.match(network):
            raise gl.vm.UserError("invalid network id")
        if not VERSION_RE.match(version):
            raise gl.vm.UserError("version must look like 1.2.3 or 1.2.3-rc.4")
        if not parse_source_url(url):
            raise gl.vm.UserError("url is not an allowed source")
        key = f"{network}:{version}"
        if key in self.releases:
            raise gl.vm.UserError("release already has a verdict")

        def leader_fn() -> dict:
            page = (gl.nondet.web.get(url).body or b"").decode("utf-8", errors="replace")
            try:
                section = release_section(page, version)
            except ValueError as e:
                # Agreed on like a verdict (validators see the same page), then reverted below.
                return {"error": str(e)}
            prompt = PROMPT.format(version=version, network=network, page=section[:MAX_PAGE_CHARS])
            try:
                return normalize_verdict(parse_llm_json(gl.nondet.exec_prompt(prompt)))
            except ValueError as e:
                raise gl.vm.UserError(f"invalid LLM verdict: {e}")

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            # Redo the whole evaluation; do not just validate the leader's shape.
            try:
                mine = leader_fn()
                if "error" in leaders_res.calldata or "error" in mine:
                    return leaders_res.calldata == mine
                theirs = normalize_verdict(leaders_res.calldata)
            except Exception:
                return False
            # What gets stored is the leader's result, so it must already be canonical:
            # no extra keys, no un-normalized values that normalization would hide.
            if leaders_res.calldata != theirs:
                return False
            return verdicts_equivalent(theirs, mine)

        if _SDK_V02:
            verdict = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        else:
            verdict = gl.vm.run_nondet(leader_fn, validator_fn)
        if "error" in verdict:
            raise gl.vm.UserError(verdict["error"])
        verdict = normalize_verdict(verdict)  # store only the canonical form
        if verdict["version"] != version:
            raise gl.vm.UserError("verdict is for a different version")

        verdict["network"] = network
        verdict["source_url"] = url
        self.releases[key] = json.dumps(verdict, sort_keys=True)
        current = self.latest.get(network)
        if current is None or version_key(version) > version_key(current):
            self.latest[network] = version

    @gl.public.view
    def get_release(self, network: str, version: str) -> dict:
        raw = self.releases.get(f"{network.strip().lower()}:{normalize_version(version)}")
        return json.loads(raw) if raw is not None else {}

    @gl.public.view
    def get_latest(self, network: str) -> dict:
        network = network.strip().lower()
        version = self.latest.get(network)
        if version is None:
            return {}
        return json.loads(self.releases[f"{network}:{version}"])


# Only one Contract subclass may be visible at module level (the SDK picks the contract class from it).
del _Contract
