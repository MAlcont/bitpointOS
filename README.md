<big><big><strong>bpOS — Bitpoint OS</strong></big></big> <sub><i>if you're gonna use it, you're gonna leverage it</i></sub>

**v0.2.2 alpha · An internet-linked Bitcoin wallet identity proof at the shared mining interface.**

> **One-line thesis:** Bitcoin nodes, pools and heterogeneous ASIC fleets already
> communicate through common internet-connected mining infrastructure. bpOS
> explores using that shared surface to distribute **cryptographically verified,
> wallet-linked internet identity signals** as an additional protective layer.
> The transport network does not itself establish Bitcoin consensus or ownership.

## Primary proof of concept — internet identity, not cancellation

The simplest falsifiable demonstration is now `bpos demo-internet`:

```bash
pip install -e '.[dev]'
bpos demo-internet
pytest -q
```

It generates two disposable credentials — a **Bitcoin-compatible secp256k1
wallet key** and an `ipayntity` **Ed25519 device key** — and jointly signs
an identity statement containing a **localhost IP:port**, nonce and expiry.
Two independent bpOS nodes on real TCP/IP then **each perform a new, signed
challenge to that endpoint**. The second peer learns the identity via signed
gossip; its miner-facing adapter can review the verified claim. A forged
association is rejected. No Bitcoin Core node or ASIC is needed for this
minimum architectural experiment.

```text
wallet key W + internet device H  --joint signatures-->  bpOS peer A
                 |                                     fresh challenge |
           endpoint IP:port <------------------------------------------+
                 ^
                 | new independent challenge
           bpOS peer B  <--signed TCP/IP gossip--  peer A
                 |
          miner-facing proof inspector
                 |
       (future) pool / Stratum / ASIC ecosystem
```

**[Internet-proof protocol, limits and reproducibility](docs/INTERNET-PROOF.md).**
For a quick review before reading the code, see **[forum / reviewer brief](docs/FORUM-OVERVIEW.md)**.

**Precise claims:** this proves control of cryptographic keys and a responsive
network endpoint at the time of verification. **An IP address is not, by
itself, a deterministic wallet identity; a TLS certificate is not a Bitcoin
ownership proof.** Bitcoin Core uses the internet for communication, but
Bitcoin consensus validates signatures and rules rather than trusting IP
addresses. The PoC does not demonstrate Bitcoin funds or UTXOs, BIP 322,
public-internet reachability, hardware attestation or consensus enforcement.

The existing v0.2.1 signed-gossip, read-only miner-template inspector and
veto simulator remain in the repository as **optional subsequent research**.
The first problem is the verifiable internet-to-wallet binding; reversal or
cancellation are not its premise.

---

## Potential uses (require later Bitcoin protocol work)

| Market | bpOS opportunity | Depends on later protocol work |
| --- | --- | --- |
| Institutional BTC custody | Move from key-only custody to continuously defended, identity-bound reserves | enforceable protected-output rules |
| Retail hardware | Tiny network-connected bpOS device independently guards a Bitcoin spending policy | hardware credential + protected UTXO deployment |
| Mining infrastructure | Vendor-agnostic miner/pool protection observations and potential monitoring/relay fees | participating pools and credible incentives |
| BTC ↔ ETH and bridges | Reusable physical-identity authorization semantics across chains | genuine peg, proofs, settlement and exit guarantees |
| On-chain exchanges / market making | Protected liquidity policies and transaction staging for new exchange/contract designs | contracts, collateral verification and settlement |
| ZK and private identity | Potential proof of membership in an authorized hardware set | an actual ZK verifier and protocol integration |
| Evolving hashrate ecosystem | No single ASIC manufacturer's firmware is a required gatekeeper | independent template-selection and deployment incentives |

**Read the complete [A–H applicability and limitations map](docs/APPLICATIONS.md).**
It addresses bridging, financial contracts, quantum assumptions, address space,
retail appliances and miner economics without representing any as complete.

## Where bpOS fits: the shared ASIC surface

```text
          Bitcoin consensus / P2P full nodes
                       |
                Bitcoin Core RPC
                       |
       bpOS internet identity, gossip and miner inspector
                       |
        Pools / Stratum proxies / job makers
                       |
        ASIC brands of different generations
```

**Yes, there is a common mining-facing control surface.** Different ASICs use
Bitcoin mining work and pools/proxies often distribute that work using Stratum
V1 or V2. Bitcoin Core exposes candidate-block templates via `getblocktemplate`.
Stratum V2 also defines Template Distribution and Job Declaration. **No, ASICs
share neither one mandated OS nor a hardware identity standard.** The most
credible vertical implementation runs at the full-node/pool/proxy coordinator;
ASICs keep hashing. See [mining surface analysis](docs/MINING-SURFACE.md).

## Additional v0.2 modules (secondary)

| Module | Actual implementation |
| --- | --- |
| `ipayntity` | Canonical digest of a device *public key* (development software-key stand-in) |
| Enrollment | Signed outpoint-to-identity overlay records; locally rejects conflicts |
| Owner messages | One registered device signs `authorize` or `veto`; **no guardian quorum** |
| Gossip | JSON/HTTP fanout of signed events, verified on each receiving node |
| Watcher | Bitcoin Core `gettxspendingprevout` mempool observations |
| Mining control surface | `getblocktemplate` + `decoderawtransaction` read-only protected-spend review |
| Mode A | `instant`: record identity authorization signals for a watched spend |
| Mode B | `veto_window`: simulate owner veto within an advisory block-height window |
| Deterministic reference | Pure, tested hypothetical protected-output transition rules |

**What it cannot do:** confirm ownership of a Bitcoin UTXO, prove a key is
inside hardware, mutate ASIC firmware, alter consensus validation, freeze or
reverse BTC, implement an ETH bridge, or guarantee global registry agreement.

## Secondary network demonstration (v0.2.1)

The retained **`bpos demo-network`** exercises the earlier alpha architecture in one
run: an ephemeral software identity registers a synthetic protected outpoint,
two independent bpOS nodes exchange authenticated events through **real TCP
loopback HTTP**, a forged message is rejected, and peer B's **miner-facing
adapter** flags the signed veto in a synthetic Bitcoin Core block template.
There is **no real Bitcoin enforcement or mining** in this demonstration.

```bash
pip install -e '.[dev]'
bpos demo-network
pytest -q
```

[Full demonstration, screenshots-ready expected output, boundaries, and next
increment](docs/DEMO-NETWORK.md). This is the **earlier gossip/veto**
demonstration, deliberately not a production-ready shield.

## Run it

Python 3.10+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
bpos demo-internet
pytest -q
```

`bpos demo` is the older, secondary local veto simulation. Its expected
demonstration: an outpoint is registered under an `ipayntity`, a
transaction is observed and one owner signature changes status to
`OWNER_VETO` with `on_chain_enforced: false`.

### Start a simulation HTTP daemon

```bash
BPOS_SIMULATE=1 BPOS_DB=dev.sqlite3 uvicorn bpos.api:app --host 127.0.0.1 --port 8080
```

In a second terminal:

```bash
bpos keygen --out device.key
bpos enroll --key device.key --outpoint aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:0 --mode veto_window --delay-blocks 6
# Copy the returned policy_id, then use:
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/v1/simulate/height -H 'Content-Type: application/json' -d '{"height":100}'
curl -X POST http://127.0.0.1:8080/v1/simulate/observe -H 'Content-Type: application/json' -d '{"policy_id":"POLICY_ID","txid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'
bpos decision --key device.key --kind veto --policy-id POLICY_ID --txid bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
```

The simulated `txid` and outpoint are dummy values. For real mempool
observation, connect a **separately managed Bitcoin Core node**, preferably on
regtest. No wallet private keys should be imported into bpOS.

### Bitcoin Core watcher and miner block-template review

```bash
export BPOS_BITCOIN_RPC_URL=http://127.0.0.1:18443
export BPOS_BITCOIN_RPC_USER=regtestuser
export BPOS_BITCOIN_RPC_PASSWORD=regtestpassword
export BPOS_DB=dev.sqlite3
uvicorn bpos.api:app --host 127.0.0.1 --port 8080
# From another terminal:
curl http://127.0.0.1:8080/v1/mining/template-review
```

The daemon watches enrolled outpoints with `gettxspendingprevout`; the miner
review endpoint inspects transactions in a Bitcoin Core `getblocktemplate`
response, marking matching inputs and their owner authorization state. The
response always declares `template_modified: false` and
`bitcoin_consensus_enforced: false`. It does **not** run Stratum V2 or choose
block transactions. See [mining design](docs/MINING-SURFACE.md).

## Research boundary: network availability is not Bitcoin consensus

TCP/IP distributes signed `ipayntity` messages, but nodes can receive them in
different orders. To create a genuine veto, Bitcoin/sidechain consensus must
have deterministic registration, on-chain verifiable hardware policy
commitments, authenticated veto authorization and a block-height-based
settlement transition. A new address string by itself does not enforce any of
these. The fork classification remains open until exact validity rules exist.

The initial reference state machine is in `src/bpos/consensus_model.py` and
specified in [consensus proposal](docs/CONSENSUS-PROPOSAL.md). It is not a
Bitcoin Core fork or consensus rule implementation.

## Project tree

```text
src/bpos/crypto.py           signed events + software-key development identity
src/bpos/internet_identity.py wallet-signature + network challenge proof
src/bpos/internet_demo.py    end-to-end joint wallet/internet key proof
src/bpos/model.py            ipayntity binding and policy validation
src/bpos/engine.py           SQLite owner-authorized overlay state
src/bpos/bitcoin_rpc.py      Bitcoin Core mempool watcher
src/bpos/miner.py            Bitcoin Core block-template inspector
src/bpos/consensus_model.py  pure proposed transaction state machine
src/bpos/network_demo.py     two independent HTTP peers + mock Core miner review
src/bpos/api.py              local gossip / observation HTTP API
src/bpos/cli.py              device emulation / enroll / decision
tests/                       deterministic unit and endpoint checks
docs/                        protocol, applications, ASIC surface, limitations
```

## Distribution note

The v0.1 prototype was previously supplied under MIT; that permission is not
retroactively revoked. This working tree builds on that code and retains the
LICENSE file. **If the product is to remain private until validation, host
this iteration in a private repository and obtain appropriate licensing and
contributor advice before external distribution.** Do not assume a private
GitHub repository changes rights already granted under MIT.

## References

- [Stratum V2 overview](https://stratumprotocol.org/specification/03-protocol-overview/)
- [Stratum V2 mining protocol](https://stratumprotocol.org/specification/05-mining-protocol/)
- [Stratum V2 Job Declaration](https://stratumprotocol.org/specification/06-job-declaration-protocol/)
- [Bitcoin Core `gettxspendingprevout`](https://bitcoincore.org/en/doc/32.0.0/rpc/blockchain/gettxspendingprevout/)
- [Bitcoin Core `getblocktemplate`](https://bitcoincore.org/en/doc/26.0.0/rpc/mining/getblocktemplate/)
