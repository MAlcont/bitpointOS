import pytest
from bpos.crypto import generate_private_key, public_hex, sign_event
from bpos.engine import Engine
from bpos.model import ipayntity_for


@pytest.fixture
def setup_engine():
    e = Engine()
    device = generate_private_key()
    pub = public_hex(device)
    body = {"outpoint": "a" * 64 + ":1", "device_pubkey": pub,
            "ipayntity": ipayntity_for(pub), "mode": "veto_window", "delay_blocks": 6}
    pid = e.apply_event(sign_event("enroll", body, device))["policy_id"]
    e.set_height(100)
    e.observe(pid, "b" * 64)
    yield e, device, pid, body
    e.close()
