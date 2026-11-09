"""Domain-separated signatures for the experimental bpOS overlay.

The signing keys used here are Ed25519 overlay credentials, NOT Bitcoin keys.
A software key is not hardware attestation. Production HSM integration is future work.
"""
import base64
import binascii
import hashlib
import json
import os
import time
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DOMAIN = b"bpOS/v2/signed-event:\x00"
EVENT_KINDS = frozenset({"enroll", "authorize", "veto"})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def public_hex(private_key):
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()


def generate_private_key():
    return Ed25519PrivateKey.generate()


def raw_private_hex(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()


def private_key_from_hex(key):
    if len(key) != 64:
        raise ValueError("Ed25519 private key must be 32 bytes (64 hex chars)")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(key))


def event_message(event):
    return DOMAIN + canonical({k: event[k] for k in ("version", "kind", "body", "signer", "nonce", "created_at")})


def sign_event(kind, body, private_key, *, now=None, nonce=None):
    if kind not in EVENT_KINDS:
        raise ValueError("Unknown event kind")
    message = {
        "version": 1,
        "kind": kind,
        "body": body,
        "signer": public_hex(private_key),
        "nonce": nonce or uuid.uuid4().hex,
        "created_at": int(time.time() if now is None else now),
    }
    message["signature"] = base64.b64encode(private_key.sign(event_message(message))).decode("ascii")
    return message


def verify_event(event, *, now=None, tolerance=86400):
    if not isinstance(event, dict):
        raise ValueError("Event must be an object")
    expected = {"version", "kind", "body", "signer", "nonce", "created_at", "signature"}
    if set(event) != expected:
        raise ValueError("Invalid event fields")
    if type(event["version"]) is not int or event["version"] != 1 or event["kind"] not in EVENT_KINDS:
        raise ValueError("Unsupported event version or kind")
    if not isinstance(event["body"], dict) or not isinstance(event["nonce"], str) or not (16 <= len(event["nonce"]) <= 128):
        raise ValueError("Malformed body or nonce")
    if type(event["created_at"]) is not int or abs(event["created_at"] - int(time.time() if now is None else now)) > tolerance:
        raise ValueError("Event outside replay window")
    if not isinstance(event["signer"], str) or len(event["signer"]) != 64:
        raise ValueError("Malformed signer")
    if not isinstance(event["signature"], str):
        raise ValueError("Malformed signature")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(event["signer"]))
        signature = base64.b64decode(event["signature"], validate=True)
        public_key.verify(signature, event_message(event))
    except (ValueError, InvalidSignature, TypeError, binascii.Error) as exc:
        raise ValueError("Invalid cryptographic signature") from exc
    return digest(event)


def write_private_key(path, private_key):
    """Refuse overwrites, write a local demo key with owner-only permissions."""
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(raw_private_hex(private_key) + "\n")
