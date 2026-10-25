"""Smoke test against the local Studio (GenLayer Studio, RPC port from STUDIO_RPC). No LLM key, no real wallet:
uses an in-memory throwaway account that is never written to disk. Refuses non-local RPC URLs."""
import os, sys
from pathlib import Path

from genlayer_py import create_account, create_client
from genlayer_py.chains import localnet
from genlayer_py.types import TransactionStatus

RPC = os.environ.get("STUDIO_RPC", "http://127.0.0.1:20481/api")
assert RPC.startswith("http://127.0.0.1:") or RPC.startswith("http://localhost:"), "local Studio only"
CONTRACT = (Path(__file__).resolve().parents[1] / "contracts" / "changelog_guard.py").read_bytes()

account = create_account()
chain = localnet.model_copy(update={"rpc_urls": {"default": {"http": [RPC]}}}) if hasattr(localnet, "model_copy") else localnet
client = create_client(chain=chain, endpoint=RPC, account=account)

tx = client.deploy_contract(code=CONTRACT, args=[], account=account)
receipt = client.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40)
addr = receipt["data"]["contract_address"] if "data" in receipt else receipt["tx_data_decoded"]["contract_address"]
print("deployed:", addr)
print("get_latest(empty):", client.read_contract(address=addr, function_name="get_latest", args=["bradbury-phase2"]))
print("get_release(empty):", client.read_contract(address=addr, function_name="get_release", args=["bradbury-phase2", "0.6.0-rc.2"]))

# Disallowed URL: must be rejected by the contract before any web/LLM call (works without an LLM key).
tx = client.write_contract(address=addr, function_name="submit", args=["bradbury-phase2", "v0.6.0-rc.2", "https://evil.example/x"], account=account)
r = client.wait_for_transaction_receipt(transaction_hash=tx, status=TransactionStatus.ACCEPTED, interval=3000, retries=40)
lr = r["consensus_data"]["leader_receipt"][0]
print("bad-url submit: status", r.get("status_name"), "| leader execution_result:", lr["execution_result"])
assert lr["execution_result"] == "ERROR" and "url is not an allowed source" in str(lr["result"]), lr["result"]
print("rejected by contract:", lr["result"])
print("get_release after rejected submit:", client.read_contract(address=addr, function_name="get_release", args=["bradbury-phase2", "0.6.0-rc.2"]))


# Not run here: a submit with an allowed URL needs a real LLM provider. Observed once (23 Oct) with the stub
# provider: web fetch ran, then the leader failed with LLM_NO_PROVIDER and the tx kept resetting, so it is
# deliberately not part of this script.
print('studio smoke OK')
