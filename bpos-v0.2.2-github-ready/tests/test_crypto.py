import pytest
from bpos.crypto import (generate_private_key, public_hex, sign_event,
                         verify_event, private_key_from_hex, raw_private_hex)


def test_keys_roundtrip():
    key = generate_private_key()
    assert public_hex(private_key_from_hex(raw_private_hex(key))) == public_hex(key)


def test_signed_events():
    key = generate_private_key()
    event = sign_event("veto", {"x": 1}, key, now=1000, nonce="0" * 32)
    assert len(verify_event(event, now=1000)) == 64


def test_expired_events():
    key = generate_private_key()
    event = sign_event("veto", {"x": 1}, key, now=1000)
    with pytest.raises(ValueError, match="replay window"):
        verify_event(event, now=1000 + 90000)


def test_malformed_base64_signature():
    key = generate_private_key()
    event = sign_event("veto", {"x": 1}, key)
    event["signature"] = "!!not-base64!!"
    with pytest.raises(ValueError, match="cryptographic signature"):
        verify_event(event)
