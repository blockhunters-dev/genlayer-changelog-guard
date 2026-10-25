# GenLayer Changelog Guard

An intelligent contract (Python, GenVM) that reads a node release's notes from an allowed source and publishes a
structured upgrade verdict agreed by validator consensus: `version`, `network`, `mandatory`, `deadline`, `breaking`,
`config_changes`, `env_changes`, `actions`, `source_url`. Category: Validator · Create Intelligent Contracts.
Live on Bradbury: `0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc` ([explorer](https://explorer-bradbury.genlayer.com/address/0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc)). Evidence: `docs/evidence/bradbury-deploy-2026-10-26.md`. Tutorial: `docs/TUTORIAL.md`.

## How consensus works
`submit(network, version, url)` -> the leader fetches the page (`gl.nondet.web.get`), turns HTML into text, cuts out the requested version's section (heading to next version heading), asks an LLM
(`gl.nondet.exec_prompt`) for canonical JSON. Every validator repeats the extraction itself inside
`gl.vm.run_nondet_unsafe` and compares:
- exact: `version`, `mandatory`, `breaking`, `deadline` (UTC);
- sets with Jaccard >= 0.8: `config_changes` (config.yaml keys, lowercase dot notation, e.g. `rollup.provider`) and `env_changes` (environment variable names, lowercased with underscores kept, e.g. `genlayernode_rollup_genlayerchainrpckey`);
- `actions`: free text per the specification; stored (bounded), not compared by validators.

Sources must be docs.genlayer.com pages or genlayerlabs release-tag pages / tag-pinned raw files.
`mandatory` / `breaking` must be real JSON booleans or the submission reverts. Draft write-up: `docs/TUTORIAL.md`.

## Layout
- `contracts/changelog_guard.py` — the contract.
- `tests/direct/` — direct-mode tests with mocked web + LLM (`run_validator` exercises validator disagreement);
  `tests/fixtures/` — one synthetic note and one trimmed real docs page (fetched 2026-10-23).
- `consumer/` — `decide.mjs` (verdict -> none | alert | auto-upgrade | hold), `read-verdict.mjs` (read-only chain reader,
  opt-in `--apply`), `index.mjs` (library entry used by the WatchLayer bot).
- `docs/WATCHTOWER_API.md` — Watchtower API contract copy, pinned (`scripts/verify-watchtower-api.sh`).

## Run
    make setup   # venv, pinned deps, pre-seeds genvm v0.2.16 (~200MB download)
    make check   # genvm-lint lint + pytest + node tests

## Bradbury status (26 Oct 2026)
- **Deployed:** contract `0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc`, deploy tx `0x3ed2d05e…2e7f0a`.
- **Verdict on chain:** `submit("bradbury-phase2", "v0.5.14", "https://docs.genlayer.com/validators/changelog")` (tx `0x7f0f7dbd…a015`) was ACCEPTED with MAJORITY_AGREE (5/5 Agree). `get_latest("bradbury-phase2")` returns `{"version": "0.5.14", "mandatory": false, "breaking": false, "deadline": null, "config_changes": [], "env_changes": [], "actions": [], ...}`.
- **Runner pin:** the contract pins the only runner Bradbury ships (`py-genlayer:babwp9t3…zxa0`, SDK v0.3).
- **Section trimming:** the contract prompts only the requested version's section. Prompting the whole page gave MAJORITY_DISAGREE.
- **Reads:** use `https://rpc-bradbury.genlayer.com`, because the public `rpc.testnet-chain.genlayer.com` has no `gen_call`.
- **Scripts:** `node scripts/bradbury.mjs deploy | submit | read | tx`.
- **Details:** `docs/evidence/bradbury-deploy-2026-10-26.md` and `docs/TUTORIAL.md`.

## Not done / not claimed
Only one real release (v0.5.14, a short bug-fix section) has a stored verdict. A v0.6.0-rc.2 submit (3.2k-char section) hit LEADER_TIMEOUT at the maximum 600 time units. No Studio real-LLM run.
Tests use mocked LLM output. They run on SDK v0.2.16 through a copy with a `latest` header; the deployed code uses SDK v0.3 through the same source (`_SDK_V02` switch).
