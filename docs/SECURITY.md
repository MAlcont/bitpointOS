# Security scope, intentionally bounded

The *design exploration* takes hardware device identity as a secure primitive.
Hardware compromise and supply-chain security are outside this iteration's
threat model, by design. This does **not** make the existing code hardware-backed:
its development identity is a normal software Ed25519 key with no attestation.

This repository is not safe for real funds. It does not implement Bitcoin
signature checks, on-chain ownership proof, consensus upgrades, fee control,
a Bitcoin wallet, withdrawals or real veto enforcement.

The overlay accepts unauthenticated inbound HTTP POST requests containing signed
events; local cryptographic validation prevents fake device signatures but does
not prevent DoS, impersonation of output ownership, network partition,
conflicting enrollments or mempool observation races. It has no durable
late-join synchronization, chain reorg tracking, rate limiting, HTTPS
termination, peer ACL enforcement, anti-equivocation, or real audit.

The miners' template inspector must not be treated as validation authority.
Miner agreement on a local policy is not Bitcoin consensus, and missing a
transaction from one local template does not make it invalid globally.

Use development keys, localhost-only test networks and Bitcoin regtest. Do
not put production private keys in the CLI, sample environment variables or
logs. An owner veto must have a deterministic, chain-ordered definition before
any deployment claims are made.
