"""Software-key device emulation; no on-chain safety claims."""
import json
from .crypto import generate_private_key, public_hex, sign_event
from .engine import Engine
from .model import ipayntity_for


def run_demo():
    device = generate_private_key()
    key = public_hex(device)
    engine = Engine()
    policy = {"outpoint": "a" * 64 + ":0", "device_pubkey": key,
              "ipayntity": ipayntity_for(key), "mode": "veto_window", "delay_blocks": 6}
    policy_id = engine.apply_event(sign_event("enroll", policy, device))["policy_id"]
    engine.set_height(100)
    txid = "b" * 64
    print("ENROLLED", policy_id, "IPAYNTITY", policy["ipayntity"])
    print("OBSERVED", json.dumps(engine.observe(policy_id, txid), sort_keys=True))
    engine.apply_event(sign_event("veto", {"policy_id": policy_id, "txid": txid}, device))
    print("AFTER OWNER VETO", json.dumps(engine.get_status(policy_id, txid), sort_keys=True))
    print("NOTE: signed owner veto is advisory only; Bitcoin has not changed.")
    engine.close()
