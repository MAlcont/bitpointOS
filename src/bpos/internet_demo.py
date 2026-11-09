"""One-command, genuine TCP end-to-end proof of concept for bpOS's first premise.

A Bitcoin-compatible ECDSA wallet key binds a device credential to an IP
endpoint. Two independent HTTP bpOS peers verify fresh endpoint challenges.
An advisory miner-facing interface sees the same registered identity.
"""
import asyncio
from contextlib import suppress

import httpx
import uvicorn
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .api import create_app
from .crypto import generate_private_key
from .internet_identity import (make_binding, verify_binding,
                                sign_endpoint_challenge, wallet_pub_hex)
from .network_demo import _listener, _wait_for_servers


class ChallengeRequest(BaseModel):
    binding_id: str
    challenge: str


async def run_internet_demo():
    """All keys disposable, all TCP endpoints localhost, no Bitcoin funds."""
    wallet_key = ec.generate_private_key(ec.SECP256K1())
    device_key = generate_private_key()
    sockets = [_listener(), _listener(), _listener()]
    urls = [f"http://127.0.0.1:{sock.getsockname()[1]}" for sock in sockets]
    wallet_pubkey = wallet_pub_hex(wallet_key)
    binding = make_binding(wallet_key, device_key, urls[0])
    proof_id = verify_binding(binding)

    endpoint_app = FastAPI(title="Proof-of-concept internet endpoint")

    @endpoint_app.post("/.well-known/bpos-challenge")
    def challenge(req: ChallengeRequest):
        if req.binding_id != proof_id or len(req.challenge) != 64:
            raise HTTPException(404, "Unrecognized proof/challenge")
        try:
            bytes.fromhex(req.challenge)
        except ValueError as exc:
            raise HTTPException(422, "Invalid challenge") from exc
        return {"signature": sign_endpoint_challenge(device_key, req.binding_id, req.challenge)}

    peers = [create_app(peers=[urls[2]], simulate=True),
             create_app(peers=[urls[1]], simulate=True)]
    apps = [endpoint_app] + peers
    servers = [uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False)) for app in apps]
    tasks = [asyncio.create_task(s.serve(sockets=[sock])) for s, sock in zip(servers, sockets)]
    try:
        await _wait_for_servers(servers, tasks)
        async with httpx.AsyncClient(timeout=4, trust_env=False) as client:
            # Bad wallet signature fails before it reaches the endpoint challenge.
            forged = {**binding, "body": {**binding["body"], "device_pubkey": "11" * 32}}
            rejected = await client.post(urls[1] + "/v1/internet-proofs", json={"binding": forged})
            if rejected.status_code != 422:
                raise RuntimeError("Altered wallet-device claim was not rejected")

            submitted = await client.post(urls[1] + "/v1/internet-proofs", json={"binding": binding})
            submitted.raise_for_status()
            if submitted.json()["proof_id"] != proof_id:
                raise RuntimeError("Node A returned different proof identifier")

            async def await_other_peer():
                while True:
                    response = await client.get(urls[2] + "/v1/internet-proofs")
                    response.raise_for_status()
                    if any(entry["proof_id"] == proof_id for entry in response.json()):
                        return
                    await asyncio.sleep(0.02)
            await asyncio.wait_for(await_other_peer(), timeout=5)

            inspected = await client.get(
                urls[2] + "/v1/mining/internet-proof-review/" + wallet_pubkey)
            inspected.raise_for_status()
            report = inspected.json()
            if report["proof_id"] != proof_id or report["proof_expired"]:
                raise RuntimeError("Peer B mining interface did not observe the verified proof")

            return {
                "result": "PASS: wallet + device signatures -> live IP challenge -> two bpOS peers -> miner interface",
                "wallet": {"public_key": wallet_pubkey, "curve": "secp256k1",
                           "key_possession_proven": True, "bitcoin_utxo_ownership_proven": False},
                "internet_shield": {"network": "TCP/IP localhost (actual HTTP)",
                                    "endpoint": urls[0], "challenge_verified_independently_by_peers": 2,
                                    "forged_binding_rejected": rejected.status_code == 422,
                                    "device_key": binding["body"]["device_pubkey"]},
                "gossip": {"source_peer": urls[1], "receiving_peer": urls[2],
                           "proof_id": proof_id, "status": "verified on both peers"},
                "miner_facing": {"proof_visible": True,
                                 "interface": "/v1/mining/internet-proof-review/{wallet_pubkey}",
                                 "stratum_job_issued": False},
                "limitations": {"IP_or_certificate_is_wallet_ownership": False,
                                "public_endpoint_proven": False, "hardware_attestation": False,
                                "bitcoin_consensus_enforced": False,
                                "bitcoin_funds_shielded": False},
            }
    finally:
        for server in servers:
            server.should_exit = True
        for task in tasks:
            if not task.done():
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(task, timeout=5)
        for sock in sockets:
            sock.close()
