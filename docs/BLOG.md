# Making GenLayer validators agree on release notes: what moved the needle

Changelog Guard turns a GenLayer node release's notes into an on-chain verdict: `version`, `mandatory`, `deadline`, `breaking`, `config_changes`, `env_changes`, `actions`. Several validators, each with its own LLM, have to agree on it. This post covers how we chose the comparison rule and what happened on Testnet Bradbury on 26 Oct 2026.

## The comparison rule
- **Decision fields, compared exactly:** `version`, `mandatory`, `breaking`, `deadline`. A node operator acts on these, and a wrong `mandatory` means a missed upgrade. The deadline is normalized to UTC first, so `16:00+02:00` and `14:00Z` are the same instant.
- **List fields, compared as sets:** `config_changes` and `env_changes`, with Jaccard similarity >= 0.8 as the specification says. With five keys, one missing key gives 5/6 = 0.83 and agrees; two missing keys give 4/6 = 0.67 and do not.
- **`actions`:** free text, stored and not compared. It is the leader's wording, so consumers should treat it as display text.

The rule only means something after normalization: lowercase keys, UTC deadlines, canonical versions, and real JSON booleans (`bool("false")` is `True`). The validator also rejects a leader result that is not already canonical, so the stored verdict is exactly what was compared.

## What happened on Bradbury
**Run 1: the whole page.** The contract cut the docs changelog page, with HTML stripped, to 30,000 characters. That window holds two releases.
- The first submit timed out because the default time units were too small.
- With 600 time units the leaders answered, but the answers differed a lot. One run listed about 30 `config_changes` and the other listed one.
- All five validators rejected the result: UNDETERMINED, MAJORITY_DISAGREE.

The threshold was not too strict. The input was too large and too vague: each LLM chose its own idea of which release, and which keys, counted.

**Run 2: one release, strict schema.** Two changes:
- the contract cuts the page to the requested version's section (from its heading to the next version heading) before prompting, the same way on every node;
- the prompt became a strict schema with narrow field definitions ("list only keys explicitly named in this section").

Result: `submit("bradbury-phase2", "v0.5.14", …)` was ACCEPTED with MAJORITY_AGREE, 5 of 5 validators voting Agree in the first round. The stored verdict is `mandatory=false, breaking=false, deadline=null`, with empty key lists.

A follow-up submit for `v0.6.0-rc.2` (a 3.2k-character section) ended in LEADER_TIMEOUT before any validator voted, even at 600 time units, the maximum the chain accepts. The leader's proposal already had empty key lists: the strict schema keeps the LLM from inventing keys. Longer sections are now limited by leader execution time rather than by agreement.

## Takeaways
- Most of the disagreement came from the input, not the threshold. Give every validator the smallest deterministic input that holds the answer.
- Narrow field definitions in the prompt cut variance that no tolerance setting can absorb.
- Compare exactly what operators act on. Keep tolerance for lists where honest variance is expected, and do not compare prose.

Code, tests (`make check`) and on-chain evidence: this repository, `docs/evidence/bradbury-deploy-2026-10-26.md`.
