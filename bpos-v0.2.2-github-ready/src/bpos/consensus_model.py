"""Deterministic *hypothetical* bpOS protected-output transition model.

NO Bitcoin transaction parsing, scripts, UTXO commitment, proof verification,
soft-fork deployment, or block-validation integration exists in this module.
This pure model provides testable ordering semantics for a future specification.
Callers must NOT treat the boolean proof inputs as actual cryptographic checks.
"""
from dataclasses import dataclass, replace


class TransitionError(ValueError):
    pass


@dataclass(frozen=True)
class ProtectedOutput:
    mode: str
    delay_blocks: int
    phase: str = "LOCKED"
    pending_txid: str | None = None
    initiated_height: int | None = None

    def __post_init__(self):
        if self.mode not in ("instant", "veto_window"):
            raise TransitionError("Unknown mode")
        if type(self.delay_blocks) is not int or not 1 <= self.delay_blocks <= 2016:
            raise TransitionError("Invalid delay")


def transition(state: ProtectedOutput, action: str, height: int, *, txid=None,
               bitcoin_signature_ok=False, device_proof_ok=False) -> ProtectedOutput:
    """Apply an ordered event in a hypothetical chain's block-height context.

    No wall clocks or gossip receipt order influence the result.  Finalized
    outputs leave the old owner's veto authority entirely.  In an actual chain,
    these proof booleans must be replaced by consensus-verifiable witnesses.
    """
    if type(height) is not int or height < 0:
        raise TransitionError("Invalid height")
    if action == "transfer_instant" and state.phase == "LOCKED" and state.mode == "instant":
        if not (bitcoin_signature_ok and device_proof_ok):
            raise TransitionError("Both Bitcoin and device authorization are required")
        if not isinstance(txid, str) or len(txid) != 64:
            raise TransitionError("Missing txid")
        return replace(state, phase="FINALIZED", pending_txid=txid)
    if action == "initiate" and state.phase == "LOCKED" and state.mode == "veto_window":
        if not bitcoin_signature_ok:
            raise TransitionError("Bitcoin signature is required")
        if not isinstance(txid, str) or len(txid) != 64:
            raise TransitionError("Missing txid")
        return replace(state, phase="PENDING", initiated_height=height, pending_txid=txid)
    if state.phase == "PENDING" and state.initiated_height is not None:
        if height < state.initiated_height:
            raise TransitionError("Cannot transition backward in chain height")
        maturity = state.initiated_height + state.delay_blocks
        if action == "veto" and height < maturity:
            if not device_proof_ok:
                raise TransitionError("Device authorization is required to veto")
            return replace(state, phase="CANCELLED")
        if action == "settle" and height >= maturity:
            return replace(state, phase="FINALIZED")
        if action == "accelerate" and bitcoin_signature_ok and device_proof_ok:
            return replace(state, phase="FINALIZED")
    raise TransitionError("Illegal transition or deadline")
