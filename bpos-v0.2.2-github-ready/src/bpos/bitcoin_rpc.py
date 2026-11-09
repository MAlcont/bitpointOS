"""READ-ONLY Bitcoin Core RPC bridge, no wallet or mining privileges."""
import httpx
from .model import parse_outpoint


class BitcoinRPC:
    def __init__(self, url, username, password, timeout=10):
        self.url = url
        self.auth = (username, password)
        self.timeout = timeout

    async def call(self, method, params=None):
        payload = {"jsonrpc": "2.0", "id": "bpos", "method": method, "params": [] if params is None else params}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.url, json=payload, auth=self.auth)
            response.raise_for_status()
            body = response.json()
        if body.get("error"):
            raise RuntimeError(f"Bitcoin RPC {method} error: {body['error']}")
        return body["result"]

    async def scan(self, engine):
        """Check registered prevouts in the local mempool, *not* chain history.

        Does not discover spends missed while offline, or provide consensus enforcement.
        """
        height = await self.call("getblockcount")
        engine.set_height(height)
        policies = engine.policies()
        if not policies:
            return []
        outpoints = [parse_outpoint(p["outpoint"]) for p in policies]
        rows = await self.call("gettxspendingprevout", [outpoints, {"mempool_only": True}])
        results = []
        for policy, row in zip(policies, rows):
            spending_txid = row.get("spendingtxid")
            if spending_txid:
                results.append(engine.observe(policy["policy_id"], spending_txid, height))
        return results
