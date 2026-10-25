import test from "node:test";
import assert from "node:assert/strict";
import { run, toPlain } from "./read-verdict.mjs";

const fake = (ret) => ({
  calls: [],
  async readContract(a) { this.calls.push(a); return ret; },
});

test("Map/bigint results from genlayer-js become plain objects", () => {
  const m = new Map([["version", "0.6.0"], ["breaking", false], ["n", 3n], ["l", ["a"]]]);
  assert.deepEqual(toPlain(m), { version: "0.6.0", breaking: false, n: 3, l: ["a"] });
});

test("run reads get_latest and decides", async () => {
  const c = fake(new Map([["version", "0.6.0"], ["breaking", true], ["mandatory", true]]));
  const r = await run({ client: c, address: "0xabc", network: "bradbury-phase2", running: "0.5.9" });
  assert.deepEqual(c.calls[0], { address: "0xabc", functionName: "get_latest", args: ["bradbury-phase2"] });
  assert.equal(r.action, "hold");
});

test("empty verdict means no action", async () => {
  const r = await run({ client: fake(new Map()), address: "0x1", network: "n", running: "0.5.9" });
  assert.equal(r.action, "none");
});

import { applyUpgrade } from "./read-verdict.mjs";
import * as lib from "./index.mjs";

const spy = () => { const calls = []; return { calls, exec: async (...a) => { calls.push(a); } }; };

test("library entry exposes what the bot needs", () => {
  for (const name of ["decide", "compareVersions", "readLatest", "run", "applyUpgrade", "buildAlert"]) assert.equal(typeof lib[name], "function");
});

test("applyUpgrade runs pull then up -d only for a non-breaking auto-upgrade", async () => {
  const s = spy();
  const r = await applyUpgrade({ action: "auto-upgrade", verdict: { breaking: false } }, { exec: s.exec, composeDir: "/node" });
  assert.equal(r.applied, true);
  assert.deepEqual(s.calls.map((c) => c[1].join(" ")), ["compose pull", "compose up -d"]);
  assert.equal(s.calls[0][2].cwd, "/node");
});

test("applyUpgrade never runs for hold, alert, breaking verdicts, or without opt-in config", async () => {
  const s = spy();
  for (const d of [
    { action: "hold", verdict: { breaking: true } },
    { action: "alert", verdict: { breaking: false } },
    { action: "auto-upgrade", verdict: { breaking: true } },
    { action: "auto-upgrade", verdict: {} },
  ]) assert.equal((await applyUpgrade(d, { exec: s.exec, composeDir: "/node" })).applied, false);
  assert.equal((await applyUpgrade({ action: "auto-upgrade", verdict: { breaking: false } }, {})).applied, false);
  assert.equal(s.calls.length, 0);
});
