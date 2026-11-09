import pytest
from bpos.crypto import generate_private_key, public_hex, sign_event
from bpos.engine import BPError, Engine
from bpos.model import ipayntity_for


def test_owner_veto(setup_engine):
    e, owner, pid, _ = setup_engine
    assert e.get_status(pid, "b" * 64)["state"] == "VETO_WINDOW_OPEN"
    e.apply_event(sign_event("veto", {"policy_id": pid, "txid": "b" * 64}, owner))
    assert e.get_status(pid, "b" * 64)["state"] == "OWNER_VETO"
    assert e.get_status(pid, "b" * 64)["on_chain_enforced"] is False


def test_outsider_cannot_veto(setup_engine):
    e, _, pid, _ = setup_engine
    with pytest.raises(BPError, match="not the registered"):
        e.apply_event(sign_event("veto", {"policy_id": pid, "txid": "b" * 64}, generate_private_key()))


def test_signatures_and_duplicate_suppression(setup_engine):
    e, owner, pid, _ = setup_engine
    ev = sign_event("authorize", {"policy_id": pid, "txid": "b" * 64}, owner)
    assert e.apply_event(ev)["accepted"] is True
    assert e.apply_event(ev)["duplicate"] is True
    assert e.get_status(pid, "b" * 64)["state"] == "AUTHORIZED_OVERLAY"
    ev["body"]["txid"] = "c" * 64
    with pytest.raises(BPError, match="signature"):
        e.apply_event(ev)


def test_expired_window_is_advisory(setup_engine):
    e, owner, pid, _ = setup_engine
    e.set_height(106)
    assert e.get_status(pid, "b" * 64)["state"] == "WINDOW_ELAPSED"
    with pytest.raises(BPError, match="window already elapsed"):
        e.apply_event(sign_event("veto", {"policy_id": pid, "txid": "b" * 64}, owner))


def test_instant_requires_authorization():
    e = Engine()
    key = generate_private_key()
    pub = public_hex(key)
    body = {"outpoint": "c" * 64 + ":0", "device_pubkey": pub,
            "ipayntity": ipayntity_for(pub), "mode": "instant", "delay_blocks": 5}
    pid = e.apply_event(sign_event("enroll", body, key))["policy_id"]
    assert e.observe(pid, "d" * 64)["state"] == "HARDWARE_PROOF_MISSING"
    e.apply_event(sign_event("authorize", {"policy_id": pid, "txid": "d" * 64}, key))
    assert e.get_status(pid, "d" * 64)["state"] == "AUTHORIZED_OVERLAY"
    with pytest.raises(BPError, match="Veto not available"):
        e.apply_event(sign_event("veto", {"policy_id": pid, "txid": "d" * 64}, key))
    e.close()


def test_conflicting_ipayntity_binding_rejected_locally(setup_engine):
    e, _, pid, body = setup_engine
    other = generate_private_key()
    new = dict(body, device_pubkey=public_hex(other), ipayntity=ipayntity_for(public_hex(other)))
    with pytest.raises(BPError, match="Conflicting local registration"):
        e.apply_event(sign_event("enroll", new, other))


def test_registration_must_match_ipayntity_and_signer(setup_engine):
    e, key, _, body = setup_engine
    new = dict(body, outpoint="d" * 64 + ":4", ipayntity="a" * 64)
    with pytest.raises(BPError, match="ipayntity does not match"):
        e.apply_event(sign_event("enroll", new, key))
