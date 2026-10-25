# Bradbury deploy and real submit, 2026-10-26

## Current contract (after the section-trimming fix)
| Item | Value |
|---|---|
| Contract address | `0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc` |
| Deploy tx | `0x3ed2d05e614a68fc8f55969de2ee9a309e4f6c3a613b0e8ec35459ddfa2e7f0a`: ACCEPTED, MAJORITY_AGREE, FINISHED_WITH_RETURN |
| Deployed code | sha256 `a8c05a8857eb176068b57690a575e97027260ef82f1951531aacaca6765d9957`, byte-identical to `contracts/changelog_guard.py` in the commit that adds this section |
| Real submit | `submit("bradbury-phase2", "v0.5.14", "https://docs.genlayer.com/validators/changelog")`, fees: leader/validator 600/600 time units, 0.1 GEN deposit |
| Submit tx | `0x7f0f7dbd28e76506c3c85c3af51c78334f0319dea5df5b00bbb0a6cb5830a015`: **ACCEPTED, MAJORITY_AGREE, votes 5/5 Agree in round 0**, FINISHED_WITH_RETURN |
| Second submit | `submit(…, "v0.6.0-rc.2", …)` tx `0xab2ceee00932cb0d55a7d20ba7405e639c81173f7ed550e2c344a37bf1cc45e9`: LEADER_TIMEOUT, no votes; nothing stored. The leader's proposal: `breaking`, empty `config_changes`/`env_changes`, 3 actions |
| Cost of this round | deploy 0.100127 GEN + submits 0.100033 + 0.000085 GEN (deposits are charged up front; unused fees came back later) |
| Total GEN spent today | 100.000000 -> 99.898648 at the end of the session = **0.101352 GEN** net (refunds of unused deposits included) |

Verdict read back with `get_latest("bradbury-phase2")` through `gen_call` on `https://rpc-bradbury.genlayer.com` (`node scripts/bradbury.mjs read 0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc bradbury-phase2`, which uses `consumer/read-verdict.mjs` `readLatest`):

```json
{
  "actions": [],
  "breaking": false,
  "config_changes": [],
  "deadline": null,
  "env_changes": [],
  "mandatory": false,
  "network": "bradbury-phase2",
  "source_url": "https://docs.genlayer.com/validators/changelog",
  "version": "0.5.14"
}
```
The live section is `v0.5.14 Bug fixes Skip replay check when chain records no result`, so the verdict matches it.

What changed from the first contract (`0x0e4a…c7e2`, below): `release_section` cuts the page to the requested version's heading-to-next-version-heading section before prompting. It works the same on leader and validators, and a missing version becomes an agreed revert (`version X is not on the page`). The prompt now has a strict JSON schema and narrow field definitions ("list only keys explicitly named in this section"). The comparison rules are unchanged.

## First contract (superseded)
The record of the first contract is kept below as history. Its open items were resolved by the current contract above, except that the public RPC still has no `gen_call`; read through `rpc-bradbury.genlayer.com`.

Network: GenLayer Testnet Bradbury, chain 4221. Writes go through `https://rpc.testnet-chain.genlayer.com`.
Deployer: `0x94C4209DF494f614041feFBfc426F723ae2FF92a` (`.secrets/deployer-changelog-guard.env`; the key is loaded only inside `scripts/bradbury.mjs`).
Tooling: `genlayer-js@2.0.0-rc.2` (from `consumer/`), `scripts/bradbury.mjs`.
GenLayer explorer: https://scan.bradbury.genlayer.com (`explorer-bradbury.genlayer.com` redirects there).

### Result
| Item | Value |
|---|---|
| Contract address | `0x0e4aE9f4861dBF9f635cFEDc3cA451671539c7e2` |
| Deploy tx | `0x66d68bb6e10e7d9af534dd52a313c1ce1aeea8c5a8dbe694278c76a6fbc14698`: ACCEPTED, then FINALIZED; MAJORITY_AGREE, FINISHED_WITH_RETURN |
| Deployed code | sha256 `fbdb3e9586a936031b4c328237a17f7076b77edb4904d56a107e449aaa9de541`. The commit that adds this file only adds the final `del _Contract` line after it (needed for `genvm-lint validate`; no on-chain behaviour change). |
| Real submit | `submit("bradbury-phase2", "v0.6.0-rc.2", "https://docs.genlayer.com/validators/changelog")`, sent twice, no verdict stored (see below) |
| GEN spent | 100.000000 -> 99.799448, so **0.200552 GEN** for 4 deploy attempts (1 reverted before consensus) and 3 submit attempts (1 reverted before consensus) |

### Transactions in order
| # | Tx | What | Outcome |
|---|---|---|---|
| 1 | `0xef54fc85aea5e0000c68485ed6e689de445775dceb100d0d8cb6ca2c8eb6f998` | deploy with no fee deposit | EVM revert `FeeValueMustBeNonZero` (selector `0x632be5a1`). v0.6 consensus requires a fee deposit. Fix: `client.estimateTransactionFees()`, like the genlayer CLI does |
| 2 | `0x28dc05bd8db51114319a89500a327a4a80417e548eaaeb1d74f83cefc55f07c8` | deploy, header `py-genlayer:latest`, contract `0x33dB02829308Ddc414d0AFBDb2D3b5f7Ce4126aE` | ACCEPTED, but all 5 validators FINISHED_WITH_ERROR. `gen_getContractSchema` gives `VMError: invalid_contract runner absent` |
| 3 | `0x92e5da1fcf394f35ff13d7348cdea8ec03bfcd0c25b65dde9e6361d8fa16c6c3` | deploy, header `py-genlayer:1jb45aa8…09h6` (the hash in docs.genlayer.com "Your First Contract"), contract `0x9ee3bAbf68727003D3921073AEdC45fa4Fe53457` | same: FINISHED_WITH_ERROR, `runner absent` |
| 4 | `0x66d68bb6e10e7d9af534dd52a313c1ce1aeea8c5a8dbe694278c76a6fbc14698` | deploy, header `py-genlayer:babwp9t37jw9g4j2bccgn14g6x7x9s1f7dsmh7emvz735pz4zxa0`, ported to SDK v0.3 | **ACCEPTED -> FINALIZED, FINISHED_WITH_RETURN** at `0x0e4aE9f4861dBF9f635cFEDc3cA451671539c7e2` |
| 5 | `0xffe72f7f5c4e7828b9f60173af6bf381d78575c5b2fae02427655b2a61ed8b4b` | submit, default fees (leader 100 / validator 200 time units, 3 rotations) | **LEADER_TIMEOUT**, result IDLE, all rotations used. The leader did produce a verdict (shown below) |
| 6 | `0x86cd82d9b19c5ddefe78bf4c69c72530963329b2ae70b07843e290c11611d6d7` | submit with 3000/3000 time units | EVM revert, error `0xdb0c8dfe(3000, 30, 600)`. 600 looks like the maximum time-unit allocation |
| 7 | `0x7002e023901c9a072e1925c482292918af812fbb01d87ce201df99fd5ceb625c` | submit with 600/600 time units | **UNDETERMINED, MAJORITY_DISAGREE**. Vote value 4 from all 5 validators, and all 5 have the same validator result hash. No verdict stored |

### Runner / SDK finding
Bradbury nodes run GenVM `v0.6.0-rc10`. Its `runners/` only ship the executor v0.3 runner `py-genlayer:babwp9t37jw9g4j2bccgn14g6x7x9s1f7dsmh7emvz735pz4zxa0`. That hash comes from `executor/v0.3.0-rc10/data/latest.json` in the node image on this host, which was only read. Neither `latest` nor the documented `1jb45…` hash resolves on Bradbury today.
SDK v0.3 is a flat module: `import genlayer as gl`, `gl.contract.Contract`, `gl.vm.run_nondet(leader_fn, validator_fn)` (there is no `run_nondet_unsafe`), and `Response.body` can be `None`. The contract selects the API at import time (`_SDK_V02`), so the direct-mode tests still run on SDK v0.2.16. `tests/direct/conftest.py` deploys a copy whose header says `latest`, because gltest has no v0.3 tarball. `make lint` validates a copy with the same header for the same reason.

### Verdict read back
**No verdict exists on chain** because both submits ended without consensus. Even so, a read could not be done:
- `rpc.testnet-chain.genlayer.com` only serves `eth_*`. `gen_call` returns `the method gen_call does not exist/is not available`, so `consumer/read-verdict.mjs` (`readLatest`) cannot read through it as written.
- `rpc-bradbury.genlayer.com` (the genlayer-py default) serves `gen_*`. For the finalized contract it answers `gen_call` with `contract not found at address 0x0e4a…c7e2` and `gen_getContractSchema` with `VMError: invalid_contract runner absent`, so that RPC node looks behind on GenVM.
  `scripts/bradbury.mjs read` uses it (`READ_RPC`).

Leader verdicts seen in the consensus outputs (`eqBlocksOutputs`, not stored):
- tx 5: `version 0.6.0-rc.2`, `breaking`, about 30 `config_changes` (consensus.*, genvm.*, node.rpc.*, …), 7 `env_changes` (`docker_host`, `genlayernode_password`, `genlayernode_rollup_genlayerchainrpckey`, `healthcheck_auto_restart`, `loki_batch_wait`, `metrics_scrape_interval`, `node_manifest_path`, `node_password` …) and 16 actions. It mixes in rc.1 notes.
- tx 7: `version 0.6.0-rc.2`, `breaking`, `config_changes = [genvm.root_dir]`, `env_changes = [healthcheck_auto_restart, loki_batch_wait, metrics_scrape_interval, node_manifest_path]`, 5 actions.
The two leaders differ widely on `config_changes`: 1 key against about 30. The 0.8 Jaccard rule cannot pass with that much LLM variance on this page, which fits MAJORITY_DISAGREE. The input is the 30,000-char cut of the docs page, which holds rc.2 and rc.1 together.

### Not done
- No verdict on chain, so there is no `get_latest` content.
- The bot cannot read through the public RPC (no `gen_call`).
- At most 2 fixes were allowed for the consensus failure and both were used: time units 3000, which reverted, then 600, which gave MAJORITY_DISAGREE.
- Possible next steps: cut the page to the requested version's section before prompting, and/or give the prompt a stricter definition of `config_changes`. Then resubmit.

### Reproduce
    cd consumer && npm ci && cd ..
    node scripts/bradbury.mjs deploy
    LEADER_TU=600 VALIDATOR_TU=600 node scripts/bradbury.mjs submit <address> bradbury-phase2 v0.6.0-rc.2 https://docs.genlayer.com/validators/changelog
    node scripts/bradbury.mjs tx <hash>
