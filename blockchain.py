"""
QUASAR COIN - educational blockchain prototype.

A genuine, minimal Bitcoin-style blockchain:
- SHA-256 hashing via Python hashlib (real proof-of-work)
- Adjustable difficulty (leading zeros)
- 500,000,000,000 (500 billion) max supply cap
- Block reward with halving every 210,000 blocks (Bitcoin-style)

This is NOT launched. It runs on one machine only: no network,
no peers, no wallets, no real miners, no monetary value.
"""

import hashlib
import json
import time

# ---- Coin parameters ----
MAX_SUPPLY = 500_000_000_000          # 500 billion coins total, hard cap
INITIAL_REWARD = 50                    # coins per block (genesis era)
HALVING_INTERVAL = 210_000             # blocks per era (Bitcoin-style)
DEFAULT_DIFFICULTY = 4                 # leading zeros; ~seconds per block on a laptop


def sha256(text: str) -> str:
    """Real SHA-256 hash, returned as hex string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def block_reward(height: int) -> float:
    """Reward for a block at a given height, halving every HALVING_INTERVAL."""
    halvings = height // HALVING_INTERVAL
    reward = INITIAL_REWARD
    for _ in range(halvings):
        reward = reward / 2
    return reward


class Block:
    def __init__(self, index, timestamp, transactions, previous_hash, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions      # list of dicts
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        block_data = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }, sort_keys=True)
        return sha256(block_data)

    def mine(self, difficulty: int) -> dict:
        """
        Real proof-of-work: increment nonce until the block hash
        starts with `difficulty` leading zeros.
        Returns stats about the mining run.
        """
        target = "0" * difficulty
        hashes_tried = 0
        start = time.time()
        while True:
            self.nonce += 1
            hashes_tried += 1
            self.hash = self.calculate_hash()
            if self.hash.startswith(target):
                break
        elapsed = time.time() - start
        return {
            "hashes_tried": hashes_tried,
            "seconds": elapsed,
            "hash_rate": hashes_tried / elapsed if elapsed > 0 else 0,
        }

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }


class Blockchain:
    def __init__(self, difficulty: int = DEFAULT_DIFFICULTY):
        self.difficulty = difficulty
        self.chain = []
        self.total_mined = 0.0
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis = Block(0, time.time(), [{"note": "genesis block"}], "0")
        # Genesis is mined too, so its hash also satisfies difficulty
        genesis.mine(self.difficulty)
        self.chain.append(genesis)
        reward = block_reward(0)
        self.total_mined += reward

    @property
    def latest_block(self) -> Block:
        return self.chain[-1]

    def remaining_supply(self) -> float:
        return MAX_SUPPLY - self.total_mined

    def mine_block(self, transactions=None, miner_name: str = "miner") -> tuple:
        """
        Mine the next block. Returns (block, mining_stats, reward_earned).
        """
        if self.remaining_supply() <= 0:
            raise RuntimeError("Max supply reached: no more coins can be mined.")

        height = len(self.chain)
        reward = block_reward(height)
        # Don't pay out more than what remains
        reward = min(reward, self.remaining_supply())

        txs = list(transactions or [])
        txs.insert(0, {
            "type": "coinbase",
            "to": miner_name,
            "amount": reward,
            "note": f"block reward for block {height}",
        })

        new_block = Block(
            index=height,
            timestamp=time.time(),
            transactions=txs,
            previous_hash=self.latest_block.hash,
        )
        stats = new_block.mine(self.difficulty)
        self.chain.append(new_block)
        self.total_mined += reward
        return new_block, stats, reward

    def is_chain_valid(self) -> bool:
        """Verify every block's hash, link, and proof-of-work."""
        target = "0" * self.difficulty
        for i, block in enumerate(self.chain):
            # Hash must match block contents
            if block.hash != block.calculate_hash():
                return False
            # Hash must satisfy difficulty
            if not block.hash.startswith(target):
                return False
            # Chain links must connect (except genesis)
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                return False
        return True
