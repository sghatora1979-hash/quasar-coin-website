"""
QUASAR CORE - node.py (STAGE 2 TESTNET)

A single-node Bitcoin-like blockchain for the Quasar testnet:

- Genesis block with a custom message ("Quasar Genesis - October 2026").
  The genesis block ALSO commits to the founder address (founder_address
  field, hashed into the block header). Every node on the network agrees
  on the founder because they agree on genesis.
- SHA-256 proof-of-work with LIVE difficulty retarget toward the
  30-second target block time (see RETARGET_INTERVAL). Difficulty is
  derived from chain history, so every node computes the same required
  difficulty for every height.
- Tokenomics (single source of truth: supply.py — NO local copies):
  500,000,000,000 max supply = 400B mining + 100B founder allocation.
  Mining pays 50,000 QSR/block x 6,000,000 blocks (phase 1, ~5.7 yrs),
  25,000 x 2,629,800 blocks (phase 2, 2.5 yrs),
  12,500 x 2,629,800 blocks (phase 3, 2.5 yrs), then 0 forever
  (stop height 11,259,600; total mined exactly 398,617,500,000 QSR).
  Founder allocation unlocks linearly over ONE WEEK (20,160 blocks)
  by block height and is claimed via FounderClaimTransaction
  (see transactions.py).
- Mempool: pending signed transactions + founder claims; miners include
  them in blocks. Founder claims are validated against vesting at the
  block height they are included in.
- UTXO set: rebuilt and fully re-validated on every load.
- Persistence: chain + mempool saved to chain_data.json.
- Full validation: hashes, links, proof-of-work (per-height difficulty),
  signatures, double-spends, coinbase amounts vs the supply schedule,
  founder claims vs vesting, combined supply cap.

STAGE 2 TESTNET ONLY. Test coins, no monetary value, no public launch.
Old chains from the pre-Stage-2 schedule (50 QSR/block, halving) are
INCOMPATIBLE: loading one raises a clear error — start a fresh data
directory for the Stage-2 testnet chain.
"""

import hashlib
import json
import os
import time

from transactions import (
    Transaction, TxInput, TxOutput, CoinbaseTransaction,
    FounderClaimTransaction, sha256_hex,
)
from wallet import base58check_encode, VERSION_BYTE
from supply import (
    block_reward_quarks, MAX_SUPPLY_QSR, QUARKS_PER_QSR,
    MINING_BUDGET_QUARKS, FOUNDER_TOTAL_QUARKS,
    founder_unlocked_quarks, validate_founder_claim,
    validate_combined_supply, TARGET_SECONDS_PER_BLOCK,
)

# ------------------------------------------------------------------ params
DEFAULT_DIFFICULTY = 3                   # leading hex zeros; laptop = seconds
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 64
# Retarget: every RETARGET_INTERVAL blocks, look at the last
# RETARGET_INTERVAL block intervals. Faster than half the target pace
# -> difficulty +1; slower than double -> difficulty -1; else hold.
# First RETARGET_INTERVAL + 1 blocks use DEFAULT_DIFFICULTY (warm-up:
# the genesis timestamp is fixed, so early windows would mislead).
RETARGET_INTERVAL = 10
GENESIS_MESSAGE = "Quasar Genesis - October 2026"
# Fixed genesis timestamp (2026-10-01 00:00:00 UTC). Mining is deterministic
# (nonce counts up from 0), so every node that creates the genesis block
# gets the IDENTICAL block. This is what lets P2P nodes agree they are on
# the same network. Changing this starts a whole new network.
GENESIS_TIMESTAMP = 1790812800
MAX_TXS_PER_BLOCK = 500
# Timestamp sanity: blocks may not be more than 5 minutes older than
# their predecessor (small clock skew) nor more than 2 hours in the
# future. Prevents timestamp games against the retarget.
MAX_BACKWARD_SKEW = 300
MAX_FUTURE_SKEW = 7200


def _default_data_path() -> str:
    """Location of chain_data.json.

    Override with the QUASAR_DATA_DIR environment variable so multiple
    nodes can run on one machine, each with its own chain data.
    """
    base = os.environ.get("QUASAR_DATA_DIR")
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "chain_data.json")


DATA_PATH = _default_data_path()


def merkle_root(tx_hashes):
    """Simple merkle root over transaction hashes (duplicates last if odd)."""
    if not tx_hashes:
        return "00" * 32
    layer = list(tx_hashes)
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [sha256_hex(layer[i] + layer[i + 1])
                 for i in range(0, len(layer), 2)]
    return layer[0]


# ------------------------------------------------------------------- block
class Block:
    def __init__(self, height, timestamp, transactions, prev_hash,
                 nonce=0, block_hash="", founder_address=""):
        self.height = height
        self.timestamp = timestamp
        self.transactions = transactions      # list[Transaction]
        self.prev_hash = prev_hash
        self.nonce = nonce
        # founder_address MUST be set before compute_hash(): it is part
        # of the header. Only the genesis block (height 0) carries one.
        self.founder_address = founder_address
        self.hash = block_hash or self.compute_hash()

    def header(self) -> str:
        tx_hashes = [t.tx_hash() for t in self.transactions]
        return (f"{self.height}|{self.timestamp}|{self.prev_hash}|"
                f"{merkle_root(tx_hashes)}|{self.nonce}|"
                f"{self.founder_address}")

    def compute_hash(self) -> str:
        return sha256_hex(self.header())

    def mine(self, difficulty: int, log_every: int = 200_000) -> dict:
        """Proof-of-work: find nonce so hash starts with `difficulty` zeros."""
        target = "0" * difficulty
        start = time.time()
        while True:
            h = self.compute_hash()
            if h.startswith(target):
                self.hash = h
                return {"hash": h, "nonce": self.nonce,
                        "seconds": round(time.time() - start, 2),
                        "hashes": self.nonce + 1}
            self.nonce += 1
            if self.nonce % log_every == 0 and self.nonce:
                print(f"  ... {self.nonce:,} hashes tried", flush=True)

    def to_dict(self):
        txs = []
        for t in self.transactions:
            d = t.to_dict()
            d["coinbase"] = isinstance(t, CoinbaseTransaction)
            txs.append(d)
        return {"height": self.height, "timestamp": self.timestamp,
                "transactions": txs, "prev_hash": self.prev_hash,
                "nonce": self.nonce, "hash": self.hash,
                "founder_address": self.founder_address}

    @classmethod
    def from_dict(cls, d):
        txs = []
        for td in d["transactions"]:
            if td.get("coinbase"):
                txs.append(CoinbaseTransaction.from_dict(td))
            else:
                # Transaction.from_dict dispatches founder claims.
                txs.append(Transaction.from_dict(td))
        return cls(d["height"], d["timestamp"], txs,
                   d["prev_hash"], d["nonce"], d["hash"],
                   d.get("founder_address", ""))

# --------------------------------------------------------------- blockchain
class Blockchain:
    def __init__(self, difficulty: int = DEFAULT_DIFFICULTY,
                 data_path: str = None):
        self.difficulty = difficulty    # difficulty for the NEXT block
        self.data_path = data_path or _default_data_path()
        self.chain = []            # list[Block]
        self.mempool = []          # list[Transaction] (verified, unconfirmed)
        self.utxo = {}             # (tx_hash, idx) -> (address, amount_quarks)
        self.total_mined_quarks = 0
        self.total_founder_claimed_quarks = 0
        # _diffs[h] = difficulty required for the block at height h.
        # Rebuilt from chain history on load; extended as blocks append.
        self._diffs = []

    @property
    def founder_address(self) -> str:
        """The founder address committed in the genesis block ('' if none)."""
        return self.chain[0].founder_address if self.chain else ""

    # -------------------------------------------------------- difficulty
    @staticmethod
    def _difficulty_for_height(chain, height: int,
                               prev_difficulty: int) -> int:
        """Difficulty required for the block at `height`, from the chain
        prefix before it (blocks with height < `height`) and the
        difficulty of block height-1. Pure function of chain history:
        every node computes the same value for the same height."""
        if height <= RETARGET_INTERVAL + 1:
            return DEFAULT_DIFFICULTY
        end = chain[height - 1].timestamp
        start = chain[height - 1 - RETARGET_INTERVAL].timestamp
        timespan = end - start
        expected = RETARGET_INTERVAL * TARGET_SECONDS_PER_BLOCK
        if timespan < expected / 2:
            return min(prev_difficulty + 1, MAX_DIFFICULTY)
        if timespan > expected * 2:
            return max(prev_difficulty - 1, MIN_DIFFICULTY)
        return prev_difficulty

    def _rebuild_difficulty_cache(self):
        """Recompute _diffs for the whole chain from timestamps."""
        diffs = []
        for h in range(len(self.chain)):
            prev = diffs[h - 1] if h > 0 else DEFAULT_DIFFICULTY
            diffs.append(self._difficulty_for_height(self.chain, h, prev))
        self._diffs = diffs
        self.difficulty = self.expected_difficulty(len(self.chain))

    def expected_difficulty(self, height: int) -> int:
        """Difficulty required for the block at `height` on this chain."""
        if height == 0:
            return DEFAULT_DIFFICULTY
        if height < len(self._diffs):
            return self._diffs[height]
        if height == len(self._diffs) and height == len(self.chain):
            prev = self._diffs[height - 1] if height > 0 else DEFAULT_DIFFICULTY
            return self._difficulty_for_height(self.chain, height, prev)
        if height == len(self.chain):
            # Cache stale (e.g. chain replaced without rebuild): recompute.
            self._rebuild_difficulty_cache()
            return self._diffs[height] if height < len(self._diffs) else \
                self._difficulty_for_height(self.chain, height,
                                            self._diffs[height - 1])
        raise ValueError(f"cannot compute difficulty for height {height} "
                         f"(chain has {len(self.chain)} blocks)")

    # ------------------------------------------------------------- genesis
    @staticmethod
    def _genesis_address() -> str:
        # Burn address: valid format, nobody owns the key.
        return base58check_encode(bytes([VERSION_BYTE]) + b"\x00" * 20)

    def create_genesis(self, founder_address: str = ""):
        coinbase = CoinbaseTransaction(
            self._genesis_address(), block_reward_quarks(0), 0)
        # Fixed timestamp -> deterministic mining -> identical genesis block
        # on every node. The message is hashed into prev_hash so the block
        # commits to it (like Bitcoin's "Chancellor on brink..." headline).
        # The founder address is hashed into the header: consensus.
        genesis = Block(0, GENESIS_TIMESTAMP, [coinbase],
                        sha256_hex(GENESIS_MESSAGE)[:64],
                        founder_address=founder_address)
        genesis.mine(DEFAULT_DIFFICULTY)
        self.chain.append(genesis)
        self._diffs = [DEFAULT_DIFFICULTY]
        self._apply_block_utxo(genesis)
        self.difficulty = self.expected_difficulty(1)

    # --------------------------------------------------------------- utxo
    def _apply_block_utxo(self, block: Block):
        for tx in block.transactions:
            th = tx.tx_hash()
            for txin in tx.inputs:
                self.utxo.pop((txin.prev_tx_hash, txin.prev_output_index), None)
            for idx, out in enumerate(tx.outputs):
                self.utxo[(th, idx)] = (out.address, out.amount_quarks)
            if tx.is_coinbase():
                self.total_mined_quarks += sum(
                    o.amount_quarks for o in tx.outputs)
            elif isinstance(tx, FounderClaimTransaction):
                self.total_founder_claimed_quarks += sum(
                    o.amount_quarks for o in tx.outputs)

    def utxo_lookup(self, tx_hash, idx):
        return self.utxo.get((tx_hash, idx))

    def get_balance_quarks(self, address: str) -> int:
        return sum(amt for (addr, amt) in self.utxo.values() if addr == address)

    def get_balance(self, address: str) -> float:
        return self.get_balance_quarks(address) / QUARKS_PER_QSR

    # -------------------------------------------------------------- mempool
    def _mempool_spent(self):
        spent = set()
        for tx in self.mempool:
            for txin in tx.inputs:
                spent.add((txin.prev_tx_hash, txin.prev_output_index))
        return spent

    def _mempool_founder_claimed(self) -> int:
        return sum(o.amount_quarks
                   for tx in self.mempool
                   if isinstance(tx, FounderClaimTransaction)
                   for o in tx.outputs)

    def add_transaction(self, tx: Transaction) -> tuple:
        """Verify a signed tx and add it to the mempool. Returns (ok, msg)."""
        if tx.is_coinbase():
            return False, "coinbase transactions cannot go in the mempool"
        if any(t.tx_hash() == tx.tx_hash() for t in self.mempool):
            return False, "already in mempool"
        if isinstance(tx, FounderClaimTransaction):
            # Founder claims: structural check + cumulative total cap.
            # Vesting is checked at block inclusion (it depends on the
            # height the claim lands in), not here.
            if not self.founder_address:
                return False, "this chain has no founder address set"
            ok, reason = tx.verify(None, self.founder_address)
            if not ok:
                return False, f"invalid founder claim: {reason}"
            pending = self._mempool_founder_claimed()
            if (self.total_founder_claimed_quarks + pending
                    + tx.outputs[0].amount_quarks > FOUNDER_TOTAL_QUARKS):
                return False, "claim would exceed 100B founder allocation"
            self.mempool.append(tx)
            return True, f"added to mempool ({reason})"
        spent = self._mempool_spent()
        for txin in tx.inputs:
            if (txin.prev_tx_hash, txin.prev_output_index) in spent:
                return False, "input already spent by a pending transaction"
        ok, reason = tx.verify(self.utxo_lookup)
        if not ok:
            return False, f"invalid transaction: {reason}"
        if len(self.mempool) >= 10_000:
            return False, "mempool full"
        self.mempool.append(tx)
        return True, f"added to mempool ({reason})"

    # --------------------------------------------------------------- mining
    def mine_pending(self, miner_address: str) -> dict:
        """Mine one block: coinbase + founder claims + up to
        MAX_TXS_PER_BLOCK mempool txs."""
        height = len(self.chain)
        reward = block_reward_quarks(height)
        if self.total_mined_quarks + reward > MINING_BUDGET_QUARKS:
            return {"ok": False, "error": "mining budget exhausted - no reward left"}

        # Re-verify mempool txs against current UTXO (skip any that conflict).
        included, skipped = [], 0
        temp_spent = set()
        for tx in self.mempool:
            if isinstance(tx, FounderClaimTransaction):
                # Vesting is checked at THIS block's height, against
                # already-claimed + claims already included in this block.
                included_claims = sum(
                    o.amount_quarks for t in included
                    if isinstance(t, FounderClaimTransaction)
                    for o in t.outputs)
                ok, reason = validate_founder_claim(
                    height, tx.outputs[0].amount_quarks,
                    self.total_founder_claimed_quarks + included_claims)
                if ok:
                    included.append(tx)
                else:
                    skipped += 1
                continue
            conflict = any((i.prev_tx_hash, i.prev_output_index) in temp_spent
                           for i in tx.inputs)
            ok, _ = tx.verify(self.utxo_lookup)
            if ok and not conflict:
                included.append(tx)
                for i in tx.inputs:
                    temp_spent.add((i.prev_tx_hash, i.prev_output_index))
            else:
                skipped += 1
            if len(included) >= MAX_TXS_PER_BLOCK:
                break

        coinbase = CoinbaseTransaction(miner_address, reward, height)
        difficulty = self.expected_difficulty(height)
        block = Block(height, int(time.time()),
                      [coinbase] + included, self.chain[-1].hash)
        print(f"Mining block {height} (difficulty={'0'*difficulty}, "
              f"{len(included)} txs)...", flush=True)
        res = block.mine(difficulty)

        self.chain.append(block)
        self._diffs.append(difficulty)
        self._apply_block_utxo(block)
        self.difficulty = self.expected_difficulty(len(self.chain))
        included_hashes = {t.tx_hash() for t in included}
        self.mempool = [t for t in self.mempool
                        if t.tx_hash() not in included_hashes]
        self.save()
        claims_included = sum(
            o.amount_quarks for t in included
            if isinstance(t, FounderClaimTransaction) for o in t.outputs)
        return {"ok": True, "height": height, "hash": block.hash,
                "nonce": block.nonce, "seconds": res["seconds"],
                "hashes": res["hashes"], "txs": len(included),
                "skipped": skipped,
                "reward_qsr": reward / QUARKS_PER_QSR,
                "founder_claims": sum(
                    1 for t in included
                    if isinstance(t, FounderClaimTransaction)),
                "founder_claimed_qsr": claims_included / QUARKS_PER_QSR}

    # ------------------------------------------------------------ auto-mine
    def mine_auto(self, miner_address: str, count: int = None,
                  pace_seconds: float = TARGET_SECONDS_PER_BLOCK,
                  sleep_chunk: float = 0.5,
                  on_block=None, on_wait=None, lock=None) -> dict:
        """MINER POLICY (not consensus): mine blocks automatically, paced.

        Mines one block at a time through the SAME mine_pending() path
        as manual mining (same coinbase, mempool inclusion, broadcast
        hook points, persistence), then waits until `pace_seconds` have
        elapsed since the previous block's timestamp before mining the
        next one. Pacing keeps the average block time near
        TARGET_SECONDS_PER_BLOCK (30s) — exactly what the difficulty
        retarget expects — so difficulty stabilizes instead of ratcheting
        up under rapid manual mining.

        - count: mine exactly this many blocks, then stop (None = forever).
        - pace_seconds: seconds between block timestamps (0 = as fast as
          possible; used by tests).
        - sleep_chunk: wait granularity; kept small so Ctrl+C stays
          responsive during the wait.
        - on_block: optional callback(res) after each mined block.
        - on_wait: optional callback(seconds_remaining) before each wait.
        - lock: optional threading lock held ONLY while a block is being
          mined (never during the wait), so P2P sync can proceed between
          blocks.
        Ctrl+C stops cleanly at any point: the in-progress block is
        discarded (it is only appended after PoW completes), already-mined
        blocks stay. Returns {"ok": True, "mined": N} or
        {"ok": False, "mined": N, "error": ...} if mining fails.
        """
        mined = 0
        try:
            while count is None or mined < count:
                if self.chain:
                    deadline = self.chain[-1].timestamp + pace_seconds
                    remaining = deadline - time.time()
                    if remaining > 0:
                        if on_wait:
                            on_wait(remaining)
                        while True:
                            remaining = deadline - time.time()
                            if remaining <= 0:
                                break
                            time.sleep(min(sleep_chunk, remaining))
                acquired = False
                if lock is not None:
                    lock.acquire()
                    acquired = True
                try:
                    res = self.mine_pending(miner_address)
                finally:
                    if acquired:
                        lock.release()
                if not res.get("ok"):
                    return {"ok": False, "mined": mined,
                            "error": res.get("error")}
                mined += 1
                if on_block:
                    on_block(res)
        except KeyboardInterrupt:
            pass
        return {"ok": True, "mined": mined}

    # ------------------------------------------------------------ validation
    @staticmethod
    def _check_timestamps(block: Block, prev_block) -> tuple:
        """Timestamp sanity: not too far behind predecessor, not too far
        in the future. Returns (ok, reason)."""
        now = time.time()
        if prev_block is not None:
            if block.timestamp < prev_block.timestamp - MAX_BACKWARD_SKEW:
                return False, "timestamp too far behind predecessor"
        if block.timestamp > now + MAX_FUTURE_SKEW:
            return False, "timestamp too far in the future"
        return True, "ok"

    def _validate_block_txs(self, block: Block, utxo: dict,
                            founder_claimed: int, total_mined: int,
                            founder_address: str) -> tuple:
        """Validate all transactions in one block against a temp UTXO set.
        Shared by validate_chain (full history) and validate_next_block
        (single block). Returns (ok, reason, new_founder_claimed,
        new_total_mined). Does NOT mutate anything."""
        seen_inputs = set()
        coinbases = 0
        for tx in block.transactions:
            if tx.is_coinbase():
                coinbases += 1
                if coinbases > 1:
                    return False, "multiple coinbases", founder_claimed, total_mined
                if len(tx.outputs) != 1:
                    return False, "malformed coinbase", founder_claimed, total_mined
                expected = block_reward_quarks(block.height)
                if tx.outputs[0].amount_quarks != expected:
                    return False, (f"coinbase pays "
                                   f"{tx.outputs[0].amount_quarks}, "
                                   f"expected {expected}"), founder_claimed, total_mined
                total_mined += tx.outputs[0].amount_quarks
            elif isinstance(tx, FounderClaimTransaction):
                if not founder_address:
                    return False, "founder claim on a chain with no founder", \
                        founder_claimed, total_mined
                ok, reason = tx.verify(None, founder_address)
                if not ok:
                    return False, f"bad founder claim: {reason}", \
                        founder_claimed, total_mined
                th = tx.tx_hash()
                if (th, 0) in utxo:
                    return False, "founder claim tx_hash collides with UTXO", \
                        founder_claimed, total_mined
                ok, reason = validate_founder_claim(
                    block.height, tx.outputs[0].amount_quarks,
                    founder_claimed)
                if not ok:
                    return False, f"founder claim rejected: {reason}", \
                        founder_claimed, total_mined
                founder_claimed += tx.outputs[0].amount_quarks
            else:
                ok, reason = tx.verify(lambda h, i, _u=utxo: _u.get((h, i)))
                if not ok:
                    return False, (f"tx {tx.tx_hash()[:12]}: {reason}"), \
                        founder_claimed, total_mined
                for txin in tx.inputs:
                    key = (txin.prev_tx_hash, txin.prev_output_index)
                    if key in seen_inputs:
                        return False, f"double-spend of {key}", \
                            founder_claimed, total_mined
                    seen_inputs.add(key)
            # apply to temp utxo
            th = tx.tx_hash()
            for txin in tx.inputs:
                utxo.pop((txin.prev_tx_hash, txin.prev_output_index), None)
            for idx, out in enumerate(tx.outputs):
                utxo[(th, idx)] = (out.address, out.amount_quarks)
        ok, reason = validate_combined_supply(total_mined, founder_claimed)
        if not ok:
            return False, reason, founder_claimed, total_mined
        return True, "ok", founder_claimed, total_mined

    def validate_chain(self) -> tuple:
        """Full re-validation from genesis. Returns (ok: bool, msg: str)."""
        if not self.chain:
            return False, "empty chain"
        utxo = {}
        total_mined = 0
        founder_claimed = 0
        founder_address = self.chain[0].founder_address
        diffs = []
        for block in self.chain:
            # 1. hash integrity + proof-of-work at THIS height's difficulty
            if block.compute_hash() != block.hash:
                return False, f"block {block.height}: hash mismatch (tampered?)"
            prev_diff = diffs[block.height - 1] if block.height > 0 \
                else DEFAULT_DIFFICULTY
            expected_diff = self._difficulty_for_height(
                self.chain, block.height, prev_diff)
            diffs.append(expected_diff)
            if not block.hash.startswith("0" * expected_diff):
                return False, (f"block {block.height}: bad proof-of-work "
                               f"(needs {expected_diff} leading zeros)")
            # 2. chain links + timestamps + founder-address placement
            if block.height == 0:
                if block.prev_hash != sha256_hex(GENESIS_MESSAGE)[:64]:
                    return False, "genesis block message mismatch"
                if founder_address and not founder_address.startswith("Q"):
                    return False, "genesis founder address malformed"
            else:
                if block.prev_hash != self.chain[block.height - 1].hash:
                    return False, f"block {block.height}: prev_hash mismatch"
                if block.height != self.chain[block.height - 1].height + 1:
                    return False, f"block {block.height}: height not sequential"
                if block.founder_address:
                    return False, (f"block {block.height}: founder_address "
                                   f"belongs only in the genesis block")
                ok, reason = self._check_timestamps(
                    block, self.chain[block.height - 1])
                if not ok:
                    return False, f"block {block.height}: {reason}"
            # 3. transactions
            ok, reason, founder_claimed, total_mined = \
                self._validate_block_txs(block, utxo, founder_claimed,
                                         total_mined, founder_address)
            if not ok:
                return False, f"block {block.height}: {reason}"
        # 4. combined supply cap
        ok, reason = validate_combined_supply(total_mined, founder_claimed)
        if not ok:
            return False, reason
        return True, (f"chain valid: {len(self.chain)} blocks, "
                      f"{total_mined / QUARKS_PER_QSR:,.2f} QSR mined, "
                      f"{founder_claimed / QUARKS_PER_QSR:,.2f} QSR founder-claimed")

    def validate_next_block(self, block: Block) -> tuple:
        """Validate ONE block as the next tip (for P2P sync).

        Mirrors validate_chain()'s per-block checks but runs against the
        CURRENT tip and UTXO set, without mutating anything.
        Returns (ok: bool, msg: str).
        """
        if not self.chain:
            return False, "no local chain to extend"
        tip = self.chain[-1]
        if block.height != tip.height + 1:
            return False, (f"bad height {block.height}, "
                           f"expected {tip.height + 1}")
        if block.prev_hash != tip.hash:
            return False, "prev_hash does not match our tip"
        if block.compute_hash() != block.hash:
            return False, "hash mismatch (tampered?)"
        expected_diff = self.expected_difficulty(block.height)
        if not block.hash.startswith("0" * expected_diff):
            return False, (f"bad proof-of-work "
                           f"(needs {expected_diff} leading zeros)")
        if block.founder_address:
            return False, "founder_address belongs only in the genesis block"
        ok, reason = self._check_timestamps(block, tip)
        if not ok:
            return False, reason
        utxo = dict(self.utxo)
        ok, reason, _, _ = self._validate_block_txs(
            block, utxo, self.total_founder_claimed_quarks,
            self.total_mined_quarks, self.founder_address)
        if not ok:
            return False, reason
        return True, "ok"

    def append_validated_block(self, block: Block):
        """Append a block that already passed validate_next_block().

        Applies UTXO changes, drops now-confirmed mempool txs, saves.
        """
        difficulty = self.expected_difficulty(block.height)
        self.chain.append(block)
        self._diffs.append(difficulty)
        self._apply_block_utxo(block)
        self.difficulty = self.expected_difficulty(len(self.chain))
        included = {t.tx_hash() for t in block.transactions}
        self.mempool = [t for t in self.mempool
                        if t.tx_hash() not in included]
        self.save()

    def adopt_chain(self, blocks: list) -> tuple:
        """Replace our chain with a longer VALID one (P2P reorg).

        `blocks` is the FULL candidate chain from genesis. It is fully
        re-validated before anything is replaced. Returns (ok, msg).
        """
        if len(blocks) <= len(self.chain):
            return False, "candidate chain is not longer than ours"
        tmp = Blockchain(self.difficulty)
        tmp.chain = list(blocks)
        ok, msg = tmp.validate_chain()
        if not ok:
            return False, f"candidate chain invalid: {msg}"
        self.chain = list(blocks)
        self.utxo = {}
        self.total_mined_quarks = 0
        self.total_founder_claimed_quarks = 0
        for b in self.chain:
            self._apply_block_utxo(b)
        self._rebuild_difficulty_cache()
        # Keep mempool txs that are still valid and not yet confirmed.
        confirmed = {t.tx_hash() for b in self.chain for t in b.transactions}
        kept, spent = [], set()
        for tx in self.mempool:
            if tx.tx_hash() in confirmed:
                continue
            if isinstance(tx, FounderClaimTransaction):
                ok2, _ = tx.verify(None, self.founder_address)
                if ok2:
                    kept.append(tx)
                continue
            if any((i.prev_tx_hash, i.prev_output_index) in spent
                   for i in tx.inputs):
                continue
            ok2, _ = tx.verify(self.utxo_lookup)
            if ok2:
                kept.append(tx)
                for i in tx.inputs:
                    spent.add((i.prev_tx_hash, i.prev_output_index))
        self.mempool = kept
        self.save()
        return True, (f"adopted longer chain: {len(blocks)} blocks, "
                      f"{msg}")

    # ----------------------------------------------------------- persistence
    def save(self):
        with open(self.data_path, "w") as f:
            json.dump({"difficulty": self.difficulty,
                       "blocks": [b.to_dict() for b in self.chain],
                       "mempool": [self._tx_to_dict(t) for t in self.mempool]},
                      f)

    @staticmethod
    def _tx_to_dict(t):
        d = t.to_dict()
        d["coinbase"] = isinstance(t, CoinbaseTransaction)
        return d

    @classmethod
    def load(cls, difficulty: int = DEFAULT_DIFFICULTY,
             data_path: str = None, founder_address: str = "") -> "Blockchain":
        bc = cls(difficulty, data_path=data_path)
        parent = os.path.dirname(bc.data_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if os.path.exists(bc.data_path):
            with open(bc.data_path) as f:
                data = json.load(f)
            for bd in data["blocks"]:
                block = Block.from_dict(bd)
                bc.chain.append(block)
                bc._apply_block_utxo(block)
            for td in data.get("mempool", []):
                if td.get("coinbase"):
                    bc.mempool.append(CoinbaseTransaction.from_dict(td))
                else:
                    # Transaction.from_dict dispatches founder claims.
                    bc.mempool.append(Transaction.from_dict(td))
            # The saved chain must fully validate under the CURRENT
            # (Stage-2) rules. An old-schedule chain (50 QSR/block,
            # halving) fails here with a clear error instead of
            # silently mixing two schedules.
            ok, msg = bc.validate_chain()
            if not ok:
                raise ValueError(
                    f"Saved chain failed validation: {msg}. "
                    "This chain data is from an incompatible "
                    "(pre-Stage-2) network — delete chain_data.json or "
                    "use a fresh --datadir to start a new Stage-2 "
                    "testnet chain.")
            bc._rebuild_difficulty_cache()
        else:
            bc.create_genesis(founder_address=founder_address)
            bc.save()
        return bc

    # ----------------------------------------------------------------- info
    def info(self) -> dict:
        mined = self.total_mined_quarks / QUARKS_PER_QSR
        claimed = self.total_founder_claimed_quarks / QUARKS_PER_QSR
        height = len(self.chain) - 1
        unlocked = founder_unlocked_quarks(max(height, 0)) / QUARKS_PER_QSR
        return {
            "height": height,
            "blocks": len(self.chain),
            "difficulty": self.difficulty,
            "tip_hash": self.chain[-1].hash if self.chain else None,
            "mined_qsr": mined,
            "remaining_qsr": MAX_SUPPLY_QSR - mined - claimed,
            "max_supply_qsr": MAX_SUPPLY_QSR,
            "next_reward_qsr": block_reward_quarks(len(self.chain)) / QUARKS_PER_QSR,
            "mempool_txs": len(self.mempool),
            "utxos": len(self.utxo),
            "founder_address": self.founder_address,
            "founder_claimed_qsr": claimed,
            "founder_unlocked_qsr": unlocked,
            "founder_remaining_qsr": FOUNDER_TOTAL_QUARKS / QUARKS_PER_QSR - claimed,
        }
