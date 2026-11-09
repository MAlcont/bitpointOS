"""End-to-end bpOS *overlay* demo using two real HTTP peers on loopback.

Both peers have independent SQLite stores, exchange Ed25519-signed events over
TCP/IP, and peer B evaluates the result through the existing miner-template
inspector. The Core response is intentionally synthetic; no Bitcoin node,
Stratum job, ASIC, hardware attestation, or Bitcoin consensus is involved.
"""
import asyncio
import socket
from contextlib import suppress

import httpx
import uvicorn

from .api import create_app
from .crypto import generate_private_key, public_hex, sign_event
from .miner import review_block_template
from .model import ipayntity_for


class DemoCore:
    """A stand-in for Core's two read-only template inspection RPCs."""

    def __init__(self, *, outpoint, spending_txid):
        self.outpoint = outpoint
        self.spending_txid = spending_txid

    async def call(self, method, params=None):
        if method == "getblocktemplate":
            return {"height": 101, "transactions": [{"data": "synthetic-transaction"}]}
        if method == "decoderawtransaction":
            return {"txid": self.spending_txid,
                    "vin": [{"txid": self.outpoint.split(":")[0],
                             "vout": int(self.outpoint.split(":")[1])}]}
        raise AssertionError(f"Unexpected demo RPC: {method}")


def _listener():
    """Reserve an OS-selected port and hand the bound socket to uvicorn."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
    except Exception:
        sock.close()
        raise
    return sock


async def _wait_for_servers(servers, tasks, *, timeout=8):
    async def check():
        while not all(s.started for s in servers):
            for t in tasks:
                if t.done():
                    raise RuntimeError("A demo HTTP peer stopped before startup")
            await asyncio.sleep(0.02)
    await asyncio.wait_for(check(), timeout=timeout)


async def _wait_for_policy(client, url, policy_id, *, timeout=5):
    """HTTP gossip fans out asynchronously, so test actual peer propagation."""
    async def check():
        while True:
            response = await client.get(url + "/v1/policies")
            response.raise_for_status()
            if any(p["policy_id"] == policy_id for p in response.json()):
                return
            await asyncio.sleep(0.03)
    await asyncio.wait_for(check(), timeout=timeout)


async def _wait_for_status(client, url, policy_id, txid, target, *, timeout=5):
    async def check():
        while True:
            response = await client.get(f"{url}/v1/status/{policy_id}/{txid}")
            response.raise_for_status()
            if response.json()["state"] == target:
                return response.json()
            await asyncio.sleep(0.03)
    return await asyncio.wait_for(check(), timeout=timeout)


async def run_network_demo():
    """Return an auditable summary of actual two-peer HTTP event propagation.

    No external network calls, existing keys, Bitcoin wallet, node, or mining
    device are required. Both peers bind to localhost only.
    """
    owner = generate_private_key()  # Disposable *software* Ed25519 key.
    public_key = public_hex(owner)
    outpoint = "a" * 64 + ":7"  # Synthetic UTXO; ownership is not proven.
    txid = "b" * 64  # Synthetic spending transaction.
    policy = {"outpoint": outpoint, "device_pubkey": public_key,
              "ipayntity": ipayntity_for(public_key),
              "mode": "veto_window", "delay_blocks": 6}

    sockets = [_listener(), _listener()]
    urls = [f"http://127.0.0.1:{sock.getsockname()[1]}" for sock in sockets]
    apps = [create_app(simulate=True, peers=[urls[1]]),
            create_app(simulate=True, peers=[urls[0]])]
    servers = [uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
               for app in apps]
    tasks = [asyncio.create_task(server.serve(sockets=[sock]))
             for server, sock in zip(servers, sockets)]
    try:
        await _wait_for_servers(servers, tasks)
        async with httpx.AsyncClient(timeout=4) as client:
            # Both observers see the same *simulated* block height.
            for url in urls:
                response = await client.post(url + "/v1/simulate/height", json={"height": 100})
                response.raise_for_status()

            enrollment = sign_event("enroll", policy, owner)
            response = await client.post(urls[0] + "/v1/events", json={"event": enrollment})
            response.raise_for_status()
            policy_id = response.json()["policy_id"]
            await _wait_for_policy(client, urls[1], policy_id)

            # Independent observers see the candidate withdrawal.
            for url in urls:
                response = await client.post(url + "/v1/simulate/observe",
                                             json={"policy_id": policy_id, "txid": txid})
                response.raise_for_status()
            before = (await client.get(f"{urls[1]}/v1/status/{policy_id}/{txid}")).json()

            # A tampered event delivered to peer B is rejected locally.
            # This tests HTTP-boundary signature verification, not just a local helper.
            veto = sign_event("veto", {"policy_id": policy_id, "txid": txid}, owner)
            forged = {**veto, "body": {"policy_id": policy_id, "txid": "c" * 64}}
            rejected = await client.post(urls[1] + "/v1/events", json={"event": forged})
            if rejected.status_code != 422:
                raise RuntimeError("Peer accepted a modified, invalidly signed event")

            # Device signs a real veto; only peer A receives it directly.
            response = await client.post(urls[0] + "/v1/events", json={"event": veto})
            response.raise_for_status()
            after = await _wait_for_status(client, urls[1], policy_id, txid, "OWNER_VETO")

            # Peer B's miner-facing adapter reads its own independently
            # populated event store. Core's block-template RPC is mocked.
            report = await review_block_template(DemoCore(outpoint=outpoint, spending_txid=txid),
                                                 apps[1].state.engine)
            flagged = report["flagged"]
            if not (before["state"] == "VETO_WINDOW_OPEN"
                    and after["state"] == "OWNER_VETO"
                    and len(flagged) == 1
                    and flagged[0]["state"] == "OWNER_VETO"
                    and flagged[0]["ipayntity"] == policy["ipayntity"]):
                raise RuntimeError("Gossip-to-miner demonstration did not agree across peers")
            return {
                "result": "PASS: signed owner veto reached independent miner-facing peer",
                "identity": {"ipayntity": policy["ipayntity"], "credential": "ephemeral software key"},
                "network": {"transport": "TCP loopback HTTP", "independent_peers": 2,
                            "gossip_signature_verified": True,
                            "forged_event_rejected": rejected.status_code == 422},
                "shield": {"before": before["state"], "after": after["state"]},
                "mining_adapter": {"candidate_spend_flagged": True,
                                   "state": flagged[0]["state"],
                                   "core_template": "synthetic RPC stub",
                                   "template_modified": report["template_modified"]},
                "limits": {"hardware_attestation": False, "bitcoin_ownership_proven": False,
                           "bitcoin_consensus_enforced": report["bitcoin_consensus_enforced"],
                           "bitcoin_funds_frozen_or_reversed": False,
                           "stratum_jobs_issued": False},
            }
    finally:
        for server in servers:
            server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=8)
        except Exception:
            for task in tasks:
                task.cancel()
            with suppress(Exception):
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for sock in sockets:
                sock.close()
