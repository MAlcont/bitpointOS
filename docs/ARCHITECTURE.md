# bpOS v0.2.2 architecture — internet identity first

**Primary system:** a wallet-compatible secp256k1 signing key (`W`) and a
networked ipayntity credential (`H`) jointly sign one bounded statement
`{W, H, IP:port, nonce, expires}`. Any participating bpOS node can verify the
signatures and separately challenge the endpoint. The signature and challenge
are the evidence; neither internet routing nor a CA is presumed to be Bitcoin
consensus authority.

```text
W (wallet signing key) + H (internet-linked device key)
                      |
           jointly signed binding
                      |
         bpOS peer A --- signed gossip ---> bpOS peer B
             |                                  |
       live challenge                       live challenge
             |                                  |
         H endpoint <----------------------------+
                                                |
                                   shared mining-facing inspector
                                                |
                                       Core / Stratum (future)
                                                |
                                        any ASIC manufacturer
```

The shipped `bpos demo-internet` exercises the entire path through peer B's
read-only proof interface with **actual local TCP/IP**. It does not connect to
an ASIC, inspect real UTXOs or change Core's consensus. See
[Internet Proof](INTERNET-PROOF.md) for the exact proof and its limits.

## Earlier modules — secondary to the binding experiment


```
         Bitcoin P2P network and independent validating nodes
                              |
                     Bitcoin Core node
                    /                \
       gettxspendingprevout       getblocktemplate
                 |                     |
            UTXO watcher          Miner inspector
                  \                    /
                     bpOS overlay daemon
                      |              |
                ipayntity      signed event store
                      |              |
                      +------ HTTP gossip mesh
                              |
                   dedicated retail / miner
                   identity credentials (future)
```

The deployed code uses software Ed25519 keys as a *stand-in* for hardware-origin
identity. `ipayntity` is the domain-separated SHA-256 digest of a public device
key; it is NOT an IP address, a device serial number or manufacturer attestation.

A signed enrollment names an outpoint, device key, identity hash, settlement
mode and block delay. It does NOT prove control of that Bitcoin UTXO. Conflicting
registrations are locally rejected without solving multi-node ordering;
production registration must be anchored on-chain and ownership-proven.

The API persists verified signed enrollment and one-device authorize/veto
statements in SQLite. The watcher observes mempool spending transactions in a
configured Core instance. The miner inspector decodes candidate block-template
transactions and identifies spends of protected outpoints. Both are read-only.

Signed-message gossip is HTTP/JSON, not a P2P consensus algorithm. Real peer
transport needs authenticated/encrypted connections, hardening, snapshots,
conflict resolution, and rate limits. Local observation heights are NOT a valid
consensus clock. The `consensus_model.py` module provides a deterministic,
chain-height-based hypothetical alternative but runs nowhere in Bitcoin Core.

See [Mining surface](MINING-SURFACE.md), [Applications](APPLICATIONS.md),
[Consensus proposal](CONSENSUS-PROPOSAL.md), [Security](SECURITY.md).
