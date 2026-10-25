# Watchtower JSON API (v0)

Public, read-only, CORS `*`. Served by `packages/indexer` (`PORT`, default 20360). Consumed by the dashboard, the bot, and project D (validator list).
Conventions: JSON; all token amounts are **decimal strings in wei** (18 decimals); epochs are decimal strings; timestamps are unix seconds (integer); addresses keep checksum case in responses, lookups are case-insensitive. Unavailable data is `null`, never guessed.

Status: **implemented** unless marked *(planned)*.

## GET /health
`200 {"ok": true, "lastSnapshot": <unix|null>}`

## GET /network
`503 {"error":"no snapshot yet"}` before the first snapshot. Otherwise:
```json
{ "epoch": "2", "nextEpochEstimate": 1792765216, "snapshotAt": 1792701818,
  "validators": { "total": 51, "active": 44, "pending": 4, "banned": 0, "needsPriming": 3 } }
```
*(planned)* `totalStake`, `txPerHour`.

## GET /validators
Array of Validator objects from the latest snapshot, ordered by address.

## GET /validators/:address
One Validator, or `404 {"error":"unknown validator"}`. Address must match `0x` + 40 hex.

### Validator object
| field | type | notes |
|---|---|---|
| address | string | validator wallet |
| operator | string | operator address (gas account) |
| moniker | string\|null | registered identity |
| status | `active`\|`pending`\|`banned`\|`needs_priming` | precedence: banned > needs_priming > active > pending |
| vStake, dStake | string | active self / delegated stake, wei |
| pendingDeposits | `{epoch, stakeRaw}[]` | `epoch` = deposit epoch; *(planned)* `activatesAtEpoch` once semantics are verified |
| operatorBalanceWei | string | operator gas balance |
| gasRunwayDays | number\|null | balance / burn rate over last 24h; only decreases count as burn; null = not measurable |
| strikes | null | not exposed by the staking SDK; always null for now |
| snapshotAt | number | snapshot time |

## Planned (not implemented; do not depend on them yet)
- `GET /validators/:address/history` — per-epoch stake/status, operator balance series.
- `GET /validators/:address/activity` — operator last tx time and tx count per epoch.
- `GET /network/history` — per-epoch totals.
Changing a planned endpoint is free; changing an implemented one requires updating this file and tests in the same commit.
