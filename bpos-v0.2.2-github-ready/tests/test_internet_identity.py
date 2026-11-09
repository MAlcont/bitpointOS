"""Cryptographic and protocol negative tests for Internet Proof v1."""
import asyncio
import copy
import time

import pytest
import httpx
from cryptography.hazmat.primitives.asymmetric import ec

from bpos.crypto import generate_private_key
from bpos.internet_identity import (
    make_binding, verify_binding, wallet_pub_hex, sign_endpoint_challenge,
    verify_endpoint_response, challenge_endpoint,
)
from bpos.internet_demo import run_internet_demo


def keyset():
    return ec.generate_private_key(ec.SECP256K1()), generate_private_key()


def test_binding_proves_wallet_key_and_device_key():
    wallet, device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9123", now=1000, nonce="ab" * 16)
    assert binding["body"]["wallet_pubkey"] == wallet_pub_hex(wallet)
    assert len(verify_binding(binding, now=1010)) == 64


def test_forged_association_or_endpoint_rejected():
    wallet, device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9123", now=1000)
    for key, replacement in (("device_pubkey", "11" * 32), ("endpoint", "http://127.0.0.1:9001"),
                             ("wallet_pubkey", wallet_pub_hex(ec.generate_private_key(ec.SECP256K1())))):
        forged = copy.deepcopy(binding)
        forged["body"][key] = replacement
        with pytest.raises(ValueError):
            verify_binding(forged, now=1001)


def test_invalid_device_signature_rejected():
    wallet, device = keyset()
    _, bad_device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9000", now=1000)
    other = make_binding(wallet, bad_device, "http://127.0.0.1:9000", now=1000)
    forged = {**binding, "device_signature": other["device_signature"]}
    with pytest.raises(ValueError, match="signature"):
        verify_binding(forged, now=1001)


def test_time_limit_and_future_binding_rejected():
    wallet, device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9000", now=1000, ttl=60)
    assert verify_binding(binding, now=1059)
    for t in (1060, 1400, 939):
        with pytest.raises(ValueError, match="Expired|not-yet"):
            verify_binding(binding, now=t)


def test_untrusted_network_addresses_rejected():
    wallet, device = keyset()
    for endpoint in ("http://192.0.2.2:80", "http://example.org:8080", "https://127.0.0.1:443",
                     "http://127.0.0.1:9000/path", "http://user:pass@127.0.0.1:9000"):
        with pytest.raises(ValueError):
            make_binding(wallet, device, endpoint)


def test_endpoint_challenge_rejects_replay_or_wrong_device():
    wallet, device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9000")
    proof_id = verify_binding(binding)
    sig = sign_endpoint_challenge(device, proof_id, "a" * 64)
    verify_endpoint_response(binding, proof_id, "a" * 64, sig)
    with pytest.raises(ValueError):
        verify_endpoint_response(binding, proof_id, "b" * 64, sig)
    with pytest.raises(ValueError):
        verify_endpoint_response(binding, "f" * 64, "a" * 64, sig)


def test_verifier_does_not_trust_http_200_without_correct_challenge():
    wallet, device = keyset()
    binding = make_binding(wallet, device, "http://127.0.0.1:9000")
    proof_id = verify_binding(binding)
    old_signature = sign_endpoint_challenge(device, proof_id, "0" * 64)

    async def verify():
        async def handler(request):
            return httpx.Response(200, json={"signature": old_signature})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(ValueError, match="Endpoint did not prove"):
                await challenge_endpoint(binding, client=client)
    asyncio.run(verify())


def test_network_and_miner_interface_end_to_end():
    data = asyncio.run(run_internet_demo())
    assert data["wallet"]["key_possession_proven"] is True
    assert data["internet_shield"]["challenge_verified_independently_by_peers"] == 2
    assert data["internet_shield"]["forged_binding_rejected"]
    assert data["miner_facing"]["proof_visible"]
    assert data["limitations"]["bitcoin_consensus_enforced"] is False
