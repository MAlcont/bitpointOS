import pytest
from bpos.consensus_model import ProtectedOutput, TransitionError, transition


def test_ordered_state_is_deterministic():
    start = ProtectedOutput("veto_window", 6)
    observations = []
    for _ in range(2):
        pending = transition(start, "initiate", 100, bitcoin_signature_ok=True, txid="a" * 64)
        observations.append(transition(pending, "veto", 103, device_proof_ok=True))
    assert observations[0] == observations[1]
    assert observations[0].phase == "CANCELLED"
    with pytest.raises(TransitionError):
        transition(observations[0], "settle", 109)


def test_settlement_after_block_delay():
    s = transition(ProtectedOutput("veto_window", 6), "initiate", 100,
                   bitcoin_signature_ok=True, txid="b" * 64)
    with pytest.raises(TransitionError):
        transition(s, "settle", 105)
    assert transition(s, "settle", 106).phase == "FINALIZED"
    with pytest.raises(TransitionError):
        transition(s, "veto", 106, device_proof_ok=True)


def test_instant_mode_requires_two_independent_checks():
    s = ProtectedOutput("instant", 6)
    with pytest.raises(TransitionError):
        transition(s, "transfer_instant", 100, txid="a" * 64, bitcoin_signature_ok=True)
    done = transition(s, "transfer_instant", 100, txid="a" * 64,
                      bitcoin_signature_ok=True, device_proof_ok=True)
    assert done.phase == "FINALIZED"


def test_accelerate_delayed_with_both_proofs():
    s = transition(ProtectedOutput("veto_window", 6), "initiate", 100,
                   bitcoin_signature_ok=True, txid="a" * 64)
    assert transition(s, "accelerate", 101, bitcoin_signature_ok=True, device_proof_ok=True).phase == "FINALIZED"
