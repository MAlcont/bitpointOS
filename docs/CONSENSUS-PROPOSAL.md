# bpOS protected-output proposal (exploratory, not a BIP)

## Objective

Bind an opt-in output to an `ipayntity` representing a hardware-origin identity.
Bitcoin's conventional spending signature is the **spend proposal**; the new
identity has authority to grant immediate spending or veto before a predictable
chain-enforced window expires. No mandatory multisig guardians.

## Design components

1. **Register:** bind a specific UTXO's locking policy to identity commitment
   `H(domain || hardware credential policy)`. A consensus commitment and an
   actual proof of output ownership are needed. An overlay-only enrollment is
   not adequate to create property rights.
2. **Initiate:** a conventional signing key makes a withdrawal proposal. The
   protected coins remain inside a pending/unvault state until maturity.
3. **Veto:** an authorized `ipayntity` witness redirects/cancels the *pending*
   withdrawal before maturity. It must be ordered by consensus (e.g. included
   in a block), not validated by local gossip arrival time.
4. **Accelerate:** ordinary spending proof **plus** identity proof may settle
   immediately, if the chosen rules permit it.
5. **Settle:** after `delay_blocks`, a pending transaction may complete; the
   previous owner's veto cannot follow coins into the recipient's UTXOs.

The `src/bpos/consensus_model.py` function emulates the resulting state
machine using block heights, ordered actions, and boolean **placeholders** for
actual cryptographic witness verification. Its purpose is to make semantics
concrete and deterministic. It is not Bitcoin validation code.

## Network agreement boundary

TCP/IP gossip transports authenticated statements. Arbitrarily delayed peer
messages are **not** Bitcoin consensus inputs. Otherwise two miners/full nodes
with the same chain data could disagree about the legality of the same block.

Enrollment authority, ownership proof, and an actionable veto must therefore
be committed in a shared chain history or otherwise proven deterministically
under explicit consensus rules. On a sidechain, the sidechain itself must have
specified finality, security and Bitcoin peg assumptions. A sidechain is not
created by naming an overlay a sidechain.

## Fork classification

If the upgraded validity conditions only **restrict** previously valid spends,
compatible deployment might be a soft fork. If upgraded rules accept blocks or
transactions older rules reject, this is a hard fork. It cannot be determined
from a longer address or an additional gossip service. New output templates
must be evaluated under old-node interpretation. Miner adoption alone does not
upgrade independent validating full nodes.

## Open protocol questions

- Which witness/attestation primitive can a Bitcoin consensus engine verify?
- How to bind `ipayntity` to a Bitcoin output without arbitrary third-party
  enrollment or a privileged registry?
- How to make veto inclusion and fee payment live even against censorship?
- Is the veto transaction itself a recovery spend, and how does it pay fees?
- What prevents abusive initiation/veto timing and contradictory authorizations?
- How to limit privacy leakage from repeated physical-device identities?
- Which on-chain state proves a cross-chain pledge without introducing a peg custodian?
- How to model reorgs, replacement policies, and pending withdrawals?

The experiment explicitly treats secure hardware credential generation and
identity custody as assumed. That assumption is not a proof that TCP/IP,
manufacturer provenance or external attestations are trustworthy consensus
inputs.
