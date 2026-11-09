"""Read-only miner-template review via Bitcoin Core getblocktemplate.

This is the common miner-facing control surface: Bitcoin Core makes candidate
block templates; pools/proxies turn those templates into ASIC hashing jobs.
No job modification, actual Stratum transport, or Bitcoin consensus enforcement.
"""
from .model import parse_outpoint


async def review_block_template(rpc, engine, *, max_transactions=5000):
    template = await rpc.call("getblocktemplate", [{"rules": ["segwit"]}])
    transactions = template.get("transactions", [])
    if len(transactions) > max_transactions:
        raise ValueError("Template too large for research inspector; review aborted")
    indexed = {}
    for policy in engine.policies():
        outpoint = parse_outpoint(policy["outpoint"])
        indexed[(outpoint["txid"], outpoint["vout"])] = policy
    flagged = []
    for tx in transactions:
        decoded = await rpc.call("decoderawtransaction", [tx["data"]])
        txid = decoded["txid"]
        for vin in decoded.get("vin", []):
            policy = indexed.get((vin.get("txid"), vin.get("vout")))
            if policy:
                status = engine.observe(policy["policy_id"], txid, engine.height())
                flagged.append({"txid": txid, "outpoint": policy["outpoint"],
                                "policy_id": policy["policy_id"], "state": status["state"],
                                "ipayntity": policy["ipayntity"], "mode": policy["mode"]})
    return {"height": template.get("height"), "total_transactions": len(transactions),
            "flagged": flagged, "template_modified": False, "bitcoin_consensus_enforced": False,
            "note": "Advisory report only; miners and validating nodes remain unrestricted."}
