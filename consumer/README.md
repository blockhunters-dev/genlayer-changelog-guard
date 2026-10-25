# Consumer (outline)

Operator-side script. Reads the on-chain verdict and decides what to do.

- `decide.mjs` — pure, tested decision logic (`node --test consumer/decide.test.mjs`). Implemented.
- `read-verdict.mjs` — read-only chain reader via `genlayer-js@rc` (`readContract`, address from `CHANGELOG_GUARD_ADDRESS`, no key). Unit-tested with a fake client; **never run against a real chain** (no deployed address).
- Actions: `alert` -> Telegram hook (WatchLayer bot); `auto-upgrade` -> `docker compose pull && up -d`
  (`applyUpgrade` / `--apply`, off by default); `hold` -> alert only, never upgrades.

## For the WatchLayer bot
Import the library instead of shelling out: `import { run, decide, applyUpgrade } from "<path>/consumer/index.mjs"`.
The bot supplies a genlayer-js client, the contract address and the running node version; the Watchtower API
(`docs/WATCHTOWER_API.md`) has no field for any of them, so none is read from it. `run()` returns `{verdict, action, reason}`.
`buildAlert(running, verdict)` returns a plain alert object (or `null`) for mandatory upgrades: `kind`, `severity`, `version`, `running`, `action`, `breaking`, `deadline`, `overdue`, `config_changes`, `env_changes`, `actions`, `source_url`, `text` -- only contract fields, no Watchtower API field. `run()` returns it as `alert`.
`applyUpgrade` does nothing unless given `exec` and `composeDir`, and never acts on a breaking verdict.
