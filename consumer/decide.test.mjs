import test from "node:test";
import assert from "node:assert/strict";
import { decide, compareVersions } from "./decide.mjs";

test("version ordering: rc < release", () => {
  assert.equal(compareVersions("v0.6.0-rc.2", "0.6.0"), -1);
  assert.equal(compareVersions("v0.6.0", "v0.5.9"), 1);
  assert.equal(compareVersions("0.6.0-rc.2", "v0.6.0-rc.2"), 0);
});

test("breaking verdict blocks auto-upgrade", () => {
  const r = decide("0.5.9", { version: "0.6.0-rc.2", breaking: true, mandatory: true });
  assert.equal(r.action, "hold");
});

test("non-breaking mandatory upgrade is auto", () => {
  assert.equal(decide("0.5.9", { version: "0.5.10", breaking: false, mandatory: true }).action, "auto-upgrade");
});

test("optional non-breaking only alerts; up-to-date and empty do nothing", () => {
  assert.equal(decide("0.5.9", { version: "0.5.10", breaking: false, mandatory: false }).action, "alert");
  assert.equal(decide("0.5.10", { version: "0.5.10" }).action, "none");
  assert.equal(decide("0.5.10", {}).action, "none");
});
