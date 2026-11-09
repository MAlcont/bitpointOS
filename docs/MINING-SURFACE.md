# Mining interface compatibility: the ASIC-neutral surface

## Core fact

Different ASIC models **do not share a mandatory operating system**. The common
invariant is the Bitcoin block header and proof-of-work target. The work
allocation control plane normally sits outside the ASIC:

```text
Bitcoin P2P / independently validating full nodes
        |
Bitcoin Core (UTXO + mempool + getblocktemplate + RPC)
        |                    ^
        |                    | read-only bpOS watcher + template inspector
        v                    |
Pool / solo miner / Stratum V2 template provider --- bpOS daemon
        |
Stratum V1 or V2 pool/proxy/job-declaration system
        |
ASIC brands and generations (hash block-header work)
```

A bpOS daemon can attach once at a pool, mining-proxy, or full-node control
plane without flashing each ASIC. This *does* permit one vertical mining-facing
implementation, even across incompatible chips and firmware, but deployment
there does **not** force all miners to honor it.

## v0.2.2 identity inspection endpoint

`GET /v1/mining/internet-proof-review/{wallet_pubkey}` reads the verified
wallet/device/endpoint proof from the local registry. In the end-to-end demo,
peer B independently verified the IP endpoint after receiving proof through
peer A's gossip. This is **read-only mining-facing metadata**; no Stratum job
or Core template is changed, and no UTXO ownership is proved.

## Earlier template inspection endpoint

`GET /v1/mining/template-review` with configured Bitcoin Core RPC:

- Calls `getblocktemplate({"rules":["segwit"]})`.
- Calls `decoderawtransaction` on the candidate block transactions.
- Compares each transaction's inputs against locally enrolled outpoints.
- Returns `ipayntity` and overlay authorization/veto status for matched spends.
- Returns `template_modified: false`, `bitcoin_consensus_enforced: false`.

This is an observability adapter, not yet a Stratum V1/V2 service or template
filter. It can be independently tested with mock Bitcoin Core RPC.

The research implementation decodes transactions serially and limits templates
to 5000 transactions. It is not optimized for production block-template latency;
use batch/parallel decoding and direct transaction-input indexes later.

## Two upgrade paths

1. **Voluntary mining deployment:** signed gossip + template review +
   opt-in transaction-template policy at pools/job declarators; this creates
   miner economics and measurable participation but **cannot** implement veto
   against otherwise valid Bitcoin blocks.
2. **Consensus proposal:** enforce `ipayntity` policy in the validation of an
   opted-in protected output, with registration and veto commitments verifiable
   using chain data; Bitcoin Core forks on regtest first, followed by a clearly
   defined soft-fork or hard-fork proposal as appropriate.

A fork's category is determined by the set of blocks/transactions accepted by
old and new nodes, not by whether the application uses TCP/IP or sidechain-like
language. A new address encoding alone is insufficient.

## Specification sources

- https://stratumprotocol.org/specification/03-protocol-overview/
- https://stratumprotocol.org/specification/05-mining-protocol/
- https://stratumprotocol.org/specification/06-job-declaration-protocol/
- https://bitcoincore.org/en/doc/32.0.0/rpc/blockchain/gettxspendingprevout/
- https://bitcoincore.org/en/doc/26.0.0/rpc/mining/getblocktemplate/
