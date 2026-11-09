from fastapi.testclient import TestClient
from bpos.api import create_app
from bpos.crypto import generate_private_key, public_hex, sign_event
from bpos.model import ipayntity_for


def test_http_enroll_observe_owner_veto():
    owner = generate_private_key()
    pub = public_hex(owner)
    body = {"outpoint": "a" * 64 + ":0", "device_pubkey": pub,
            "ipayntity": ipayntity_for(pub), "mode": "veto_window", "delay_blocks": 6}
    with TestClient(create_app(simulate=True)) as client:
        assert client.get("/health").json()["consensus_enforced"] is False
        r = client.post("/v1/events", json={"event": sign_event("enroll", body, owner)})
        pid = r.json()["policy_id"]
        assert r.status_code == 200
        assert client.post("/v1/simulate/height", json={"height": 100}).status_code == 200
        assert client.post("/v1/simulate/observe", json={"policy_id": pid, "txid": "b" * 64}).status_code == 200
        ev = sign_event("veto", {"policy_id": pid, "txid": "b" * 64}, owner)
        assert client.post("/v1/events", json={"event": ev}).status_code == 200
        assert client.get(f"/v1/status/{pid}/{'b' * 64}").json()["state"] == "OWNER_VETO"


def test_simulator_api_absent_by_default():
    with TestClient(create_app(simulate=False)) as client:
        assert client.post("/v1/simulate/height", json={"height": 4}).status_code == 404
        assert client.get("/v1/mining/template-review").status_code == 404
