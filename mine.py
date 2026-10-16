#!/usr/bin/env python3
"""
QUASAR COIN miner CLI (educational prototype).

Usage:
    python3 mine.py

Mines blocks one by one, showing for each block:
- block number, hash, nonce, hashes tried, time taken
- coins earned this block, total mined / 500B remaining
- running hash rate

Press Ctrl+C to stop.
"""

import sys
import time

from blockchain import Blockchain, DEFAULT_DIFFICULTY, MAX_SUPPLY

DIFFICULTY = DEFAULT_DIFFICULTY  # change me: higher = slower mining


def fmt(n):
    return f"{n:,.2f}"


def main():
    print("=" * 64)
    print("  QUASAR COIN - educational mining prototype")
    print("  Real SHA-256 proof-of-work. NOT launched. Coins have NO value.")
    print("=" * 64)
    print(f"  Difficulty     : {DIFFICULTY} leading zeros")
    print(f"  Max supply     : {MAX_SUPPLY:,} coins")
    print("  Press Ctrl+C to stop mining.\n")

    chain = Blockchain(difficulty=DIFFICULTY)
    total_hashes = 0
    total_seconds = 0.0
    blocks_mined = 0

    # Genesis block was mined in __init__; report it too
    g = chain.chain[0]
    print(f"[genesis] hash={g.hash} nonce={g.nonce}")
    print(f"          reward=50.00  total_mined={fmt(chain.total_mined)}")
    print("-" * 64)

    try:
        while True:
            block, stats, reward = chain.mine_block(
                transactions=[{"note": f"demo tx in block {len(chain.chain)}"}],
                miner_name="you",
            )
            blocks_mined += 1
            total_hashes += stats["hashes_tried"]
            total_seconds += stats["seconds"]
            avg_rate = total_hashes / total_seconds if total_seconds else 0

            print(f"[block {block.index}]")
            print(f"  hash        : {block.hash}")
            print(f"  nonce       : {block.nonce:,}  (hashes tried: {stats['hashes_tried']:,})")
            print(f"  time        : {stats['seconds']:.2f}s  | block rate: {stats['hash_rate']:,.0f} H/s")
            print(f"  reward      : +{fmt(reward)} coins")
            print(f"  total mined : {fmt(chain.total_mined)} / {MAX_SUPPLY:,} "
                  f"({chain.remaining_supply():,.0f} remaining)")
            print(f"  avg rate    : {avg_rate:,.0f} H/s over {blocks_mined} block(s)")
            print(f"  chain valid : {chain.is_chain_valid()}")
            print("-" * 64)
            sys.stdout.flush()
    except KeyboardInterrupt:
        print("\n\n⛏  Stopped by user.")
    finally:
        print(f"\nSession summary: {blocks_mined} block(s) mined, "
              f"{total_hashes:,} hashes, avg {total_hashes/total_seconds:,.0f} H/s" if total_seconds else
              "\nSession summary: no new blocks mined.")
        print(f"Total supply mined: {fmt(chain.total_mined)} / {MAX_SUPPLY:,}")
        print(f"Chain valid: {chain.is_chain_valid()}")


if __name__ == "__main__":
    main()
