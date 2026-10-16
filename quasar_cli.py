#!/usr/bin/env python3
"""
QUASAR CORE - quasar_cli.py

Command-line interface for the local Quasar learning blockchain.

    python3 quasar_cli.py new-address <name>
    python3 quasar_cli.py balance <name-or-address>
    python3 quasar_cli.py mine <name> [--difficulty N]
    python3 quasar_cli.py mine-auto <name> [count]
        # Automatic paced mining: one block every 30s (Ctrl+C stops).
        # Same mine_pending() path as manual `mine`; miner policy only,
        # no consensus change. Give [count] to mine exactly N blocks.
    python3 quasar_cli.py claim-founder <amount_qsr>
        # Stage-2 TESTNET: claim unlocked founder allocation to the
        # founder address recorded in the genesis block. Vesting is
        # enforced by every node (linear unlock over 1 week by block
        # height). Test coins only, no value.
    python3 quasar_cli.py mine-prototype --mode eco --blocks 2 --i-consent
        # Stage-1 LOCAL mining prototype (test coins, no network, no value).
        # Requires explicit owner consent (--i-consent).
    python3 quasar_cli.py mine-benchmark
        # Benchmark the prototype puzzle in Eco/Balanced/Performance modes.
    python3 quasar_cli.py send <from_name> <to_address> <amount_qsr>
    python3 quasar_cli.py mempool
    python3 quasar_cli.py info
    python3 quasar_cli.py validate

P2P network (public chain - multiple nodes, shared blocks/txs):

    python3 quasar_cli.py start-node [--port 9333] [--datadir PATH]
                                     [--seed host:port ...]
                                     [--founder <founder-address>]
                                     [--mine-auto <wallet>]
        # Starts this machine's node, connects to seeds, opens an
        # interactive console. --mine-auto starts mining to <wallet>
        # immediately (one-click installer); otherwise use the console.
        #   mine <wallet> | mine-auto <wallet> [count] |
        #   send <from> <to> <qsr> | balance <x> |
        #   claim-founder <amount_qsr> | info | mempool | validate |
        #   peers | add-peer <host:port> | quit
        # --founder sets the founder address in the GENESIS block, but
        # only when starting a FRESH chain (no chain_data.json yet).
        # The seed node operator passes it once; peers inherit it by
        # syncing genesis from the seed.

Run with the project venv so `ecdsa` is available:
    ~/workspace/quasar-coin/qcore-venv/bin/python quasar_cli.py ...

=====================================================================
STAGE-2 TESTNET. Test coins only, no monetary value.
The P2P mode below is an EDUCATIONAL v1: no encryption, no auth yet.
Keep nodes on localhost or a private VPN for now.
=====================================================================
"""

import os
import sys

BANNER = ("=====================================================================\n"
          " QUASAR CORE - Stage-2 TESTNET. Test coins only, NO monetary value.\n"
          " For education/testing only.\n"
          "=====================================================================")

from wallet import Wallet
from transactions import (Transaction, TxInput, TxOutput,
                          qsr_to_quarks, quarks_to_qsr, QUARKS_PER_QSR,
                          FounderClaimTransaction)
from node import Blockchain, DEFAULT_DIFFICULTY
from supply import TARGET_SECONDS_PER_BLOCK


def resolve_address(name_or_addr: str) -> str:
    """Accept a wallet name or a raw Q... address."""
    if name_or_addr.startswith("Q"):
        return name_or_addr
    return Wallet.load(name_or_addr).address


def cmd_new_address(name: str):
    w = Wallet.generate()
    path = w.save(name)
    print(BANNER)
    print(f"\nNew wallet '{name}' created.")
    print(f"  Address:     {w.address}")
    print(f"  Public key:  {w.public_key_hex[:32]}...")
    print(f"  Saved to:    {path}")
    print("\nDEMO KEYS - back up the file above if you want to keep these coins.")
    print("Never use these keys for anything with real value.")


def cmd_balance(name_or_addr: str):
    bc = Blockchain.load()
    addr = resolve_address(name_or_addr)
    q = bc.get_balance(addr)
    print(f"Balance of {addr}: {q:,.8f} QSR")


def cmd_mine(name: str, difficulty: int = None):
    bc = Blockchain.load()
    if difficulty is not None:
        bc.difficulty = difficulty
    addr = resolve_address(name)
    print(BANNER)
    res = bc.mine_pending(addr)
    if not res.get("ok"):
        print("Mining failed:", res.get("error"))
        return
    print(f"\nBlock {res['height']} mined!")
    print(f"  Hash:    {res['hash']}")
    print(f"  Nonce:   {res['nonce']:,}")
    print(f"  Time:    {res['seconds']}s ({res['hashes']:,} hashes)")
    print(f"  Txs:     {res['txs']} (+coinbase, {res['skipped']} skipped)")
    print(f"  Reward:  {res['reward_qsr']:,.2f} QSR -> {addr}")
    print(f"  Balance: {bc.get_balance(addr):,.8f} QSR")


def cmd_mine_auto(name: str, count: int = None):
    """mine-auto <wallet> [count] — automatic paced mining (plain CLI).

    Miner policy only (no consensus change): mines through the SAME
    mine_pending() path as manual `mine`, pacing blocks
    TARGET_SECONDS_PER_BLOCK (30s) apart so the difficulty retarget sees
    the block time it expects and difficulty stabilizes. Ctrl+C stops
    cleanly; a half-mined block is never appended.
    """
    bc = Blockchain.load()
    addr = resolve_address(name)
    pace = TARGET_SECONDS_PER_BLOCK
    print(BANNER)
    scope = f"{count} blocks" if count is not None else "until stopped"
    print(f"Auto-mining to {addr}: one block every {pace:.0f}s "
          f"({scope}, Ctrl+C stops)...")

    def _show(res):
        print(f"  block {res['height']} mined: {res['hash'][:16]}... "
              f"({res['hashes']:,} hashes, {res['seconds']}s)", flush=True)

    def _wait(secs):
        print(f"  next block in ~{secs:.0f}s (Ctrl+C stops)...", flush=True)

    res = bc.mine_auto(addr, count=count, on_block=_show, on_wait=_wait)
    if not res.get("ok"):
        print(f"\nAuto-mine stopped: {res['mined']} block(s) mined, "
              f"then: {res.get('error')}")
    else:
        print(f"\nAuto-mine stopped: {res['mined']} block(s) mined. "
              f"Balance: {bc.get_balance(addr):,.8f} QSR")


def cmd_send(from_name: str, to_addr: str, amount_qsr: str):
    bc = Blockchain.load()
    wallet = Wallet.load(from_name)
    amount_quarks = qsr_to_quarks(float(amount_qsr))
    if amount_quarks <= 0:
        print("Amount must be positive.")
        return

    # Gather the sender's UTXOs until we cover the amount.
    owned = [(k, v) for k, v in bc.utxo.items() if v[0] == wallet.address]
    owned.sort(key=lambda kv: kv[1][1])
    chosen, total = [], 0
    for key, (addr, amt) in owned:
        chosen.append((key, amt))
        total += amt
        if total >= amount_quarks:
            break
    if total < amount_quarks:
        have = total / QUARKS_PER_QSR
        print(f"Insufficient funds: have {have:,.8f} QSR, need {float(amount_qsr):,.8f} QSR")
        return

    inputs = [TxInput(h, idx) for (h, idx), amt in chosen]
    outputs = [TxOutput(to_addr, amount_quarks)]
    change = total - amount_quarks
    if change > 0:
        outputs.append(TxOutput(wallet.address, change))  # change back to sender
    tx = Transaction(inputs, outputs)
    for i in range(len(inputs)):
        tx.sign_input(i, wallet)

    ok, msg = bc.add_transaction(tx)
    if ok:
        bc.save()
        print(f"Transaction created: {tx.tx_hash()}")
        print(f"  {float(amount_qsr):,.8f} QSR: {wallet.address} -> {to_addr}")
        if change:
            print(f"  Change: {change / QUARKS_PER_QSR:,.8f} QSR back to sender")
        print(f"  Status: {msg} (mine a block to confirm)")
    else:
        print("Transaction rejected:", msg)


def cmd_claim_founder(amount_qsr: str):
    """Stage-2 testnet: claim unlocked founder allocation.

    The claim goes into the mempool; the next mined block includes it
    if the amount is within the unlocked vesting at that block height.
    """
    import random
    bc = Blockchain.load()
    if not bc.founder_address:
        print("This chain has no founder address set (genesis has none).")
        print("Start the seed node with --founder <address> on a fresh chain.")
        return
    amount_quarks = qsr_to_quarks(float(amount_qsr))
    if amount_quarks <= 0:
        print("Amount must be positive.")
        return
    nonce = random.getrandbits(63)
    tx = FounderClaimTransaction(bc.founder_address, amount_quarks, nonce)
    ok, msg = bc.add_transaction(tx)
    if ok:
        bc.save()
        print(f"Founder claim created: {tx.tx_hash()}")
        print(f"  {float(amount_qsr):,.8f} QSR -> founder {bc.founder_address}")
        print(f"  Status: {msg} (mine a block to confirm)")
    else:
        print("Founder claim rejected:", msg)


def cmd_mempool():
    bc = Blockchain.load()
    print(f"Mempool: {len(bc.mempool)} pending transaction(s)")
    for tx in bc.mempool:
        ins = sum(bc.utxo_lookup(i.prev_tx_hash, i.prev_output_index)[1]
                  for i in tx.inputs)
        outs = sum(o.amount_quarks for o in tx.outputs)
        print(f"  {tx.tx_hash()[:16]}... in={ins/QUARKS_PER_QSR:.4f} "
              f"out={outs/QUARKS_PER_QSR:.4f} fee={(ins-outs)/QUARKS_PER_QSR:.8f}")


def cmd_info():
    bc = Blockchain.load()
    i = bc.info()
    print(BANNER)
    print(f"""
  Chain height:      {i['height']}  ({i['blocks']} blocks)
  Difficulty:        {'0' * i['difficulty']} ({i['difficulty']} leading zeros)
  Tip hash:          {i['tip_hash'][:24]}...
  Total mined:       {i['mined_qsr']:,.2f} QSR
  Remaining:         {i['remaining_qsr']:,.2f} QSR
  Max supply:        {i['max_supply_qsr']:,} QSR
  Next block reward: {i['next_reward_qsr']:,.2f} QSR
  Mempool:           {i['mempool_txs']} tx(s)
  UTXOs tracked:     {i['utxos']}
  Founder:           {i['founder_address'] or '(none)'}
  Founder claimed:   {i['founder_claimed_qsr']:,.2f} QSR
  Founder unlocked:  {i['founder_unlocked_qsr']:,.2f} QSR
  Founder remaining: {i['founder_remaining_qsr']:,.2f} QSR
""")


def cmd_validate():
    bc = Blockchain.load()
    print("Validating full chain (hashes, links, PoW, signatures, double-spends)...")
    ok, msg = bc.validate_chain()
    print(("VALID  " if ok else "INVALID") + f": {msg}")


def cmd_start_node(argv):
    """start-node [--port N] [--datadir PATH] [--seed host:port ...]
    [--founder <address>] [--mine-auto <wallet>]"""
    port = 9333
    datadir = None
    seeds = []
    founder = ""
    mine_auto_wallet = ""
    i = 2
    while i < len(argv):
        if argv[i] == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
            i += 2
        elif argv[i] == "--datadir" and i + 1 < len(argv):
            datadir = argv[i + 1]
            i += 2
        elif argv[i] == "--seed" and i + 1 < len(argv):
            seeds.append(argv[i + 1])
            i += 2
        elif argv[i] == "--founder" and i + 1 < len(argv):
            founder = argv[i + 1]
            i += 2
        elif argv[i] == "--mine-auto" and i + 1 < len(argv):
            mine_auto_wallet = argv[i + 1]
            i += 2
        else:
            i += 1
    if datadir:
        # Must be set before Blockchain.load() / Wallet ops read it.
        os.environ["QUASAR_DATA_DIR"] = os.path.abspath(datadir)
        os.makedirs(os.environ["QUASAR_DATA_DIR"], exist_ok=True)
    from p2p import start_node, DEFAULT_PORT  # lazy: keeps plain CLI fast
    print(BANNER)
    print(f"\nStarting P2P node on port {port} "
          f"(data: {os.environ.get('QUASAR_DATA_DIR', 'default')}) ...")
    if founder:
        print(f"Founder address for fresh genesis: {founder}")
    if mine_auto_wallet:
        print(f"Auto-mining to wallet '{mine_auto_wallet}' on start.")
    start_node(port=port or DEFAULT_PORT, seeds=seeds or None,
               founder_address=founder, mine_auto_wallet=mine_auto_wallet)


def cmd_mine_prototype(argv):
    """mine-prototype [--mode eco|balanced|performance] [--blocks N]
    [--difficulty N] [--threads N] [--max-seconds S]
    [--temp-limit C] --i-consent
    Stage-1 LOCAL mining prototype. Test coins only, no network,
    no value. Refuses to run without explicit --i-consent.
    (Additive wiring: does not touch any existing CLI command.)
    """
    import mining_prototype as mp
    rest = argv[2:]
    if "--i-consent" not in rest:
        print("REFUSED: mining needs explicit owner consent.")
        print("Re-run with --i-consent to start the miner.")
        return
    mp.run_cli(["--mine"] + [a for a in rest if a != "--i-consent"]
               + ["--i-consent"])


def cmd_mine_benchmark():
    """mine-benchmark — benchmark the prototype puzzle in all modes."""
    import mining_prototype as mp
    mp.print_benchmark(mp.benchmark_modes())


def usage():
    print(__doc__)
    print("Wallets:", ", ".join(Wallet.list_names()) or "(none yet)")


def main(argv):
    if len(argv) < 2:
        usage()
        return
    cmd = argv[1]
    try:
        if cmd == "start-node":
            cmd_start_node(argv)
        elif cmd in ("add-peer", "peers"):
            print("Run 'python3 quasar_cli.py start-node' first, then use "
                  "add-peer / peers inside its interactive console.")
        elif cmd == "new-address" and len(argv) == 3:
            cmd_new_address(argv[2])
        elif cmd == "balance" and len(argv) == 3:
            cmd_balance(argv[2])
        elif cmd == "mine" and len(argv) >= 3:
            diff = None
            if "--difficulty" in argv:
                diff = int(argv[argv.index("--difficulty") + 1])
            cmd_mine(argv[2], diff)
        elif cmd == "mine-auto" and len(argv) >= 3:
            count = None
            if len(argv) >= 4:
                try:
                    count = int(argv[3])
                except ValueError:
                    print("count must be a whole number")
                    return
                if count <= 0:
                    print("count must be positive")
                    return
            cmd_mine_auto(argv[2], count)
        elif cmd == "claim-founder" and len(argv) == 3:
            cmd_claim_founder(argv[2])
        elif cmd == "mine-prototype":
            cmd_mine_prototype(argv)
        elif cmd == "mine-benchmark":
            cmd_mine_benchmark()
        elif cmd == "send" and len(argv) == 5:
            cmd_send(argv[2], argv[3], argv[4])
        elif cmd == "mempool":
            cmd_mempool()
        elif cmd == "info":
            cmd_info()
        elif cmd == "validate":
            cmd_validate()
        else:
            usage()
    except FileNotFoundError as e:
        print(f"Error: {e} (did you create the wallet with new-address first?)")
    except Exception as e:  # noqa: BLE001 - CLI should never crash cryptically
        print(f"Error: {e}")


if __name__ == "__main__":
    main(sys.argv)
