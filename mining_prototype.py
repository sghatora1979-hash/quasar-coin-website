#!/usr/bin/env python3
"""
Quasar Coin — Stage 1 LOCAL MINING PROTOTYPE.

PROTOTYPE / TEST COINS ONLY. No monetary value. No guaranteed earnings.
Performance figures are DESIGN TARGETS, not benchmarks — actual speed
depends on CPU, memory bandwidth, OS, cooling, and electricity use.

What this is
-----------
A local, single-machine proof-of-work prototype that lets anyone test
laptop-friendly mining with explicit consent. It solves local test
challenges only — there is NO network, NO testnet, NO production chain
here (Stage 2 testnet and Stage 3 production are NOT built yet).

Puzzle: memory-hard PoW via ``hashlib.scrypt`` (stdlib, established KDF).
------------------------------------------------------------------------
IMPORTANT — READ THIS: this prototype uses scrypt as a STAND-IN for
memory-hard proof-of-work. It is NOT RandomX. The production design
should EVALUATE native RandomX (reference implementation: fast mode
~2,080 MiB shared memory, light mode ~256 MiB) later, after review.
Do not claim this prototype is RandomX, and do not trust a currency
to a home-grown algorithm invented for this prototype.

Why memory-hard: each hash attempt allocates a large scratchpad
(256 MiB–1 GiB depending on mode), which reduces the advantage of
specialized mining hardware (ASICs) and keeps ordinary CPUs competitive.

DISTRIBUTION (see supply.py): 400B QSR via mining rewards under the
published schedule, PLUS one transparent FOUNDER ALLOCATION of 100B
QSR (20% of cap) that unlocks linearly over ONE WEEK (20,160 blocks). The
founder allocation is the ONLY non-mining issuance, and it is
enforced by consensus vesting — no other allocation, reserve, or
side path exists.

NO PRICE OR VALUE TARGETS: nothing in this prototype states or
implies any price, value, or market outcome. Test coins have no
monetary value. Any "what if $1/QSR" arithmetic is math only,
never a forecast or a promise.

NO RAM BONUS
------------
A block's reward is IDENTICAL on every machine — it comes only from
the consensus schedule (see supply.py). RAM/CPU only set what
resources the miner is ALLOWED to use within the owner's limits:
a 64 GB machine earns exactly the same per accepted block as an
8 GB machine. Rewarding RAM directly would encourage buying hardware
instead of contributing verified work.

HASHRATE SETS SPEED / SHARE — NOT REWARD PER BLOCK
--------------------------------------------------
A miner's hashrate (set by its CPU/RAM) determines how FAST it finds
blocks: alone on the network it wins 100% of blocks; competing, its
expected share = its own hashrate / total network hashrate. A bigger
machine therefore mines MORE — but only by winning a bigger share of
the same scheduled blocks, never by changing what a block pays.

NO INTERNET-SPEED FACTOR
------------------------
Internet speed does NOT affect PoW earnings: it only affects how
fast a solved block propagates to peers (milliseconds). No
internet-speed factor exists in this puzzle, and none may be added
— such a factor would be dishonest and trivially gameable.

DIFFICULTY ADJUSTMENT STAYS
---------------------------
Difficulty retargets toward the 30-second block time (see
retarget_difficulty). It is what protects the 400B schedule from
being mined out in days by large farms: without it, 10,000 machines
could exhaust the supply almost immediately and drown the chain in
blocks nobody could sync or verify.

PUZZLE STAYS MEMORY-HARD
------------------------
The puzzle stays memory-hard (scrypt stand-in; RandomX to be
evaluated for production). No switch to a SHA-256-like puzzle: that
would let ASICs dominate and kill laptop-first mining. Bigger
machines still mine more under memory-hard PoW (hashrate -> share);
memory-hardness only narrows the gap so laptops stay competitive.

Modes (resource limits, not rewards)
------------------------------------
* eco:         ~256 MiB/hash, 1-2 threads — leaves headroom for
               normal tasks. Design target: 8 GB RAM machines.
* balanced:    ~512 MiB/hash, 2 threads. Design target: 16-32 GB.
* performance: ~1 GiB/hash, up to 4 threads (bounded by user limits).
               Design target: 64 GB+ machines.

Consent & safety
----------------
* The miner REFUSES to run without explicit owner consent
  (PrototypeMiner(consent=True) / CLI --i-consent).
* Pause/resume, user-set thread/memory/runtime limits, and a
  best-effort CPU-temperature safeguard (psutil if available,
  otherwise gracefully disabled — never a crash).
* No hidden mining: nothing here runs without being started
  explicitly, and nothing installs itself anywhere.
* Energy numbers are ROUGH ESTIMATES (CPU time x assumed watts),
  not measurements. Continuous mining causes heat, fan noise,
  electricity cost, and battery wear. A browser tab is NOT a
  dependable 24/7 mining service.

Usage
-----
    python3 mining_prototype.py --benchmark
    python3 mining_prototype.py --mine --mode eco --blocks 2 --i-consent
    python3 quasar_cli.py mine-prototype --mode balanced --blocks 2 --i-consent
    python3 quasar_cli.py mine-benchmark
"""

import argparse
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from supply import (QUARKS_PER_QSR, block_reward_quarks,  # noqa: E402
                    validate_block_reward)

# --------------------------------------------------------------------------
# Modes: resource limits ONLY. Never rewards.
# --------------------------------------------------------------------------

# scrypt memory per hash attempt = 128 * n * r bytes.
#   eco:         128 * 2**18 * 8 = 256 MiB
#   balanced:    128 * 2**19 * 8 = 512 MiB
#   performance: 128 * 2**20 * 8 = 1 GiB
MODES = {
    "eco": {
        "label": "Eco",
        "scrypt_n": 2 ** 18, "scrypt_r": 8, "scrypt_p": 1,
        "threads": 1, "assumed_watts": 15,
        "desc": "Low memory + 1-2 threads. Leaves headroom for normal tasks.",
    },
    "balanced": {
        "label": "Balanced",
        "scrypt_n": 2 ** 19, "scrypt_r": 8, "scrypt_p": 1,
        "threads": 2, "assumed_watts": 45,
        "desc": "Medium memory + 2 threads.",
    },
    "performance": {
        "label": "Performance",
        "scrypt_n": 2 ** 20, "scrypt_r": 8, "scrypt_p": 1,
        "threads": 4, "assumed_watts": 90,
        "desc": "Higher memory + more threads (bounded by user-set limits).",
    },
}

# DESIGN TARGETS only — never a performance guarantee.
RAM_TIER_TARGETS = {
    "8 GB": "Eco recommended",
    "16-32 GB": "Standard (Balanced) recommended",
    "64 GB+": "High-Capacity (Performance) allowed — reward unchanged",
}

DEFAULT_TEMP_LIMIT_C = 85.0


def scrypt_memory_mib(n: int, r: int) -> float:
    """Scratchpad memory (MiB) one scrypt hash attempt needs."""
    return 128 * n * r / (1024 * 1024)


def detect_total_ram_gb():
    """Best-effort total RAM in GiB. Returns None if undetectable."""
    try:
        import psutil  # optional
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return None


def suggested_mode_for_ram(total_ram_gb):
    """Design-target suggestion only — never a reward, never a guarantee."""
    if total_ram_gb is None:
        return "eco"
    if total_ram_gb < 12:
        return "eco"
    if total_ram_gb < 48:
        return "balanced"
    return "performance"


# --------------------------------------------------------------------------
# Puzzle: solve() / verify()
# --------------------------------------------------------------------------

def encode_challenge(challenge: dict) -> bytes:
    """Canonical byte encoding of a challenge (deterministic)."""
    canon = "|".join([
        str(challenge.get("prev_hash", "0" * 64)),
        str(challenge.get("height", 0)),
        str(challenge.get("difficulty_bits", 0)),
        str(challenge.get("tag", "quasar-prototype")),
        str(challenge.get("timestamp", 0)),
    ])
    return canon.encode("utf-8")


def target_for_bits(difficulty_bits: int) -> int:
    """Numeric target: proof must be < 2**(256 - bits)."""
    if not 0 <= difficulty_bits <= 256:
        raise ValueError("difficulty_bits must be in [0, 256]")
    return 1 << (256 - difficulty_bits)


def _scrypt_maxmem(n: int, r: int) -> int:
    """OpenSSL maxmem for scrypt params: scratchpad + 64 MiB slack,
    capped below 2**31 (OpenSSL requires maxmem < 2147483647)."""
    return min(128 * n * r + (64 * 1024 * 1024), 2 ** 31 - 1)


def _scrypt_once(challenge_bytes: bytes, nonce: int,
                 n: int, r: int, p: int) -> bytes:
    """One memory-hard hash attempt. Deterministic for (challenge, nonce)."""
    nonce_bytes = nonce.to_bytes(8, "big")
    # OpenSSL enforces a maxmem cap; size it from the actual params.
    maxmem = _scrypt_maxmem(n, r)
    return hashlib.scrypt(
        password=challenge_bytes + nonce_bytes,
        salt=challenge_bytes,
        n=n, r=r, p=p, dklen=32, maxmem=maxmem,
    )


def solve(challenge: dict, difficulty_bits: int, *,
          scrypt_params: dict | None = None,
          max_attempts: int = 1_000_000,
          start_nonce: int = 0, nonce_step: int = 1,
          stop_event: threading.Event | None = None):
    """Search for a nonce whose proof beats the difficulty target.

    Returns (nonce, proof_hex) on success, or None if not found
    (attempts exhausted / stopped). Independent of any miner state.
    """
    params = scrypt_params or MODES["eco"]
    n, r, p = params["scrypt_n"], params["scrypt_r"], params["scrypt_p"]
    cb = encode_challenge(challenge)
    target = target_for_bits(difficulty_bits)
    nonce = start_nonce
    for _ in range(max_attempts):
        if stop_event is not None and stop_event.is_set():
            return None
        proof = _scrypt_once(cb, nonce, n, r, p)
        if int.from_bytes(proof, "big") < target:
            return nonce, proof.hex()
        nonce += nonce_step
    return None


def verify(challenge: dict, difficulty_bits: int, nonce: int,
           proof_hex: str, *, scrypt_params: dict | None = None) -> bool:
    """INDEPENDENT verification: recompute and compare.

    Rejects wrong nonces, wrong proofs, and any tampered challenge
    (changing any challenge field changes the recomputed proof).
    """
    try:
        params = scrypt_params or MODES["eco"]
        n, r, p = params["scrypt_n"], params["scrypt_r"], params["scrypt_p"]
        cb = encode_challenge(challenge)
        expected = _scrypt_once(cb, nonce, n, r, p)
        if expected.hex() != proof_hex.lower():
            return False
        return int.from_bytes(expected, "big") < target_for_bits(difficulty_bits)
    except Exception:
        return False


def retarget_difficulty(prev_bits: int, actual_seconds_per_block: float,
                        target_seconds: float = 60.0,
                        min_bits: int = 0, max_bits: int = 24) -> int:
    """Simple retarget helper: +/-1 bit per block, clamped.

    Blocks too fast -> harder; too slow -> easier. A production
    network would use a smoother, multi-block retarget (e.g. Bitcoin's
    2016-block window); this single-step helper is for the prototype.
    """
    if actual_seconds_per_block <= 0 or target_seconds <= 0:
        return prev_bits
    if actual_seconds_per_block < target_seconds * 0.5:
        return min(prev_bits + 1, max_bits)
    if actual_seconds_per_block > target_seconds * 2.0:
        return max(prev_bits - 1, min_bits)
    return prev_bits


# --------------------------------------------------------------------------
# Miner
# --------------------------------------------------------------------------

class PrototypeMiner:
    """Local test-challenge miner. No network. Test coins only.

    Requires explicit owner consent: PrototypeMiner(consent=True).
    Without it, construction raises ValueError and nothing runs.
    """

    def __init__(self, mode: str = "eco", *, consent: bool = False,
                 threads: int | None = None, max_seconds: float | None = None,
                 temp_limit_c: float = DEFAULT_TEMP_LIMIT_C,
                 scrypt_params: dict | None = None,
                 target_seconds_per_block: float = 60.0):
        if not consent:
            raise ValueError(
                "Explicit owner consent required: pass consent=True "
                "(CLI: --i-consent). The miner refuses to run otherwise."
            )
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; choose {sorted(MODES)}")
        self.mode = mode
        self.params = dict(scrypt_params or MODES[mode])
        self.threads = max(1, threads or MODES[mode]["threads"])
        self.max_seconds = max_seconds
        self.temp_limit_c = temp_limit_c
        self.target_seconds_per_block = target_seconds_per_block
        # State / stats
        self._pause_event = threading.Event()   # set = paused
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.attempts = 0
        self.accepted = 0
        self.rejected = 0
        self.confirmed_test_qsr = 0.0
        self.blocks = []  # accepted test blocks (local only)
        self.safeguard_trips = 0
        self.safeguard_available = False
        self._cpu_start = None
        self.started_at = None
        self._check_temperature_support()

    # -- safeguards -------------------------------------------------------
    def _check_temperature_support(self):
        try:
            import psutil  # optional
            self._psutil = psutil
            self.safeguard_available = hasattr(psutil, "sensors_temperatures")
        except Exception:
            self._psutil = None
            self.safeguard_available = False

    def _temperature_c(self):
        """Best-effort max CPU temp, or None if unsupported."""
        if not self.safeguard_available:
            return None
        try:
            temps = self._psutil.sensors_temperatures() or {}
            vals = [e.current for group in temps.values() for e in group
                    if e.current is not None]
            return max(vals) if vals else None
        except Exception:
            return None

    def _maybe_thermal_pause(self):
        temp = self._temperature_c()
        if temp is not None and temp > self.temp_limit_c:
            if not self._pause_event.is_set():
                self.safeguard_trips += 1
            self._pause_event.set()
            return True
        return False

    # -- controls ---------------------------------------------------------
    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    @property
    def paused(self) -> bool:
        return self._pause_event.is_set()

    def stop(self):
        self._stop_event.set()
        self.resume()  # unblock workers waiting in pause

    # -- stats ------------------------------------------------------------
    def stats(self) -> dict:
        elapsed = (time.time() - self.started_at) if self.started_at else 0.0
        cpu_seconds = 0.0
        if self._cpu_start is not None:
            cpu_seconds = max(0.0, time.process_time() - self._cpu_start)
        assumed_watts = MODES[self.mode]["assumed_watts"]
        # ROUGH ESTIMATE from CPU time x assumed watts — NOT a measurement.
        energy_kwh = cpu_seconds * assumed_watts / 3_600_000.0
        return {
            "mode": self.mode,
            "hashrate_h_s": self.attempts / elapsed if elapsed > 0 else 0.0,
            "attempts": self.attempts,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "confirmed_test_qsr": round(self.confirmed_test_qsr, 8),
            "estimated_energy_kwh_rough": round(energy_kwh, 6),
            "energy_note": "ROUGH estimate (CPU time x assumed watts), not a measurement",
            "elapsed_s": round(elapsed, 1),
            "safeguard_available": self.safeguard_available,
            "safeguard_trips": self.safeguard_trips,
            "paused": self.paused,
        }

    # -- mining -----------------------------------------------------------
    def _worker(self, challenge, difficulty_bits, worker_id, result):
        """One thread: search nonces worker_id, +threads, ..."""
        nonce = worker_id
        cb = encode_challenge(challenge)
        n = self.params["scrypt_n"]
        r = self.params["scrypt_r"]
        p = self.params["scrypt_p"]
        target = target_for_bits(difficulty_bits)
        while not self._stop_event.is_set():
            while self._pause_event.is_set() and not self._stop_event.is_set():
                time.sleep(0.05)
            if self._stop_event.is_set():
                return
            self._maybe_thermal_pause()
            if self._pause_event.is_set():
                continue
            proof = _scrypt_once(cb, nonce, n, r, p)
            with self._lock:
                self.attempts += 1
            if int.from_bytes(proof, "big") < target:
                with self._lock:
                    if result.get("found") is None:
                        result["found"] = (nonce, proof.hex())
                        self._found_event.set()
                return
            nonce += self.threads

    def mine_blocks(self, max_blocks: int = 1, difficulty_bits: int = 4,
                    *, verbose: bool = False):
        """Mine up to max_blocks local test blocks (no network).

        Each accepted block is independently verified via verify() and
        its reward checked via supply.validate_block_reward() before
        any test QSR is credited. A failed verification counts as
        rejected work and is never credited.
        """
        self._found_event = threading.Event()
        self.started_at = time.time()
        self._cpu_start = time.process_time()
        deadline = (self.started_at + self.max_seconds) if self.max_seconds else None
        prev_hash = "0" * 64
        height = 0
        bits = difficulty_bits
        mined = []
        for _ in range(max_blocks):
            if self._stop_event.is_set():
                break
            if deadline and time.time() > deadline:
                break
            challenge = {"prev_hash": prev_hash, "height": height,
                         "difficulty_bits": bits, "tag": "quasar-prototype",
                         "timestamp": int(time.time())}
            self._found_event.clear()
            result = {"found": None}
            block_t0 = time.time()
            with ThreadPoolExecutor(max_workers=self.threads) as pool:
                futures = [pool.submit(self._worker, challenge, bits, w, result)
                           for w in range(self.threads)]
                while not self._found_event.wait(timeout=0.2):
                    if self._stop_event.is_set():
                        break
                    if deadline and time.time() > deadline:
                        self.stop()
                        break
                # Workers exit on their own (found / stopped); join them.
                for f in futures:
                    try:
                        f.result(timeout=120)
                    except Exception:
                        pass
            if result["found"] is None:
                break  # stopped / timed out / no solution
            nonce, proof_hex = result["found"]
            # INDEPENDENT verification before crediting anything.
            ok = verify(challenge, bits, nonce, proof_hex,
                        scrypt_params=self.params)
            if not ok:
                with self._lock:
                    self.rejected += 1
                continue
            # Exact integer-quark accounting (no float round-trip).
            reward_quarks = block_reward_quarks(height)
            reward = reward_quarks / QUARKS_PER_QSR
            total_so_far = sum(block_reward_quarks(b["height"])
                               for b in self.blocks)
            valid, reason = validate_block_reward(
                reward_quarks, height, total_so_far)
            if not valid:
                with self._lock:
                    self.rejected += 1
                if verbose:
                    print(f"  Block {height} rejected by supply rules: {reason}")
                continue
            with self._lock:
                self.accepted += 1
                self.confirmed_test_qsr += reward
            block = {"height": height, "nonce": nonce, "proof": proof_hex,
                     "prev_hash": prev_hash, "difficulty_bits": bits,
                     "reward_qsr": reward}
            self.blocks.append(block)
            mined.append(block)
            if verbose:
                print(f"  Block {height} accepted: nonce={nonce} "
                      f"reward={reward} test-QSR")
            prev_hash = proof_hex
            height += 1
            # Simple per-block retarget toward the target block time.
            bits = retarget_difficulty(bits, time.time() - block_t0,
                                       self.target_seconds_per_block)
        return mined


# --------------------------------------------------------------------------
# Benchmark
# --------------------------------------------------------------------------

def benchmark_modes(attempts_per_mode: int = 2, *,
                    test_params: dict | None = None):
    """Run the puzzle in each mode; return a list of result rows.

    test_params (optional): override scrypt params (e.g. tiny values
    in unit tests) so a smoke run stays fast on any machine.
    """
    rows = []
    for mode, spec in MODES.items():
        params = dict(test_params or spec)
        n, r, p = params["scrypt_n"], params["scrypt_r"], params["scrypt_p"]
        challenge = {"prev_hash": "0" * 64, "height": 0,
                     "difficulty_bits": 0, "tag": "benchmark",
                     "timestamp": 0}
        cb = encode_challenge(challenge)
        t0 = time.time()
        cpu0 = time.process_time()
        for i in range(attempts_per_mode):
            _scrypt_once(cb, i, n, r, p)
        dt = max(time.time() - t0, 1e-9)
        cpu_s = max(time.process_time() - cpu0, 0.0)
        rows.append({
            "mode": mode,
            "memory_mib_per_hash": round(scrypt_memory_mib(n, r), 1),
            "threads_default": spec["threads"],
            "attempts": attempts_per_mode,
            "seconds": round(dt, 2),
            "hashes_per_sec": round(attempts_per_mode / dt, 2),
            "cpu_seconds": round(cpu_s, 2),
            # ROUGH estimate, not a measurement.
            "est_energy_kwh_rough": round(
                cpu_s * spec["assumed_watts"] / 3_600_000.0, 6),
        })
    return rows


def print_benchmark(rows):
    print("Quasar mining prototype — benchmark (DESIGN TARGETS, not benchmarks)")
    print("Each row = attempts in that mode on THIS machine, right now.")
    hdr = (f"{'mode':<12}{'MiB/hash':>10}{'threads':>9}{'attempts':>10}"
           f"{'seconds':>10}{'H/s':>10}{'est kWh*':>12}")
    print(hdr)
    print("-" * len(hdr))
    for row in rows:
        print(f"{row['mode']:<12}{row['memory_mib_per_hash']:>10.1f}"
              f"{row['threads_default']:>9}{row['attempts']:>10}"
              f"{row['seconds']:>10.2f}{row['hashes_per_sec']:>10.2f}"
              f"{row['est_energy_kwh_rough']:>12.6f}")
    print("* est kWh = ROUGH estimate (CPU time x assumed watts), not a measurement.")


# --------------------------------------------------------------------------
# CLI entry point (also wired into quasar_cli.py)
# --------------------------------------------------------------------------

def run_cli(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mining_prototype",
        description="Quasar Coin Stage-1 LOCAL mining prototype. "
                    "Test coins only — NO monetary value, NO guaranteed earnings. "
                    "Requires explicit owner consent (--i-consent) to mine.")
    parser.add_argument("--benchmark", action="store_true",
                        help="Run the puzzle in each mode and print a table.")
    parser.add_argument("--mine", action="store_true",
                        help="Mine local test blocks (no network).")
    parser.add_argument("--mode", choices=sorted(MODES), default="eco",
                        help="Resource limits only — NEVER affects reward.")
    parser.add_argument("--blocks", type=int, default=1,
                        help="Max test blocks to mine (default 1).")
    parser.add_argument("--difficulty", type=int, default=4,
                        help="Leading-zero bits for demo blocks (default 4).")
    parser.add_argument("--threads", type=int, default=None,
                        help="Worker threads (default: mode default).")
    parser.add_argument("--max-seconds", type=float, default=None,
                        help="Stop mining after this many seconds.")
    parser.add_argument("--temp-limit", type=float, default=DEFAULT_TEMP_LIMIT_C,
                        help="Auto-pause above this CPU temp in C (psutil only).")
    parser.add_argument("--i-consent", action="store_true",
                        help="REQUIRED for --mine: explicit owner consent.")
    args = parser.parse_args(argv)

    if args.benchmark:
        print_benchmark(benchmark_modes())
        return 0
    if args.mine:
        if not args.i_consent:
            print("REFUSED: mining needs explicit owner consent.")
            print("Re-run with --i-consent to start the miner.")
            return 2
        ram = detect_total_ram_gb()
        print("Quasar mining prototype — LOCAL TEST ONLY, test coins, no value.")
        print(f"  Mode: {args.mode} (suggested for this machine: "
              f"{suggested_mode_for_ram(ram)}; detected RAM: "
              f"{ram:.1f} GiB" if ram else "  Mode: {args.mode} (RAM undetected)")
        print(f"  Reward per accepted block is the SAME in every mode "
              f"(NO RAM bonus).")
        miner = PrototypeMiner(
            args.mode, consent=True, threads=args.threads,
            max_seconds=args.max_seconds, temp_limit_c=args.temp_limit,
        )
        print(f"  Temp safeguard: "
              f"{'available' if miner.safeguard_available else 'unavailable (psutil/sensors missing — degrading gracefully)'}")
        print("  Mining... Ctrl+C to stop (pause: not available in this simple CLI run).")
        try:
            miner.mine_blocks(max_blocks=args.blocks,
                              difficulty_bits=args.difficulty, verbose=True)
        except KeyboardInterrupt:
            miner.stop()
            print("\nStopped by user.")
        print("  Stats:", json.dumps(miner.stats(), indent=2))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())
