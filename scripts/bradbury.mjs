// Bradbury (chain 4221) deploy / submit / read for ChangelogGuard, with genlayer-js from consumer/.
// Usage (from repo root):
//   node scripts/bradbury.mjs deploy
//   node scripts/bradbury.mjs submit <address> <network> <version> <url>
//   node scripts/bradbury.mjs read <address> <network>
//   node scripts/bradbury.mjs tx <hash>
// The deployer key is read from $DEPLOYER_ENV (default ../.secrets/deployer-changelog-guard.env) inside this
// process only; it is never printed. Full receipts go to artifacts/ (gitignored).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const GLJS = resolve(ROOT, "consumer/node_modules/genlayer-js/dist");
const { createClient, createAccount } = await import(`${GLJS}/index.js`);
const { testnetBradbury } = await import(`${GLJS}/chains/index.js`);
const { readLatest } = await import(`${ROOT}/consumer/read-verdict.mjs`);

const RPC = "https://rpc.testnet-chain.genlayer.com";
// rpc.testnet-chain.genlayer.com answers eth_* only ("the method gen_call does not exist/is not available");
// view calls go to the GenLayer RPC that genlayer-py's testnet_bradbury chain uses.
const READ_RPC = process.env.READ_RPC || "https://rpc-bradbury.genlayer.com";
const json = (v) => JSON.stringify(v, (_, x) => (typeof x === "bigint" ? x.toString() : x instanceof Map ? Object.fromEntries(x) : x), 2);

function loadAccount() {
  const path = process.env.DEPLOYER_ENV || resolve(ROOT, "../.secrets/deployer-changelog-guard.env");
  const env = Object.fromEntries(
    readFileSync(path, "utf8").split("\n").filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1).trim()]),
  );
  const pk = env.BRADBURY_PRIVATE_KEY.startsWith("0x") ? env.BRADBURY_PRIVATE_KEY : `0x${env.BRADBURY_PRIVATE_KEY}`;
  const account = createAccount(pk);
  if (account.address.toLowerCase() !== env.BRADBURY_ADDRESS.toLowerCase()) throw new Error("key does not match BRADBURY_ADDRESS");
  return account;
}

async function balance(address, tries = 5) {
  for (let i = 0; i < tries; i++) {
    try {
      const v = await balanceOnce(address);
      if (v !== undefined) return v;
    } catch {}
    await new Promise((ok) => setTimeout(ok, 3000));
  }
  throw new Error("eth_getBalance failed");
}
async function balanceOnce(address) {
  const r = await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_getBalance", params: [address, "latest"] }) });
  const j = await r.json();
  return j.result === undefined ? undefined : BigInt(j.result);
}
// genlayer-js rc.2 reads FeeManager.estimateProposeReceiptGas with eth_call + gasPrice but no `from`, which
// Bradbury rejects (zero address has no funds). Fill `from` with the sender for eth_call only; nothing else changes.
function fillCallSender(from) {
  const orig = globalThis.fetch;
  globalThis.fetch = (url, init) => {
    if (init && typeof init.body === "string" && init.body.includes('"eth_call"')) {
      const fix = (m) => (m.method === "eth_call" && m.params?.[0] && !m.params[0].from ? { ...m, params: [{ ...m.params[0], from }, ...m.params.slice(1)] } : m);
      const body = JSON.parse(init.body);
      init = { ...init, body: JSON.stringify(Array.isArray(body) ? body.map(fix) : fix(body)) };
    }
    return orig(url, init);
  };
}
const gen = (wei) => `${(Number(wei) / 1e18).toFixed(6)} GEN`;

function save(name, obj) {
  mkdirSync(resolve(ROOT, "artifacts"), { recursive: true });
  const p = resolve(ROOT, "artifacts", name);
  writeFileSync(p, json(obj));
  return p;
}

async function waitReceipt(client, hash) {
  const r = await client.waitForTransactionReceipt({ hash, waitUntil: "decided", interval: 5000, retries: 240 });
  return r;
}

function summary(r) {
  const lr = r?.consensus_data?.leader_receipt;
  const leader = Array.isArray(lr) ? lr[0] : lr;
  return {
    status: r.statusName ?? r.status_name ?? r.status,
    result: r.resultName ?? r.result_name ?? r.result,
    txExecutionResult: r.txExecutionResultName ?? r.tx_execution_result_name,
    leader_execution_result: leader?.execution_result,
    leader_result: leader?.result,
    contract_address: r.data?.contract_address ?? r.txDataDecoded?.contractAddress ?? r.recipient,
  };
}

const [cmd, ...a] = process.argv.slice(2);
const chain = { ...testnetBradbury, rpcUrls: { default: { http: [RPC] } } };

if (cmd === "read") {
  const client = createClient({ chain: { ...testnetBradbury, rpcUrls: { default: { http: [READ_RPC] } } } });
  console.log(json(await readLatest(client, a[0], a[1])));
} else if (cmd === "tx") {
  const client = createClient({ chain });
  const r = await client.getTransaction({ hash: a[0] });
  console.log("saved:", save(`tx-${a[0]}.json`, r));
  console.log(json(summary(r)));
} else if (cmd === "deploy" || cmd === "submit") {
  const account = loadAccount();
  fillCallSender(account.address);
  const client = createClient({ chain, account });
    const before = await balance(account.address);
  console.log("sender:", account.address, "balance before:", gen(before));
  // Bradbury v0.6 consensus rejects a zero fee deposit (FeeValueMustBeNonZero): estimate a full fee
  // object from the network's fee policy, as the genlayer CLI does, and cap it.
  // A submit runs a web fetch plus an LLM call on the leader and on every validator; the default time-unit
  // allocation (leader 100, validator 200) ended in LEADER_TIMEOUT on 26 Oct. Override with LEADER_TU / VALIDATOR_TU.
  const tu = {};
  if (process.env.LEADER_TU) tu.leaderTimeunitsAllocation = BigInt(process.env.LEADER_TU);
  if (process.env.VALIDATOR_TU) tu.validatorTimeunitsAllocation = BigInt(process.env.VALIDATOR_TU);
  const est = await client.estimateTransactionFees(tu);
  const fees = { distribution: est.distribution, ...(est.messageAllocations ? { messageAllocations: est.messageAllocations } : {}), feeValue: est.feeValue };
  console.log("fee deposit (estimate):", gen(fees.feeValue), json({ distribution: est.distribution, policy: est.policy }));
  const CAP = BigInt(process.env.MAX_FEE_WEI || 25n * 10n ** 18n);
  if (fees.feeValue > CAP) throw new Error(`fee deposit ${gen(fees.feeValue)} exceeds cap ${gen(CAP)}`);
  let hash;
  if (cmd === "deploy") {
    const code = readFileSync(resolve(ROOT, "contracts/changelog_guard.py"), "utf8");
    hash = await client.deployContract({ code, args: [], fees });
  } else {
    const [address, network, version, url] = a;
    hash = await client.writeContract({ address, functionName: "submit", args: [network, version, url], value: 0n, fees });
  }
  console.log("tx hash:", hash);
  let r;
  try {
    r = await waitReceipt(client, hash);
  } catch (e) {
    console.log("wait error:", e.message);
    r = await client.getTransaction({ hash });
  }
  console.log("saved:", save(`${cmd}-${hash}.json`, r));
  console.log(json(summary(r)));
  const after = await balance(account.address);
  console.log("balance after:", gen(after), "spent:", gen(before - after));
} else {
  console.error("usage: deploy | submit <address> <network> <version> <url> | read <address> <network> | tx <hash>");
  process.exit(2);
}
