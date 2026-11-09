# Demonstration 1 — Signed internet gossip reaching the miner interface

**Alpha v0.2.1.** The aim is to demonstrate one small end-to-end claim:

> bpOS can use a conventional TCP/IP overlay to propagate an owner's signed
> shield instruction between independent nodes, where it becomes visible to a
> miner-facing Bitcoin template inspector without changing ASIC firmware.

This is a demonstration of an **operational path**, not a Bitcoin security
proof, an ASIC operating system, a deployed soft fork, or a working sidechain.

## Run in one command

Python 3.10+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
bpos demo-network
pytest -q
```

The first command starts two bpOS HTTP servers on OS-assigned localhost ports,
then shuts them down when the experiment finishes. No external Bitcoin node,
ASIC hardware, keys, pools, or internet service is needed. Do not supply real
private keys or use funds with this demonstration.

The output includes:

```json
{
  "result": "PASS: signed owner veto reached independent miner-facing peer",
  "network": {"transport": "TCP loopback HTTP", "independent_peers": 2,
              "gossip_signature_verified": true, "forged_event_rejected": true},
  "shield": {"before": "VETO_WINDOW_OPEN", "after": "OWNER_VETO"},
  "mining_adapter": {"candidate_spend_flagged": true,
                     "state": "OWNER_VETO", "core_template": "synthetic RPC stub",
                     "template_modified": false},
  "limits": {"hardware_attestation": false, "bitcoin_ownership_proven": false,
             "bitcoin_consensus_enforced": false,
             "bitcoin_funds_frozen_or_reversed": false,
             "stratum_jobs_issued": false}
}
```

The command also prints a random `ipayntity` value. Its exact value changes
on each run.

## What this execution actually exercises

1. A disposable Ed25519 software identity signs the registration of a **fake**
   Bitcoin outpoint on **peer A**.
2. Peer A relays the intact signed message over HTTP/TCP to **peer B**.
   Peer B independently validates and stores the registration.
3. Both peers receive an **artificial mempool observation** at simulated block
   height 100; this models what independent Bitcoin Core watchers would see.
4. An altered signed veto sent to peer B is rejected as invalid (HTTP 422).
5. The legitimate owner signs a veto and sends it **only to peer A**. Peer A
   relays it; peer B verifies it and moves its *local advisory status* from
   `VETO_WINDOW_OPEN` to `OWNER_VETO`.
6. Peer B's miner-facing review function evaluates a **synthetic Bitcoin Core**
   `getblocktemplate` / `decoderawtransaction` response and flags the candidate
   spend as `OWNER_VETO`.

The two bpOS instances have separate in-memory SQLite stores. There is real
local TCP communication between them. The Core RPC result, observed UTXO,
spending transaction, and block height are deliberately synthetic.

### What is NOT demonstrated

- No proof of Bitcoin UTXO ownership on enrollment; anyone can register an
  arbitrary unclaimed outpoint in this research overlay.
- No proof that any signature originates inside trusted hardware. The demo
  models a device with an ordinary software Ed25519 key.
- No ASIC operating system or universal ASIC hardware identity. The shared
  surface is the **node/pool/template-coordinator interface** above ASICs.
- No real Stratum proxy, mining job declaration, modified block template,
  withdrawal rejection, veto transaction, or consensus-enforced freeze.
- No global agreement about conflicting identity registrations, nor
  deterministic gossip ordering. The two-node demonstration uses a single
  non-conflicting registration and consistent simulated local heights.
- No durable security guarantee when a device goes offline, a pool ignores
  bpOS, an attacker controls the network, or independently validating Bitcoin
  nodes disagree with the overlay.

## Credible feasibility claim

The modest proposition **is shown**: a signed event from an owner's device
can be carried over TCP/IP and acted upon as an *advisory signal* at a
vendor-neutral Bitcoin mining control point. No chip redesign is needed to
observe it there.

The more valuable proposition **is still a hypothesis**: make that shield
binding and an actionable recovery path part of a Bitcoin-verifiable protected
output, or an expressly opted-in sidechain with its own security model. That
requires an explicit locking/settlement design. Miner cooperation alone
cannot change what independent Bitcoin full nodes accept as valid.

## One logical next increment

Take peer B's miner-facing `OWNER_VETO` verdict and use it to build a
**dry-run opt-in transaction selection report** for a candidate block
(including descendant dependencies). Test it with synthetic block templates
before attempting Stratum V2 job-declaration integration. This would
connect internet shielding to a potential miner action while remaining
non-consensus and intentionally reversible in development.
