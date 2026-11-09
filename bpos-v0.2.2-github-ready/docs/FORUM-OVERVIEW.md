# bpOS v0.2.2 alpha — reviewer brief

## One-sentence proposal

Explore a **voluntary miner/node-facing coordination service** that verifies a cryptographic association between a Bitcoin-compatible signing key, a separate device credential (`ipayntity`), and an internet-reachable endpoint, using the mining infrastructure shared across otherwise heterogeneous ASIC fleets.

## What you can run today

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
bpos demo-internet
pytest -q
```

The demo creates a disposable secp256k1 wallet-signing key and a separate software Ed25519 device key. Both sign one expiring statement that names a localhost endpoint. Two independent bpOS peers verify that statement and each challenge the endpoint over actual local TCP/IP HTTP. The second peer obtains the claim through signed HTTP gossip and makes a **read-only** verification result accessible to a miner-facing query. Tampering with the claim fails. The older `bpos demo-network` and `bpos demo` examples explore advisory owner signals separately.

## Proposed long-term interface

```text
wallet credentials + separate hardware-origin credential (future)
                          |
             signed, short-lived association
                          |
                  bpOS internet peers
                          |
               miner / pool / node control plane
                          |
              Stratum / template coordinators
                          |
                  multiple ASIC vendors
```

Bitcoin consensus is **not** changed by the PoC. Its core feasibility hypothesis is that a shared *mining control plane*, rather than universal ASIC firmware, can be a useful optional integration surface. Stratum V2 and Bitcoin Core template interfaces are promising integration candidates but are not presently wired to bpOS.

## What has been demonstrated — and what has not

- **Demonstrated:** key possession; joint signed binding; short-lived claim; independent fresh challenges over loopback TCP/IP; peer-to-peer relay; read-only miner-visible query; negative tests.
- **Not demonstrated:** public IPv4/IPv6 reachability, X.509 certificate verification, Bitcoin address/UTXO or script ownership, hardware custody or anti-relay attestation, miner job construction, valid on-chain shielding, consensus enforcement, or a fork.
- **Importantly:** a reachable IP address is not a globally unique or durable proof of a wallet, and cryptographic response forwarding does not establish the physical location of the device key. Internet routing is a communications assumption; Bitcoin transaction validity does not trust IP identity.

## Future questions for Bitcoin reviewers

1. Is the pool/proxy/job coordinator the right ASIC-neutral boundary for an optional wallet-identity observation service? Under which decentralization and adoption assumptions?
2. What *Bitcoin-script/UTXO-aware* proof should bind W to an output or address? BIP 322 is relevant prior art; a raw secp256k1 ECDSA statement is not equivalent.
3. Could hardware-origin credential attestations and endpoint certificates be useful for *off-chain monitoring* without inserting a certificate authority or IP allocation into Bitcoin consensus?
4. Which useful protection properties can be provided as an optional external service; which would require opt-in on-chain spending conditions, a sidechain trust model, or a consensus change?
5. Which attack cases matter first: key compromise, remote signing/relay, endpoint churn, censoring/miner nonparticipation, contradictory enrollment, and gossip partitions?

The cancellation/veto prototype is **secondary**. Cross-chain bridges, complex financial contracts, zero-knowledge systems, and additional guardian models are intentionally excluded from the initial protocol scope. Applications are mapped in [`APPLICATIONS.md`](APPLICATIONS.md), while mining integration is discussed in [`MINING-SURFACE.md`](MINING-SURFACE.md).

**Research-alpha claim:** this repository tests an internet credential-to-wallet-key proof *delivered to a miner-facing API*. It is neither a secure Bitcoin wallet nor a proof of feasible on-chain enforcement; those are further design and validation tasks.
