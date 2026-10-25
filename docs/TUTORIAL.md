# Tutorial: an LLM verdict that GenLayer validators agree on (Changelog Guard)

This tutorial walks through Changelog Guard, an intelligent contract on GenLayer Testnet Bradbury. It reads one node release's notes and stores a structured upgrade verdict that the validators agreed on. Everything below was run on Bradbury on 26 Oct 2026. Hashes and costs are in `docs/evidence/bradbury-deploy-2026-10-26.md`.

## 1. The problem
Release notes are free text. A script can't parse them, and a single LLM can miss a breaking change. With GenLayer, several validators read the same notes with their own LLMs, and the contract stores only a verdict they agree on.

## 2. The contract in one call
`submit(network, version, url)`:
1. Checks the inputs deterministically. The URL must be a docs.genlayer.com page or a genlayerlabs release-tag / tag-pinned raw file. The version must look like `1.2.3` or `1.2.3-rc.4`, and a version can only be submitted once.
2. Runs a non-deterministic block. Leader and validators fetch the page (`gl.nondet.web.get`), cut out the requested version's section, and ask their LLM for JSON (`gl.nondet.exec_prompt`).
3. Stores the leader's verdict only if the validators accept it. `get_release(network, version)` and `get_latest(network)` read it back.

The comparison (validator side):
- exact: `version`, `mandatory`, `breaking`, `deadline` (normalized to UTC);
- sets with Jaccard >= 0.8: `config_changes`, `env_changes` (lowercase; dot notation for config keys);
- `actions`: free text, stored and not compared.

The validator repeats the whole extraction itself. If it only checked the format of the leader's answer, there would be no consensus to speak of.

## 3. Step by step on Bradbury
### Pin the runner the network actually ships
The first line of the contract selects the GenVM runner. On Bradbury (node v0.6, GenVM v0.6.0-rc10) only this one resolves:

    # { "Depends": "py-genlayer:babwp9t37jw9g4j2bccgn14g6x7x9s1f7dsmh7emvz735pz4zxa0" }

`py-genlayer:latest` and the hash shown in the docs tutorial deployed "successfully" as transactions, but every validator finished with an error. The schema call said `invalid_contract runner absent`.
This runner is SDK v0.3, where the API changed: `import genlayer as gl`, `gl.contract.Contract`, and `gl.vm.run_nondet(leader_fn, validator_fn)` instead of `run_nondet_unsafe`. Changelog Guard detects the SDK at import, so its local tests still run on SDK v0.2.16.

### Pay the fee deposit
Consensus v0.6 rejects a transaction with no fee deposit (`FeeValueMustBeNonZero`). With genlayer-js 2.0 rc:

    const est = await client.estimateTransactionFees({ leaderTimeunitsAllocation: 600n, validatorTimeunitsAllocation: 600n });
    await client.writeContract({ address, functionName: "submit", args, value: 0n,
      fees: { distribution: est.distribution, feeValue: est.feeValue } });

Default time units (100 for the leader, 200 per validator) were too small for a web fetch plus an LLM call: the leader timed out on every rotation (LEADER_TIMEOUT). 3000 was rejected by the chain, and 600 worked.
The deposit is about 0.1 GEN. What is not consumed is refunded.
`scripts/bradbury.mjs` wraps all of this: `deploy`, `submit`, `read`, `tx`.

### Give every validator the same, short input
The first real submit fed the LLM the first 30,000 characters of the whole docs changelog page, which covers two releases (v0.6.0-rc.2 and rc.1). Two leaders produced:
- `config_changes`: about 30 keys in one run, a single key (`genvm.root_dir`) in the other.

No 0.8 Jaccard rule survives that, and the transaction ended UNDETERMINED (MAJORITY_DISAGREE).
The fix was to make the input deterministic and small. `release_section(page, version)` finds the heading for the requested version and keeps everything up to the next version heading:
- in HTML it uses `<h1>`–`<h6>`; in markdown, `#` lines;
- if the version has no heading, the result is an agreed error and the transaction reverts with `version X is not on the page`.

Leader and validators run the same code on the same page, so they prompt with the same text.

### Tell the LLM exactly what to return
The prompt gives a strict schema with JSON types and defines each field narrowly:
- "mandatory: true only if the section explicitly says operators must upgrade or states a deadline";
- "list only keys explicitly named in this section, lowercase dot notation".

Vague instructions such as "if unsure, say it is mandatory" leave each LLM to decide on its own, so they were removed.

### Read it back
`get_latest` is a view, served by `gen_call`. On Bradbury use `https://rpc-bradbury.genlayer.com`. The public `rpc.testnet-chain.genlayer.com` answers only `eth_*` methods.

    node scripts/bradbury.mjs read 0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc bradbury-phase2

## 4. Result
Contract `0x0D81c42a86eF913e1Eb6c34DE02c5608C31961Cc`.
`submit("bradbury-phase2", "v0.5.14", "https://docs.genlayer.com/validators/changelog")` was ACCEPTED with MAJORITY_AGREE: all 5 validators voted Agree in the first round. Stored and read back:

    {"actions": [], "breaking": false, "config_changes": [], "deadline": null, "env_changes": [],
     "mandatory": false, "network": "bradbury-phase2",
     "source_url": "https://docs.genlayer.com/validators/changelog", "version": "0.5.14"}

A second submit on the same contract, for `v0.6.0-rc.2` (a 3,234-character section, tx `0xab2ceee00932cb0d55a7d20ba7405e639c81173f7ed550e2c344a37bf1cc45e9`), ended in LEADER_TIMEOUT with no validator votes, even at 600 time units, the maximum the chain accepts. The leader had proposed `breaking` with empty key lists, but nothing was stored. A longer section takes longer for the leader to finish (web fetch + LLM), so short sections are the reliable case today.

## 5. Using the verdict
`consumer/decide.mjs` maps a verdict to `none | alert | auto-upgrade | hold`, and a breaking verdict never auto-upgrades. `consumer/index.mjs` is what the WatchLayer bot imports. Set its RPC to `rpc-bradbury.genlayer.com` for reads.

## 6. Checklist for your own LLM contract
- Pin the runner hash the target network ships, and check it with `gen_getContractSchema` before you rely on a deploy.
- Estimate and send the fee deposit, and size the time units for web + LLM work.
- Make the non-deterministic input as small and deterministic as you can before the LLM sees it.
- Define each output field narrowly. Compare decision fields exactly, use tolerance only where honest variance is expected, and leave free text uncompared.
- Validators must redo the work, and they must reject a leader result that is not already canonical.
- Require real JSON booleans: `bool("false")` is `True`.
