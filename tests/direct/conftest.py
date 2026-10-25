import json
import re
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "contracts" / "changelog_guard.py"
# The contract pins the executor v0.3 runner that Bradbury nodes ship. gltest direct mode only has SDK v0.2.16
# (no v0.3 tarball), so tests run an identical copy whose header says `latest` (= v0.2.16); the contract body
# selects the matching SDK API itself (see `_SDK_V02`).
_src = SOURCE.read_text()
_tmp = Path(tempfile.mkdtemp(prefix="changelog-guard-")) / "changelog_guard.py"
_tmp.write_text(re.sub(r'^# \{ "Depends": "py-genlayer:[^"]+" \}', '# { "Depends": "py-genlayer:latest" }', _src, count=1))
assert _tmp.read_text() != _src, "header rewrite failed"
CONTRACT = str(_tmp)
FIXTURE = (ROOT / "tests" / "fixtures" / "synthetic_release_v0_6_0_rc_2.md").read_text()
URL = "https://docs.genlayer.com/validators/changelog"

VERDICT = {
    "version": "v0.6.0-rc.2",
    "mandatory": True,
    "deadline": "2026-10-22T14:00:00Z",
    "breaking": True,
    "config_changes": ["rollup.provider", "consensus.chainid", "consensus.manifestpath"],
    "env_changes": ["GENLAYERNODE_ROLLUP_GENLAYERCHAINRPCKEY"],
    "actions": ["download_manifest", "set_node_password"],
}


@pytest.fixture
def guard(direct_vm, direct_deploy):
    return direct_deploy(CONTRACT)


def mock_page(vm, body=FIXTURE, url=URL):
    vm.mock_web(url, {"method": "GET", "status": 200, "body": body})


def mock_llm(vm, verdict):
    vm.mock_llm(r"RELEASE NOTES", json.dumps(verdict))
