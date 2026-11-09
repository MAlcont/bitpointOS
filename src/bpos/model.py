"""Validation of bpOS research-only identity bindings (NOT Bitcoin ownership)."""
import re
from .crypto import digest

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def is_hex64(value):
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def parse_outpoint(value):
    if not isinstance(value, str) or ":" not in value:
        raise ValueError("Outpoint must be txid:vout")
    txid, vout = value.split(":", 1)
    if not is_hex64(txid) or not vout.isdecimal() or str(int(vout)) != vout or int(vout) > 4294967295:
        raise ValueError("Invalid outpoint")
    return {"txid": txid, "vout": int(vout)}


def ipayntity_for(device_pubkey):
    if not is_hex64(device_pubkey):
        raise ValueError("Invalid device public key")
    return digest({"namespace": "bpos:ipayntity:v1", "device_pubkey": device_pubkey})


def validate_policy(body, signer):
    expected = {"outpoint", "ipayntity", "device_pubkey", "delay_blocks", "mode"}
    if not isinstance(body, dict) or set(body) != expected:
        raise ValueError("Unexpected policy fields")
    parse_outpoint(body["outpoint"])
    if not is_hex64(body["device_pubkey"]) or body["device_pubkey"] != signer:
        raise ValueError("Enrollment must be signed by the enrolled device credential")
    if body["ipayntity"] != ipayntity_for(signer):
        raise ValueError("ipayntity does not match the device public key")
    if body["mode"] not in ("instant", "veto_window"):
        raise ValueError("Invalid protection mode")
    if type(body["delay_blocks"]) is not int or not 1 <= body["delay_blocks"] <= 2016:
        raise ValueError("Invalid block delay")
    return digest(body)
