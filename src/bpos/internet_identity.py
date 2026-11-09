"""bpOS alpha: wallet-key + device-key + reachable internet endpoint binding.

This proves signatures by a Bitcoin-compatible secp256k1 key and an Ed25519
identity key, and fresh challenge control of a network endpoint. It does NOT
prove possession of Bitcoin UTXOs, stable IP allocation, hardware custody,
TLS certification, or any Bitcoin consensus rule.
"""
import base64
import binascii
import hashlib
import ipaddress
import secrets
import time
from urllib.parse import urlsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

from .crypto import canonical, digest, public_hex

BINDING_DOMAIN = b"bpOS/internet-binding/v1:\x00"
CHALLENGE_DOMAIN = b"bpOS/internet-challenge/v1:\x00"
MAX_AGE = 600  # intentionally short-lived, proof-of-concept only
CLOCK_SKEW = 60


def wallet_pub_hex(private_key):
    """Compressed public point for a Bitcoin-compatible (secp256k1) key."""
    return private_key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    ).hex()


def _endpoint(endpoint):
    """Restrict active verification to loopback, avoiding open proxy/SSRF in this alpha.

    Public HTTPS and real IP/certificate validation require an explicit next
    protocol design; this proof runs across actual localhost TCP connections.
    """
    if not isinstance(endpoint, str) or len(endpoint) > 128:
        raise ValueError("Invalid endpoint")
    parsed = urlsplit(endpoint)
    try:
        host = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except (ValueError, TypeError) as exc:
        raise ValueError("Endpoint must use a loopback IP and explicit port") from exc
    if (parsed.scheme != "http" or not host.is_loopback or not isinstance(host, ipaddress.IPv4Address)
            or not port or parsed.username or parsed.password or parsed.path not in ("", "/")
            or parsed.query or parsed.fragment or endpoint != f"http://{host}:{port}"):
        raise ValueError("For safety the alpha only accepts http://127.0.0.1:<port>")
    return endpoint


def binding_message(body):
    return BINDING_DOMAIN + canonical(body)


def make_binding(wallet_key, device_key, endpoint, *, now=None, nonce=None, ttl=300):
    _endpoint(endpoint)
    issued = int(time.time() if now is None else now)
    if type(ttl) is not int or not 1 <= ttl <= MAX_AGE:
        raise ValueError("Invalid proof lifetime")
    body = {
        "protocol": "bpos-internet-binding-v1",
        "wallet_pubkey": wallet_pub_hex(wallet_key),
        "device_pubkey": public_hex(device_key),
        "endpoint": endpoint,
        "nonce": nonce or secrets.token_hex(16),
        "issued_at": issued,
        "expires_at": issued + ttl,
    }
    message = binding_message(body)
    return {
        "body": body,
        "wallet_signature": base64.b64encode(wallet_key.sign(message, ec.ECDSA(hashes.SHA256()))).decode("ascii"),
        "device_signature": base64.b64encode(device_key.sign(message)).decode("ascii"),
    }


def _decode_signature(value):
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("Invalid signature format")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid signature encoding") from exc


def verify_binding(binding, *, now=None):
    if not isinstance(binding, dict) or set(binding) != {"body", "wallet_signature", "device_signature"}:
        raise ValueError("Invalid binding envelope")
    body = binding["body"]
    if not isinstance(body, dict) or set(body) != {
        "protocol", "wallet_pubkey", "device_pubkey", "endpoint", "nonce", "issued_at", "expires_at"
    } or body["protocol"] != "bpos-internet-binding-v1":
        raise ValueError("Invalid binding body")
    _endpoint(body["endpoint"])
    if (type(body["issued_at"]) is not int or type(body["expires_at"]) is not int
            or not isinstance(body["nonce"], str) or len(body["nonce"]) != 32):
        raise ValueError("Invalid binding timestamps or nonce")
    try:
        bytes.fromhex(body["nonce"])
        wallet_bytes = bytes.fromhex(body["wallet_pubkey"])
        device_bytes = bytes.fromhex(body["device_pubkey"])
        if len(wallet_bytes) != 33 or wallet_bytes[0] not in (2, 3) or len(device_bytes) != 32:
            raise ValueError("Invalid public key length")
        wallet_pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), wallet_bytes)
        device_pub = ed25519.Ed25519PublicKey.from_public_bytes(device_bytes)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Malformed identity key or nonce") from exc
    now = int(time.time() if now is None else now)
    if not (now - MAX_AGE <= body["issued_at"] <= now + CLOCK_SKEW
            and 0 < body["expires_at"] - body["issued_at"] <= MAX_AGE
            and now < body["expires_at"]):
        raise ValueError("Expired or not-yet-valid binding")
    try:
        message = binding_message(body)
        wallet_pub.verify(_decode_signature(binding["wallet_signature"]), message, ec.ECDSA(hashes.SHA256()))
        device_pub.verify(_decode_signature(binding["device_signature"]), message)
    except (InvalidSignature, ValueError) as exc:
        raise ValueError("Invalid wallet/device binding signature") from exc
    return digest(binding)


def sign_endpoint_challenge(device_key, binding_id, challenge):
    return base64.b64encode(device_key.sign(CHALLENGE_DOMAIN + canonical({
        "binding_id": binding_id, "challenge": challenge
    }))).decode("ascii")


def verify_endpoint_response(binding, binding_id, challenge, signature):
    try:
        pub = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(binding["body"]["device_pubkey"]))
        pub.verify(_decode_signature(signature), CHALLENGE_DOMAIN + canonical({
            "binding_id": binding_id, "challenge": challenge
        }))
    except (InvalidSignature, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Endpoint did not prove possession of the bound device key") from exc


async def challenge_endpoint(binding, *, client=None):
    """Check endpoint reachability by NEW unpredictable challenge per verifier.

    Signature over the challenge is necessary: HTTP connectivity or IP
    assignment alone is not a proof of identity. Never follow redirects.
    """
    binding_id = verify_binding(binding)
    challenge = secrets.token_hex(32)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=2, follow_redirects=False, trust_env=False)
    try:
        response = await client.post(binding["body"]["endpoint"] + "/.well-known/bpos-challenge",
                                     json={"binding_id": binding_id, "challenge": challenge})
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or set(data) != {"signature"}:
            raise ValueError("Malformed challenge response")
        verify_endpoint_response(binding, binding_id, challenge, data["signature"])
    finally:
        if owns_client:
            await client.aclose()
    return binding_id
