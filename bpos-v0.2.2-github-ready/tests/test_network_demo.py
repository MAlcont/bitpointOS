"""Smoke test of signed gossip over actual loopback TCP connections."""
import asyncio

from bpos.network_demo import run_network_demo


def test_end_to_end_gossip_to_miner_review():
    result = asyncio.run(run_network_demo())
    assert result["result"].startswith("PASS")
    assert result["network"]["independent_peers"] == 2
    assert result["network"]["gossip_signature_verified"]
    assert result["network"]["forged_event_rejected"]
    assert result["shield"] == {"before": "VETO_WINDOW_OPEN", "after": "OWNER_VETO"}
    assert result["mining_adapter"]["candidate_spend_flagged"]
    assert result["mining_adapter"]["state"] == "OWNER_VETO"
    assert result["mining_adapter"]["template_modified"] is False
    assert result["limits"]["bitcoin_consensus_enforced"] is False
    assert result["limits"]["bitcoin_funds_frozen_or_reversed"] is False
