import test from "node:test";
import assert from "node:assert/strict";
import { buildAlert } from "./alert.mjs";
import { run } from "./read-verdict.mjs";

const v = {
  version: "0.6.0-rc.2", network: "bradbury-phase2", mandatory: true, breaking: true,
  deadline: "2026-10-22T14:00:00Z",
  config_changes: ["rollup.provider"], env_changes: ["genlayernode_rollup_genlayerchainrpckey"],
  actions: ["download_manifest"], source_url: "https://docs.genlayer.com/validators/changelog",
};

test("mandatory breaking upgrade -> critical alert with all verdict fields", () => {
  const a = buildAlert("0.5.14", v, new Date("2026-10-22T10:00:00Z"));
  assert.equal(a.kind, "mandatory-upgrade");
  assert.equal(a.severity, "critical");
  assert.equal(a.action, "hold");
  assert.equal(a.overdue, false);
  assert.deepEqual(a.config_changes, ["rollup.provider"]);
  assert.match(a.text, /0\.5\.14 -> 0\.6\.0-rc\.2 by 2026-10-22T14:00:00Z/);
  assert.match(a.text, /BREAKING/);
  assert.match(a.text, /source: https:\/\/docs\.genlayer\.com/);
});

test("past deadline is flagged overdue", () => {
  const a = buildAlert("0.5.14", { ...v, breaking: false }, new Date("2026-10-23T00:00:00Z"));
  assert.equal(a.overdue, true);
  assert.equal(a.severity, "critical");
  assert.match(a.text, /OVERDUE/);
});

test("non-breaking, future deadline -> warning", () => {
  const a = buildAlert("0.5.14", { ...v, breaking: false }, new Date("2026-10-21T00:00:00Z"));
  assert.equal(a.severity, "warning");
  assert.equal(a.action, "auto-upgrade");
});

test("no alert when up to date, optional, or no verdict", () => {
  assert.equal(buildAlert("0.6.0-rc.2", v), null);
  assert.equal(buildAlert("0.7.0", v), null);
  assert.equal(buildAlert("0.5.14", { ...v, mandatory: false }), null);
  assert.equal(buildAlert("0.5.14", {}), null);
  assert.equal(buildAlert("0.5.14", undefined), null);
});

test("run() returns the alert next to the decision, from a chain-shaped Map", async () => {
  const client = { readContract: async () => new Map(Object.entries(v)) };
  const r = await run({ client, address: "0x1", network: "bradbury-phase2", running: "0.5.14" });
  assert.equal(r.action, "hold");
  assert.equal(r.alert.kind, "mandatory-upgrade");
});
