# bpOS Internet Proof v1 — minimal architectural PoC

This is the **primary** v0.2.2 experiment. It does **not** depend on vetoes, cancellation,
additional guardians, bridges, ZK proofs, special ASIC chips or new Bitcoin consensus rules.

## Premise and boundary

Bitcoin peers and mining infrastructure use internet connectivity to receive
transactions and exchange blocks/jobs. This creates a plausible **optional**
coordination surface for additional wallet safety signals, shared by Bitcoin
miners irrespective of ASIC chip manufacturer. It does **not** imply that
Bitcoin Core trusts the **identity** of IP addresses when validating coins.

An IP address is routing information, not a wallet credential. NAT, dynamic
allocation, BGP interference and endpoint compromise rule out treating one
as a permanent authenticated owner ID. Likewise, TLS certificates generally
bind keys to named entities according to an issuer's validation process;
that alone does not prove Bitcoin signing authority. We use cryptographic
challenges to make the network claim measurable instead of assuming it.

## One executable claim

```text
  Bitcoin-compatible wallet software key W (secp256k1)
                        +
          ipayntity device key H (Ed25519)
                        |
  jointly sign  {W.pub, H.pub, endpoint IP:port, nonce, expiry}
                        |
              bpOS internet peer A
              validates BOTH signatures
                        |
    sends a random challenge to endpoint IP:port
    endpoint H signs the challenge + specific proof ID
                        |
            local peer A accepts proof
                        |
                 TCP/IP gossip
                        |
              independent peer B
       verifies signatures + NEW network challenge
                        |
          miner-facing read-only inspector
           can query the accepted binding
                        |
        (future) pool/Stratum/Bitcoin Core
                     -> ASICs
```

Each node checks the signed identity binding *and independently challenges the
endpoint*. Receiving a record from a trusted peer is not sufficient by itself.

### Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
bpos demo-internet
pytest -q
```

No Bitcoin wallet, internet-facing server, ASIC, or existing funds needed. The
demo starts **three localhost TCP HTTP servers**: identity endpoint and two
independent bpOS peers with separate SQLite registries. The endpoint is proof
of a reachable local IP/port, not proof that the public internet assigned a
permanent IP to a unique wallet or hardware asset.

### Result and interpretation

The demo requires that:

1. a secp256k1 wallet key signs the same identity-binding statement as the
   simulated hardware's Ed25519 key;
2. peer A challenges the endpoint via HTTP and verifies the H signature;
3. peer B receives the signed binding through gossip and independently
   challenges the endpoint with a different unpredictable nonce;
4. a tampered binding is rejected;
5. peer B's miner-facing read-only endpoint observes the binding.

`/v1/internet-proofs` is the new receipt endpoint. The miner-facing
`/v1/mining/internet-proof-review/{wallet_pubkey}` returns an explicit
advisory status. Both endpoints are experimental and do not issue Stratum jobs.

### Explicit things not proven

| Property | Demonstrated? |
| --- | --- |
| A real TCP/IP endpoint can be jointly bound to W and H | Yes, localhost PoC |
| Independent nodes verify proofs, not merely trust gossip | Yes |
| Bitcoin signing *key* control | Yes, raw ECDSA/secp256k1 domain-separated proof |
| Standards-compatible BIP 322 message signing | **No**, future adapter |
| Control of real Bitcoin UTXOs / script satisfaction | **No** |
| Deterministic global IP assignment or uniqueness | **No** |
| X.509/CA certificate identity assurance | **No** |
| H is truly held in tamper-resistant hardware | **No** |
| On-chain enforcement, protected spending or veto | **No** |
| Stratum V1/V2 mining-job control | **No** |

These distinctions are the protocol's initial research questions, not hidden
assumptions. The original veto simulator remains as a **secondary research
module**, not the architectural foundation.

## Internet-facing version (next discussion, not implemented)

The endpoint and device proof format could be adapted to verified HTTPS or
other authenticated transports and actual hardware credentials. For a live
Bitcoin address or UTXO binding, use a standards-compatible BIP 322 signature
or a consensus-valid script/transaction proof, together with independent UTXO
state checks where applicable. These would *strengthen* the proof but do not
follow merely from availability of a DNS name, IP address, or TLS certificate.

The binding and endpoint challenge must remain short-lived, scoped and
verifiable without trusting peers' conclusions. Independent miners are never
obligated to honor bpOS unless an actual consensus or explicit incentive
mechanism provides such rules.

## Technical prior art

- [BIP 322: Generic Signed Message Format](https://github.com/bitcoin/bips/blob/master/bip-0322.mediawiki)
- [BIP 324: v2 P2P Transport](https://github.com/bitcoin/bips/blob/master/bip-0324.mediawiki)
- [Stratum V2: Job Declaration](https://stratumprotocol.org/specification/06-job-declaration-protocol/)
