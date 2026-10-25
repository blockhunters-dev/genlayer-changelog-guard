<!-- SYNTHETIC FIXTURE: shaped after the example verdict in the specification, NOT the real upstream changelog.
     Replace with the verbatim v0.5 -> v0.6 notes before the Bradbury deploy. -->
# v0.6.0-rc.2

Upgrade is mandatory for Bradbury Phase 2 validators before 2026-10-22 14:00 UTC.

## Breaking changes
- `rollup.provider` and `consensus.chainid` changed; `consensus.manifestpath` is new.
- New env var `GENLAYERNODE_ROLLUP_GENLAYERCHAINRPCKEY`.

## Steps
1. Download the protocol manifest.
2. Set NODE_PASSWORD.
