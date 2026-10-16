#!/usr/bin/env python3
"""
Quasar Coin — Supply rules (Stage 2 mining).

PROTOTYPE / TEST COINS ONLY. No monetary value. No guaranteed earnings.
The numbers below are the founder-approved parameters for the permanent
chain (decided 2026-10-14). They are consensus rules: every node must
run validate_block_reward() / validate_founder_claim() and reject
anything beyond the schedule, the vesting, or the cap.

Supply split (hard cap 500,000,000,000 QSR)
------------------------------------------
* MINING BUDGET: 400,000,000,000 QSR ceiling — earned ONLY through
  mining rewards under the block-reward schedule below. The schedule
  actually emits 398,617,500,000 QSR (see math proof); the remaining
  ~1.38B of the budget is never created.
* FOUNDER ALLOCATION: 100,000,000,000 QSR (20% of cap) — a separate,
  transparent genesis allocation, NOT mined. It unlocks linearly over
  ONE WEEK (see founder_unlocked_quarks). Nodes must reject any
  founder claim beyond the scheduled unlocked amount.
* Combined actual: 398,617,500,000 mined + 100,000,000,000 founder
  = 498,617,500,000 QSR — below the 500B hard cap.

Block-reward schedule (founder directive 2026-10-14)
----------------------------------------------------
* Phase 1: 50,000 QSR/block for 6,000,000 blocks (~5.7 years at the
  30-second target) = 300,000,000,000 QSR.
* Phase 2 (halving 1): 25,000 QSR/block for 2,629,800 blocks
  (2.5 years) = 65,745,000,000 QSR.
* Phase 3 (halving 2): 12,500 QSR/block for 2,629,800 blocks
  (2.5 years) = 32,872,500,000 QSR.
* Then STOP: every block at height >= 11,259,600 pays 0.
* Total mined = 398,617,500,000 QSR over 11,259,600 reward blocks
  (~10.7 years of mining at the 30-second target).

WHY THIS SHAPE: the founder rejected both endless timelines and
flat-forever rewards. Halving is triggered by BLOCK HEIGHT (coins
mined), never by calendar date: more miners do NOT finish the 300B
faster — difficulty holds ~30-second blocks, so the timeline is
fixed and extra miners only split the same reward. The two halvings
are hard-coded eras, not an infinite geometric series: after phase 3
the reward is 0, permanently.

MATH PROOF — schedule sums to EXACTLY 398,617,500,000 QSR
--------------------------------------------------------
Phase 1: 6,000,000 x 5,000,000,000,000 quarks
       = 30,000,000,000,000,000,000 quarks = 300,000,000,000 QSR
Phase 2: 2,629,800 x 2,500,000,000,000 quarks
       = 6,574,500,000,000,000,000 quarks = 65,745,000,000 QSR
Phase 3: 2,629,800 x 1,250,000,000,000 quarks
       = 3,287,250,000,000,000,000 quarks = 32,872,500,000 QSR
Total  = 39,861,750,000,000,000,000 quarks
       = EXACTLY 398,617,500,000 QSR (< 400B budget ceiling).

Per-era mining emission (30s blocks)
-----------------------------------
Phase 1 (~5.7 yrs): 300,000,000,000 QSR mined (cumulative 300B)
Phase 2 (2.5 yrs):   65,745,000,000 QSR mined (cumulative 365.745B)
Phase 3 (2.5 yrs):   32,872,500,000 QSR mined (cumulative 398.6175B)
Then mining rewards stop forever at height 11,259,600.

* NO RAM BONUS. A block's reward depends ONLY on its height and the
  schedule. A 64 GB machine earns exactly the same reward per accepted
  block as an 8 GB machine. RAM/CPU only set what resources the miner
  is allowed to use (see mining_prototype.py MODES).
* HASHRATE SETS SPEED / SHARE — NOT REWARD PER BLOCK. A miner's
  hashrate (set by its CPU/RAM) determines how FAST it finds blocks:
  alone on the network it wins 100% of blocks; competing, its expected
  share = its own hashrate / total network hashrate. It never changes
  the reward a block pays — that comes only from the schedule.
* NO INTERNET-SPEED FACTOR. Internet speed does NOT affect PoW
  earnings: it only affects how fast a solved block propagates to
  peers (milliseconds). No internet-speed factor exists in the
  puzzle, and none may be added — such a factor would be dishonest
  and trivially gameable.
* DIFFICULTY ADJUSTMENT STAYS. Difficulty retargets toward the
  30-second block time. It is what keeps the phase timelines fixed no
  matter how many miners join: without it, 10,000 machines could
  exhaust a phase almost immediately and drown the chain in blocks
  nobody could sync or verify.
* NO HIDDEN ISSUANCE. There is no function in this module — or in
  mining_prototype.py — that creates coins outside (a) the mining
  schedule above or (b) the single disclosed founder allocation with
  vesting below. Every node must independently run
  validate_block_reward() / validate_founder_claim() and reject
  anything beyond the schedule, the vesting, or the cap.

FOUNDER ALLOCATION (transparent, 1-WEEK vesting)
----------------------------------------------
* FOUNDER_TOTAL_QSR = 100,000,000,000 (100 billion QSR, 20% of cap).
* Unlock: linear over ONE WEEK, measured in blocks at the 30-second
  target: VESTING_BLOCKS = 7 x 24 x 120 = 20,160 blocks
  (founder directive 2026-10-14: "one week, that's it").
  At height h, unlocked = FOUNDER_TOTAL x h // VESTING_BLOCKS
  (capped at FOUNDER_TOTAL). Block height is the vesting clock —
  deterministic, no timestamp trust.
* A founder claim is valid only if claimed_so_far + claim <= unlocked.
  Claims are cumulative; the total can never exceed 100B. Claims are
  MANUAL (claim-founder) — no founder reward is paid automatically
  on mining blocks.
* After launch the schedule is consensus and cannot be changed by
  any party.

(Scope: this rule governs the mining chain. The older, separate
staking.py tap/staking demo has its own demo-coin logic and is NOT
part of coin distribution — it must never be wired into the mining
chain.)

Units: 1 QSR = 100,000,000 quarks (8 decimals), matching transactions.py.
"""

MAX_SUPPLY_QSR = 500_000_000_000          # 500 billion QSR hard cap
QUARKS_PER_QSR = 100_000_000               # 8-decimal "quark" units

# --- Split of the cap -------------------------------------------------
MINING_BUDGET_QSR = 400_000_000_000        # ceiling; schedule emits less
FOUNDER_TOTAL_QSR = 100_000_000_000        # transparent founder allocation

# --- Mining schedule (founder directive 2026-10-14) -------------------
# Phase 1: 300B @ 50,000 QSR/block
PHASE1_BLOCKS = 6_000_000                    # 300B / 50,000 per block
PHASE1_REWARD_QUARKS = 5_000_000_000_000     # exact: 50,000 QSR
# Phase 2: 25,000 QSR/block for 2.5 years
PHASE2_BLOCKS = 2_629_800                    # 2.5 x 365.25 x 24 x 120
PHASE2_REWARD_QUARKS = 2_500_000_000_000     # exact: 25,000 QSR
# Phase 3: 12,500 QSR/block for 2.5 years
PHASE3_BLOCKS = 2_629_800                    # 2.5 x 365.25 x 24 x 120
PHASE3_REWARD_QUARKS = 1_250_000_000_000     # exact: 12,500 QSR

# Phase boundary heights (first block of each phase / stop height).
PHASE1_END = PHASE1_BLOCKS                               # 6,000,000
PHASE2_END = PHASE1_BLOCKS + PHASE2_BLOCKS               # 8,629,800
PHASE3_END = PHASE2_END + PHASE3_BLOCKS                  # 11,259,600
TOTAL_REWARD_BLOCKS = PHASE3_END

# Exact total mined by the schedule (must be <= MINING_BUDGET_QUARKS).
SCHEDULED_EMISSION_QUARKS = (
    PHASE1_BLOCKS * PHASE1_REWARD_QUARKS
    + PHASE2_BLOCKS * PHASE2_REWARD_QUARKS
    + PHASE3_BLOCKS * PHASE3_REWARD_QUARKS
)
assert SCHEDULED_EMISSION_QUARKS == 39_861_750_000_000_000_000  # 398,617,500,000 QSR

# Aliases kept so existing callers using the INITIAL_REWARD names keep
# working: the "initial" reward is the phase-1 reward.
INITIAL_REWARD_QUARKS = PHASE1_REWARD_QUARKS
INITIAL_REWARD_QSR = INITIAL_REWARD_QUARKS / QUARKS_PER_QSR  # 50,000.0
TARGET_SECONDS_PER_BLOCK = 30.0            # target block time

# --- Founder vesting --------------------------------------------------
# Linear unlock over ONE WEEK, measured in blocks at the 30s target.
VESTING_BLOCKS = 20_160                     # 7 x 24 x 120 (founder directive 2026-10-14)

MAX_SUPPLY_QUARKS = MAX_SUPPLY_QSR * QUARKS_PER_QSR
MINING_BUDGET_QUARKS = MINING_BUDGET_QSR * QUARKS_PER_QSR
FOUNDER_TOTAL_QUARKS = FOUNDER_TOTAL_QSR * QUARKS_PER_QSR
assert SCHEDULED_EMISSION_QUARKS <= MINING_BUDGET_QUARKS
assert SCHEDULED_EMISSION_QUARKS + FOUNDER_TOTAL_QUARKS <= MAX_SUPPLY_QUARKS


def block_reward_quarks(height: int) -> int:
    """Scheduled MINING reward (in quarks) at a given block height.

    Pure function of height only — NOT of machine, RAM, hashrate, or
    who mined the block. Phase 1 pays 50,000 QSR, phase 2 pays
    25,000 QSR, phase 3 pays 12,500 QSR; every block at height >=
    TOTAL_REWARD_BLOCKS (11,259,600) pays 0 — mining stops forever.
    """
    if height < 0:
        raise ValueError("height must be >= 0")
    if height < PHASE1_END:
        return PHASE1_REWARD_QUARKS
    if height < PHASE2_END:
        return PHASE2_REWARD_QUARKS
    if height < PHASE3_END:
        return PHASE3_REWARD_QUARKS
    return 0


def block_reward_qsr(height: int) -> float:
    """Scheduled mining reward in QSR (convenience wrapper)."""
    return block_reward_quarks(height) / QUARKS_PER_QSR


def total_emission_quarks(num_blocks: int) -> int:
    """Total MINED QSR (in quarks) after mining blocks [0, num_blocks).

    Founder allocation is NOT included here — it is tracked separately
    via founder_unlocked_quarks() / validate_founder_claim(). Sums the
    three phases exactly. Used by tests to PROVE the mining emission:
    total emission over all heights must equal EXACTLY
    SCHEDULED_EMISSION_QUARKS (398,617,500,000 QSR).
    """
    if num_blocks < 0:
        raise ValueError("num_blocks must be >= 0")
    total = 0
    p1 = min(num_blocks, PHASE1_END)
    total += p1 * PHASE1_REWARD_QUARKS
    if num_blocks > PHASE1_END:
        p2 = min(num_blocks, PHASE2_END) - PHASE1_END
        total += p2 * PHASE2_REWARD_QUARKS
    if num_blocks > PHASE2_END:
        p3 = min(num_blocks, PHASE3_END) - PHASE2_END
        total += p3 * PHASE3_REWARD_QUARKS
    return total


def total_supply_quarks(num_blocks: int, founder_claimed_quarks: int) -> int:
    """Combined supply: mined emission + founder claims so far."""
    if founder_claimed_quarks < 0:
        raise ValueError("founder_claimed_quarks must be >= 0")
    return total_emission_quarks(num_blocks) + founder_claimed_quarks


def validate_block_reward(block_reward_quarks_: int, height: int,
                          mined_so_far_quarks: int):
    """Consensus check: does this block's mining reward follow the schedule?

    mined_so_far_quarks = MINED supply before this block (founder
    claims are tracked separately and do NOT count here).

    Returns (ok: bool, reason: str). A node MUST reject a block when:
      * the reward is negative,
      * the reward is anything other than exactly the scheduled reward
        for its height (over- or under-reward),
      * accepting it would push MINED supply past the 400B mining
        budget ceiling.

    Note: this helper checks the reward in isolation. Full block
    validation (PoW, signatures, double-spends) lives elsewhere.
    """
    if block_reward_quarks_ < 0:
        return False, "negative block reward"
    expected = block_reward_quarks(height)
    if block_reward_quarks_ != expected:
        return False, (
            f"reward {block_reward_quarks_} != scheduled {expected} "
            f"at height {height}"
        )
    if mined_so_far_quarks < 0:
        return False, "negative mined supply"
    if mined_so_far_quarks + block_reward_quarks_ > MINING_BUDGET_QUARKS:
        return False, "block would exceed 400B mining budget"
    return True, "ok"


def founder_unlocked_quarks(height: int) -> int:
    """Founder allocation unlocked (in quarks) at a given block height.

    Linear unlock over VESTING_BLOCKS (one week), capped at
    FOUNDER_TOTAL_QUARKS. Pure function of height. At height 0 nothing
    is unlocked; at height >= VESTING_BLOCKS the full 100B is unlocked.
    """
    if height < 0:
        raise ValueError("height must be >= 0")
    if height >= VESTING_BLOCKS:
        return FOUNDER_TOTAL_QUARKS
    return FOUNDER_TOTAL_QUARKS * height // VESTING_BLOCKS


def founder_unlocked_qsr(height: int) -> float:
    """Founder allocation unlocked in QSR (convenience wrapper)."""
    return founder_unlocked_quarks(height) / QUARKS_PER_QSR


def validate_founder_claim(height: int, claim_quarks: int,
                           already_claimed_quarks: int):
    """Consensus check: is this founder claim within the vesting schedule?

    Returns (ok: bool, reason: str). A node MUST reject a claim when:
      * the claim or already-claimed amount is negative,
      * already-claimed already exceeds what is unlocked at this height
        (should be impossible on a valid chain),
      * the claim would push cumulative claims past the unlocked amount,
      * the claim would push cumulative claims past the 100B total.

    Founder claims are cumulative and enforced by every node.
    """
    if claim_quarks < 0:
        return False, "negative founder claim"
    if already_claimed_quarks < 0:
        return False, "negative already-claimed amount"
    unlocked = founder_unlocked_quarks(height)
    if already_claimed_quarks > unlocked:
        return False, "already-claimed exceeds unlocked amount"
    if already_claimed_quarks + claim_quarks > unlocked:
        return False, "claim exceeds unlocked founder allocation"
    if already_claimed_quarks + claim_quarks > FOUNDER_TOTAL_QUARKS:
        return False, "claim exceeds 100B founder allocation total"
    return True, "ok"


def validate_combined_supply(mined_quarks: int,
                             founder_claimed_quarks: int):
    """Consensus check: does the combined supply respect the 500B cap?

    Returns (ok: bool, reason: str). Rejects mined supply past the 400B
    mining budget ceiling, founder claims past the 100B allocation, or a
    combined total past the 500B hard cap.
    """
    if mined_quarks < 0 or founder_claimed_quarks < 0:
        return False, "negative supply component"
    if mined_quarks > MINING_BUDGET_QUARKS:
        return False, "mined supply exceeds 400B mining budget"
    if founder_claimed_quarks > FOUNDER_TOTAL_QUARKS:
        return False, "founder claims exceed 100B founder allocation"
    if mined_quarks + founder_claimed_quarks > MAX_SUPPLY_QUARKS:
        return False, "combined supply exceeds 500B max supply"
    return True, "ok"


if __name__ == "__main__":
    # Quick self-check: print the schedule summary and the cap proof.
    print("Quasar Coin — supply schedule (founder-approved 2026-10-14)")
    print(f"  Max supply:      {MAX_SUPPLY_QSR:,} QSR")
    print(f"  Mining budget:   {MINING_BUDGET_QSR:,} QSR (ceiling)")
    print(f"  Founder alloc:   {FOUNDER_TOTAL_QSR:,} QSR (20%, 1-week vesting)")
    print(f"  Phase 1:         50,000 QSR x {PHASE1_BLOCKS:,} blocks "
          f"(~5.7 yrs) = 300,000,000,000 QSR")
    print(f"  Phase 2:         25,000 QSR x {PHASE2_BLOCKS:,} blocks "
          f"(2.5 yrs) = 65,745,000,000 QSR")
    print(f"  Phase 3:         12,500 QSR x {PHASE3_BLOCKS:,} blocks "
          f"(2.5 yrs) = 32,872,500,000 QSR")
    print(f"  Stop height:     {TOTAL_REWARD_BLOCKS:,} (reward = 0 after)")
    print(f"  Target block:    {TARGET_SECONDS_PER_BLOCK:g} seconds")
    print(f"  Block 0:         {block_reward_qsr(0):,.0f} QSR/block")
    print(f"  Block 6,000,000: {block_reward_qsr(6_000_000):,.0f} QSR/block "
          f"(halving 1)")
    print(f"  Block 8,629,800: {block_reward_qsr(8_629_800):,.0f} QSR/block "
          f"(halving 2)")
    print(f"  Block 11,259,600:{block_reward_qsr(11_259_600):,.0f} QSR/block "
          f"(STOP)")
    total = total_emission_quarks(100_000_000)  # effectively "all heights"
    print(f"  Total mined if every block is mined: "
          f"{total / QUARKS_PER_QSR:,.2f} QSR")
    print(f"  Schedule exact:  {total == SCHEDULED_EMISSION_QUARKS}")
    print(f"  Under 400B cap:  {total <= MINING_BUDGET_QUARKS}")
    print(f"  Combined under 500B cap: "
          f"{total + FOUNDER_TOTAL_QUARKS <= MAX_SUPPLY_QUARKS}")
    print(f"  Founder vesting: linear over {VESTING_BLOCKS:,} blocks "
          f"(1 week at 30s/block)")
