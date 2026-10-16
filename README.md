# QUASAR COIN — Educational Blockchain Prototype

## What this IS

A **real, working** minimal blockchain written in Python:

- **Real SHA-256 hashing** (Python `hashlib`) — the same algorithm Bitcoin uses
- **Real proof-of-work mining** — each block's nonce is brute-forced until the
  block hash starts with N leading zeros (adjustable difficulty, default 4,
  so a block mines in seconds on a laptop)
- **Blocks** contain: index, timestamp, transactions, previous hash, nonce, hash
- **Chain validation** — every block's hash, proof-of-work, and link to the
  previous block is verified
- **500,000,000,000 (500 billion) max supply**, hard-capped in code
- **Block reward: 3 phases** — 50,000 QSR/block x 6,000,000 blocks
  (~5.7 yrs), then 25,000 x 2,629,800 blocks (2.5 yrs), then
  12,500 x 2,629,800 blocks (2.5 yrs), then 0 forever (stop height
  11,259,600). Total mined exactly 398,617,500,000 QSR.
  See `supply.py` for the exact schedule. Old pre-Stage-2 chains are
  rejected on load — use a fresh data directory.

Run it and watch real mining happen:

Run it (Stage 2 testnet — see TESTNET_STEPS.txt):

```bash
cd ~/workspace/quasar-coin
set QUASAR_DATA_DIR=quasar-seed   # Windows cmd (Linux/Mac: export QUASAR_DATA_DIR=quasar-seed)
python quasar_cli.py new-address alice
python quasar_cli.py start-node --port 9333 --datadir quasar-seed --founder <YOUR-Q-ADDRESS>
# inside the node console: mine alice / balance alice / claim-founder 100 / validate
```
Wallet + datadir must match: the node looks for wallets INSIDE the
--datadir folder, so create the wallet with QUASAR_DATA_DIR set to the
same folder (see TESTNET_STEPS.txt).

Or try the local Stage 1 prototype (test challenges only, coins do NOT carry over):

```bash
python3 mining_prototype.py --mine --mode eco --blocks 2 --i-consent
```

## What this is NOT

- **NOT launched.** Stage 2 is a TESTNET (invite-only: seed node + `add-peer`), not a public launch. Production needs a security audit first.
- **Real P2P network (testnet).** Nodes connect over TCP port 9333, share blocks/transactions, and converge on the longest VALID chain (`p2p.py`).
- **Real wallets.** ECDSA secp256k1 keypairs, addresses starting with **Q** (`wallet.py`, `quasar_cli.py new-address`). Wallet files are plain JSON for learning — never reuse these keys for anything with real value.
- **NO value.** These coins cannot be bought, sold, or transferred. They are worth nothing.
- **NOT secure at production scale.** One laptop's hash power means anyone could
  rewrite the chain. Real blockchains are secured by thousands of independent miners.

## What a REAL launch would need

1. **Peer-to-peer network + nodes** — software that many independent computers run
   to share and agree on the chain (this is the actual hard part)
2. **Wallets** — key generation, addresses, signing (never store keys in plain text)
3. **Miner community** — real people running real hardware, securing the chain
4. **Security audit** — professional review before anyone trusts it with value
5. **Legal / securities review** — a lawyer must assess whether the coin is a
   security in each country (e.g. OSC/CSA in Canada) BEFORE any public sale or promise
6. **Exchanges / liquidity** — a market where the coin can actually trade

Until all of that exists, this is a **learning tool** — which is exactly what it is for.

---

## Quasar Core (Bitcoin-like) — mine from your laptop

A **full single-node blockchain**, like Bitcoin in miniature:

| File | What it does |
|---|---|
| `wallet.py` | Real ECDSA secp256k1 keypairs (same curve as Bitcoin), Bitcoin-style Base58Check addresses starting with **Q** |
| `transactions.py` | Signed UTXO transactions (inputs/outputs, signature verification), coinbase mining rewards |
| `node.py` | Blockchain + mempool + UTXO set, SHA-256 proof-of-work, genesis block, chain persistence, full validation |
| `quasar_cli.py` | Command-line interface: wallets, mining, sending, balances |

**Tokenomics (mining prototype):** 500B max supply; mining in
3 phases (50,000 -> 25,000 -> 12,500 QSR/block, then stop;
398,617,500,000 QSR total); 100B founder allocation with 1-week
vesting. See `supply.py`.
Amounts are integers ("quarks": 1 QSR = 100,000,000 quarks — like satoshis).

### Laptop setup (2 minutes)

```bash
cd ~/workspace/quasar-coin
python3 -m venv qcore-venv
qcore-venv/bin/pip install ecdsa
```

### Usage

```bash
PY=./qcore-venv/bin/python

$PY quasar_cli.py new-address alice      # create a wallet (address starts with Q)
$PY quasar_cli.py new-address bob
$PY quasar_cli.py mine alice             # mine one block -> 50,000 QSR to alice (phase 1 reward)
$PY quasar_cli.py balance alice          # check balance
$PY quasar_cli.py send alice <bob-address> 10   # signed tx -> mempool
$PY quasar_cli.py mine bob               # confirm the pending tx in a block
$PY quasar_cli.py mempool                # pending transactions
$PY quasar_cli.py info                   # height, difficulty, mined vs remaining
$PY quasar_cli.py validate               # full chain audit (hashes, PoW, signatures, double-spends)
```

Difficulty defaults to 3 leading zeros (a laptop mines a block in well under a
second). Raise it for a workout: `quasar_cli.py mine alice --difficulty 4`.

Your chain is saved to `chain_data.json` — close the terminal, come back
tomorrow, mining continues where you left off. Wallets live in `wallets/`.

### What this is NOT

- **NOT a public network.** One node, one computer, no peers.
- **NOT launched.** These coins have **no monetary value** and cannot be
  traded, sold, or sent to anyone outside this folder.
- **Demo keys.** Wallet files are plain JSON for learning. Never reuse these
  keys for anything with real value.

---

## P2P Public Network (v1) — `p2p.py`

Quasar Core can now run as a **public network**: multiple nodes connect over
TCP, gossip transactions, broadcast mined blocks, and converge on the
**longest VALID chain** (every received block is fully re-validated: hash,
proof-of-work, signatures, double-spends).

### Run two nodes on one machine

```bash
$PY quasar_cli.py start-node --port 9333 --datadir ~/.quasar-node1
# in a second terminal:
$PY quasar_cli.py start-node --port 9334 --datadir ~/.quasar-node2 \
    --seed 127.0.0.1:9333
```

Inside the `start-node` console:

```
quasar-node:9333> mine alice        # mine + broadcast the block to peers
quasar-node:9333> send alice <addr> 10
quasar-node:9333> peers             # list connected peers
quasar-node:9333> add-peer 192.168.1.50:9333
quasar-node:9333> quit
```

### How sync works

- On connect, nodes exchange `hello` (version, height, tip, genesis hash).
  Different genesis = different network: the connection is dropped.
- A node behind its peer downloads missing blocks (`getblocks`), validates
  each one, and appends them.
- On a fork, the node walks back to the common ancestor, downloads the
  peer's branch, fully re-validates it, and adopts it **only if it is longer
  AND valid**. The loser's fork blocks become orphans (their rewards vanish
  — exactly like Bitcoin reorgs).

`seeds.json` lists seed nodes (`127.0.0.1:9333` = your own first node).

### v1 limitations — read before exposing a node

- **No encryption, no authentication.** Anyone can connect. Keep nodes on
  localhost or a private VPN between trusted machines for now.
- **No Sybil protection.** Fake nodes can lie about their height, but they
  **cannot** forge a longer *valid* chain — invalid blocks are rejected.
- Nodes you want to stay in sync should stay **online**; there is no
  always-on backbone yet.
- Fork choice is longest-valid-chain; exact ties wait for the next block.

Educational network only — coins have no monetary value.

---

# Mining Prototype (Stage 1) — LOCAL ONLY

**Prototype / test coins only. No monetary value. No guaranteed earnings.**
Performance figures are design targets, not benchmarks.

Stage 1 is a **local** mining prototype: it solves test challenges on one
machine, with no network. Launch order: **Stage 1 local prototype (this) →
public testnet → security audit → production only after audit.**

## Run it

```bash
cd ~/workspace/quasar-coin
python3 mining_prototype.py --benchmark
python3 mining_prototype.py --mine --mode eco --blocks 2 --i-consent
# or via the main CLI (additive commands; existing commands untouched):
python3 quasar_cli.py mine-prototype --mode balanced --blocks 2 --i-consent
python3 quasar_cli.py mine-benchmark
```

Files: `supply.py` (supply rules), `mining_prototype.py` (puzzle + miner),
`test_mining_prototype.py` (tests). Stdlib only — no new dependencies.

## Design

**Puzzle — memory-hard PoW, scrypt stand-in (NOT RandomX).**
Each hash attempt uses `hashlib.scrypt` with a large scratchpad
(Eco ~256 MiB, Balanced ~512 MiB, Performance ~1 GiB), which reduces
the advantage of specialized mining hardware. This prototype is a
**stand-in**: production must evaluate native RandomX (reference
implementation: fast mode ~2,080 MiB shared memory, light mode
~256 MiB) later, after review. Do not claim this prototype is RandomX,
and do not trust a currency to a home-grown algorithm.

**NO RAM bonus.** A block's reward is identical on every machine —
it comes only from the consensus schedule. RAM/CPU only set what
resources the miner is allowed to use within the owner's limits.
A 64 GB machine earns exactly the same per accepted block as an
8 GB machine. RAM tiers are design targets only (8 GB → Eco,
16–32 GB → Standard/Balanced, 64 GB+ → High-Capacity); actual speed
depends on CPU, memory bandwidth, OS, cooling, and electricity use.

**Hashrate sets SPEED / SHARE — not reward per block.** A miner's
hashrate (set by its CPU/RAM) determines how fast it finds blocks:
alone on the network it wins 100% of blocks; competing, its expected
share = its own hashrate / total network hashrate. A bigger machine
mines MORE — only by winning a bigger share of the same scheduled
blocks, never by changing what a block pays.

**No internet-speed factor.** Internet speed does NOT affect PoW
earnings — it only affects how fast a solved block propagates to
peers (milliseconds). No internet-speed factor exists in the puzzle,
and none may be added.

**Difficulty adjustment STAYS.** Difficulty retargets toward the
30-second block time. It protects the 400B schedule from being
mined out in days by large farms: without it, 10,000 machines could
exhaust the supply almost immediately and drown the chain in blocks
nobody could sync or verify.

**Puzzle stays memory-hard.** The puzzle stays memory-hard (scrypt
stand-in; RandomX to be evaluated for production). No switch to a
SHA-256-like puzzle: that would let ASICs dominate and kill
laptop-first mining. Bigger machines still mine more under
memory-hard PoW (hashrate → share); memory-hardness only narrows the
gap so laptops stay competitive.

**Modes (resource limits, not rewards):** Eco (low memory, 1–2
threads, leaves headroom for normal tasks), Balanced (medium),
Performance (higher memory + more threads, bounded by user limits).

**Supply rules (`supply.py`):** max supply 500,000,000,000 QSR hard
cap, split into two parts that sum to the cap EXACTLY:
- **Mining: 398,617,500,000 QSR in 3 phases** (founder directive
  2026-10-14), under the 400,000,000,000 QSR budget ceiling:
  Phase 1: 50,000 QSR/block x 6,000,000 blocks (~5.7 yrs) = 300B.
  Phase 2: 25,000 QSR/block x 2,629,800 blocks (2.5 yrs) = 65.745B.
  Phase 3: 12,500 QSR/block x 2,629,800 blocks (2.5 yrs) = 32.8725B.
  Then STOP: every block at height >= 11,259,600 pays 0, forever.
  Halvings are hard-coded eras triggered by BLOCK HEIGHT (coins
  mined), never by date — more miners do not shorten phases;
  difficulty holds ~30s blocks, so extra miners only split the same
  reward. See the math proof in `supply.py`. Mining ends after
  ~10.7 years.
- **Founder allocation: 100,000,000,000 QSR (20% of cap)** — one
  transparent genesis allocation, NOT mined. It unlocks linearly over
  ONE WEEK (20,160 blocks at 30s; founder directive 2026-10-14).
  Nodes reject any founder claim beyond the scheduled unlocked
  amount. Claims are manual (`claim-founder`); no founder reward is
  paid automatically on mining blocks.

**Per-phase mining emission (30s blocks):**

| Phase | Reward/block | Blocks | Mined | Cumulative |
|---|---|---|---|---|
| 1 | 50,000 QSR | 6,000,000 (~5.7 yrs) | 300,000,000,000 | 300B |
| 2 | 25,000 QSR | 2,629,800 (2.5 yrs) | 65,745,000,000 | 365.745B |
| 3 | 12,500 QSR | 2,629,800 (2.5 yrs) | 32,872,500,000 | 398.6175B |

Then mining rewards stop forever at height 11,259,600.
Every node must independently run `validate_block_reward()` /
`validate_founder_claim()` / `validate_combined_supply()` and reject
anything beyond the schedule, the vesting, or the cap.

**Distribution.** 398,617,500,000 via mining + 100,000,000,000
founder allocation = 498,617,500,000 QSR, under the 500B hard cap.
The founder allocation is the ONLY non-mining issuance;
no other allocation, reserve, airdrop, or side path exists (verified
by test). Scope note: the older, separate `staking.py` tap/staking
demo has its own demo-coin logic and is NOT part of coin
distribution — it must never be wired into the mining chain.

**No price or value targets.** Nothing in the prototype states or
implies any price, value, or market outcome. Test coins have no
monetary value.

**Customer-first / consent:** the miner **refuses to run** without
explicit owner consent (`--i-consent`). Pause/resume, user-set
thread/memory/runtime limits, best-effort CPU-temperature safeguard
(psutil if available, otherwise gracefully disabled), and mining
statistics (hashrate, accepted/rejected work, rough estimated
energy, confirmed test QSR). Energy numbers are ROUGH estimates
(CPU time × assumed watts), **not measurements**. No hidden mining:
nothing runs without being started explicitly, and nothing installs
itself anywhere. Continuous mining causes heat, fan noise,
electricity cost, and battery wear. A browser tab is NOT a
dependable 24/7 mining service.

**Verification:** every accepted block is independently re-verified
(`verify()`) and its reward checked against the schedule before any
test QSR is credited. The miner cannot award itself coins by
reporting a high hashrate.

## NOT built yet

- **Stage 3 — production network:** only after consensus review,
  security testing, economic modelling, and an independent audit.
  Not built.
- **Real RandomX:** the prototype uses scrypt as a stand-in. Not built.
- **Any price, exchange listing, or value promise:** never part of this
  project.

## Stage 2 — TESTNET (BUILT)

`node.py` now runs the `supply.py` schedule (3 phases:
50,000 -> 25,000 -> 12,500 QSR/block, then stop; 398,617,500,000
mined + 100B founder, under the 500B cap). Old pre-Stage-2 chains
are rejected on load — start a fresh data directory for the
testnet chain.

- **Founder claims:** `FounderClaimTransaction` pays unlocked founder
  allocation to the founder address committed in the genesis block.
  Vesting is linear over ONE WEEK (20,160 blocks) by block height;
  every node rejects over-claims, double-claims, and claims to
  non-founder addresses.
- **Real mining to wallet:** mined blocks credit the coinbase to the
  miner's wallet address as a real chain balance (`balance` command).
- **Live difficulty:** retargets every 10 blocks toward the 60s target
  (faster → +1 leading zero, slower → −1, else hold). Difficulty is
  derived from chain history, so all nodes agree per height.
- **P2P:** peers reject blocks/chains violating the schedule on sync
  and broadcast. Testnet is invite-only (seed node + `add-peer`),
  localhost / trusted LAN / VPN only.

### Auto-mine (`mine-auto`) — the node mines by itself

Typing `mine founder` for every block is only for testing. For real
operation the node mines **automatically**, one block at a time:

- **Node console:** `mine-auto founder` (or `mine-auto founder 50` to
  mine exactly 50 blocks, then stop)
- **Plain CLI:** `python quasar_cli.py mine-auto founder 50`

**Miner policy only — no consensus change.** Auto-mine uses the exact
same `mine_pending()` path as manual `mine` (same coinbase, mempool
inclusion, P2P broadcast, persistence). The only difference is pacing:
after each block it waits until **30 seconds** have elapsed since the
previous block's timestamp before mining the next one.

**Why pacing matters:** the difficulty retarget expects ~30s blocks.
Manual instant mining made blocks arrive in seconds, so the retarget
kept adding +1 leading zero (16x harder) every 10 blocks and mining
stalled. Paced ~30s blocks make the retarget **hold difficulty steady**
instead of ratcheting up.

**Stopping:** press **Ctrl+C** — it stops cleanly and returns to the
prompt. A half-mined block is never appended. Already-mined blocks stay.

**Upgrading a live node to get auto-mine:** in the console type `quit`,
replace the `.py` files with the new versions, then restart with the
**same** `--datadir` folder and the same start-node command. Your
`chain_data.json` (chain) and `wallets/` are preserved — no new genesis,
no lost coins. The old chain loads and validates under the new code.

See `TESTNET_STEPS.txt` for exact run commands. Tests:
`python3 test_stage2_testnet.py` (28 tests) +
`python3 test_mining_prototype.py` (41 tests) +
`python3 test_automine.py` (6 tests).
