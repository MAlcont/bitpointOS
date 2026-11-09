"""Optional HTTP gossip daemon. Use HTTPS, authentication and rate limits in deployment."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .bitcoin_rpc import BitcoinRPC
from .engine import BPError, Engine
from .miner import review_block_template
from .internet_identity import challenge_endpoint, verify_binding

logger = logging.getLogger("bpos")


class EventRequest(BaseModel):
    event: dict


class InternetProofRequest(BaseModel):
    binding: dict


class ObservationRequest(BaseModel):
    policy_id: str
    txid: str
    seen_height: int | None = None


class HeightRequest(BaseModel):
    height: int


def create_app(*, database=":memory:", peers=(), simulate=False, rpc=None, interval=10):
    engine = Engine(database)
    peer_urls = tuple(p.rstrip("/") for p in peers if p)

    async def fanout(event):
        if not peer_urls:
            return
        async with httpx.AsyncClient(timeout=5) as client:
            async def send(peer):
                try:
                    await client.post(peer + "/v1/events", json={"event": event})
                except httpx.HTTPError as exc:
                    logger.warning("Gossip to %s failed: %s", peer, exc)
            await asyncio.gather(*(send(peer) for peer in peer_urls))

    async def fanout_internet_binding(binding):
        if not peer_urls:
            return
        async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
            async def send(peer):
                try:
                    await client.post(peer + "/v1/internet-proofs", json={"binding": binding})
                except httpx.HTTPError as exc:
                    logger.warning("Internet proof gossip to %s failed: %s", peer, exc)
            await asyncio.gather(*(send(peer) for peer in peer_urls))

    async def watch_loop():
        while True:
            try:
                await rpc.scan(engine)
            except Exception:
                logger.exception("Bitcoin Core watcher scan failed")
            await asyncio.sleep(interval)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(watch_loop()) if rpc else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            engine.close()

    app = FastAPI(title="bpOS / Bitpoint OS", version="0.2.2", lifespan=lifespan,
                  description="Experimental ipayntity ownership overlay. NO consensus enforcement.")
    app.state.engine = engine

    @app.get("/health")
    def health():
        return {"name": "bpOS", "version": "0.2.2", "height": engine.height(),
                "consensus_enforced": False, "mode": "simulation" if simulate else "observer"}

    @app.get("/v1/policies")
    def policies():
        return engine.policies()

    @app.get("/v1/observations")
    def observations():
        return engine.observations()

    @app.get("/v1/status/{policy_id}/{txid}")
    def status(policy_id: str, txid: str):
        try:
            return engine.get_status(policy_id, txid)
        except BPError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/v1/events")
    async def events(req: EventRequest):
        try:
            result = engine.apply_event(req.event)
        except BPError as exc:
            raise HTTPException(422, str(exc)) from exc
        if result["accepted"]:
            # This is an opt-in allowlisted HTTP gossip *prototype*; no proof of global propagation.
            asyncio.create_task(fanout(req.event))
        return result

    @app.get("/v1/internet-proofs")
    def internet_proofs():
        return [{"proof_id": x["proof_id"], "verified_at": x["verified_at"],
                 "wallet_pubkey": x["binding"]["body"]["wallet_pubkey"],
                 "device_pubkey": x["binding"]["body"]["device_pubkey"],
                 "endpoint": x["binding"]["body"]["endpoint"]}
                for x in engine.internet_bindings()]

    @app.post("/v1/internet-proofs")
    async def internet_proof(req: InternetProofRequest):
        try:
            proof_id = verify_binding(req.binding)
            # Important: every peer performs its OWN fresh challenge, not trusting
            # the originating peer's assertion of endpoint reachability.
            await challenge_endpoint(req.binding)
            result = engine.register_internet_binding(req.binding, proof_id, int(time.time()))
        except (ValueError, BPError, httpx.HTTPError) as exc:
            raise HTTPException(422, str(exc)) from exc
        if not result["already_known"]:
            asyncio.create_task(fanout_internet_binding(req.binding))
        return {**result, "wallet_key_verified": True, "device_key_verified": True,
                "fresh_endpoint_challenge_verified": True,
                "bitcoin_utxo_ownership_proven": False,
                "hardware_attested": False, "bitcoin_consensus_enforced": False}

    @app.get("/v1/mining/internet-proof-review/{wallet_pubkey}")
    def miner_internet_proof_review(wallet_pubkey: str):
        try:
            row = engine.internet_binding(wallet_pubkey)
        except BPError as exc:
            raise HTTPException(404, str(exc)) from exc
        binding = row["binding"]
        return {"proof_id": row["proof_id"], "wallet_pubkey": wallet_pubkey,
                "endpoint": binding["body"]["endpoint"],
                "device_pubkey": binding["body"]["device_pubkey"],
                "verified_endpoint_at": row["verified_at"],
                "proof_expired": int(time.time()) >= binding["body"]["expires_at"],
                "purpose": "read-only shared miner-control-plane proof inspection",
                "bitcoin_utxo_ownership_proven": False,
                "template_modified": False, "stratum_job_issued": False,
                "bitcoin_consensus_enforced": False}

    if rpc:
        @app.get("/v1/mining/template-review")
        async def template_review():
            try:
                return await review_block_template(rpc, engine)
            except (ValueError, RuntimeError, httpx.HTTPError) as exc:
                raise HTTPException(503, str(exc)) from exc

    if simulate:
        @app.post("/v1/simulate/height")
        def set_height(req: HeightRequest):
            try:
                engine.set_height(req.height)
            except BPError as exc:
                raise HTTPException(422, str(exc)) from exc
            return {"height": engine.height()}

        @app.post("/v1/simulate/observe")
        def observe(req: ObservationRequest):
            try:
                return engine.observe(req.policy_id, req.txid, req.seen_height)
            except BPError as exc:
                raise HTTPException(422, str(exc)) from exc
    return app


def create_app_from_env():
    peers = os.getenv("BPOS_PEERS", "").split(",")
    rpc = None
    if os.getenv("BPOS_BITCOIN_RPC_URL"):
        rpc = BitcoinRPC(os.environ["BPOS_BITCOIN_RPC_URL"],
                         os.getenv("BPOS_BITCOIN_RPC_USER", ""),
                         os.getenv("BPOS_BITCOIN_RPC_PASSWORD", ""))
    simulate = os.getenv("BPOS_SIMULATE", "0") == "1"
    if simulate and rpc:
        raise ValueError("BPOS_SIMULATE and live Bitcoin RPC are mutually exclusive")
    return create_app(database=os.getenv("BPOS_DB", "bpos.sqlite3"), peers=peers,
                      simulate=simulate, rpc=rpc, interval=float(os.getenv("BPOS_POLL_SECONDS", "10")))


app = create_app_from_env()
