"""Prototype CLI: enroll device identity, authorize or veto watched transactions."""
import argparse
import asyncio
import json
from pathlib import Path
import httpx
from .crypto import generate_private_key, private_key_from_hex, public_hex, sign_event, write_private_key
from .demo import run_demo
from .model import ipayntity_for


def main():
    parser = argparse.ArgumentParser(prog="bpos", description="bpOS experimental miner-side overlay")
    sub = parser.add_subparsers(dest="command", required=True)
    key = sub.add_parser("keygen", help="Create SOFTWARE-ONLY development identity")
    key.add_argument("--out", required=True)
    sub.add_parser("demo", help="Local owner-veto demonstration")
    sub.add_parser("demo-network", help="Two real HTTP peers: signed gossip to miner review (synthetic Core)")
    sub.add_parser("demo-internet", help="Wallet + internet endpoint proof relayed to miner-facing peers")
    enroll = sub.add_parser("enroll", help="Register an outpoint (no Bitcoin ownership proof)")
    enroll.add_argument("--key", required=True)
    enroll.add_argument("--outpoint", required=True)
    enroll.add_argument("--mode", choices=["instant", "veto_window"], default="veto_window")
    enroll.add_argument("--delay-blocks", type=int, default=6)
    enroll.add_argument("--api", default="http://127.0.0.1:8080")
    decision = sub.add_parser("decision", help="Sign authorize/veto as registered ipayntity")
    decision.add_argument("--key", required=True)
    decision.add_argument("--kind", choices=["authorize", "veto"], required=True)
    decision.add_argument("--policy-id", required=True)
    decision.add_argument("--txid", required=True)
    decision.add_argument("--api", default="http://127.0.0.1:8080")
    args = parser.parse_args()
    if args.command == "keygen":
        private = generate_private_key()
        write_private_key(args.out, private)
        print(json.dumps({"key_file": args.out, "public_key": public_hex(private),
                          "ipayntity": ipayntity_for(public_hex(private))}, indent=2))
    elif args.command == "demo":
        run_demo()
    elif args.command == "demo-network":
        from .network_demo import run_network_demo
        print(json.dumps(asyncio.run(run_network_demo()), indent=2))
    elif args.command == "demo-internet":
        from .internet_demo import run_internet_demo
        print(json.dumps(asyncio.run(run_internet_demo()), indent=2))
    else:
        private = private_key_from_hex(Path(args.key).read_text(encoding="ascii").strip())
        if args.command == "enroll":
            pub = public_hex(private)
            body = {"outpoint": args.outpoint, "device_pubkey": pub,
                    "ipayntity": ipayntity_for(pub), "delay_blocks": args.delay_blocks, "mode": args.mode}
            event = sign_event("enroll", body, private)
        else:
            event = sign_event(args.kind, {"policy_id": args.policy_id, "txid": args.txid}, private)
        resp = httpx.post(args.api.rstrip("/") + "/v1/events", json={"event": event}, timeout=10)
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))


if __name__ == "__main__":
    main()
