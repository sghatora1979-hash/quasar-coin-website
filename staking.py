"""
QUASAR COIN - educational staking prototype.

A genuine staking + distribution simulation (the mobile-friendly
alternative to mining):
- Wallets stake coins (minimum 100) and earn 12% APY, 10-second epochs
- Welcome airdrop (500 coins) + bulk airdrops (capped at 1% of max supply)
- Pi-style tap-to-mine: 24h sessions, 10 coins/hour base, +50% if staking,
  +10% per active referral (capped +100%)
- Referral system: unique codes, 100-coin referrer bonus, +250 referee bonus
- State persists to staking_state.json across restarts

This is NOT launched. Coins have no value. A real launch would need
smart contracts, a security audit, and legal/securities review.
"""

import json
import os
import secrets
import time

from blockchain import MAX_SUPPLY

# ---- Time (injectable for tests: override staking._now) ----
_now = time.time

# ---- Staking parameters ----
EPOCH_SECONDS = 10                    # 1 epoch = 10 real seconds (demo speed)
EPOCHS_PER_YEAR = 365 * 24 * 3600 // EPOCH_SECONDS   # 3,153,600
APY = 0.12                            # 12% annual percentage yield
MIN_STAKE = 100                       # minimum coins to stake
UNBOND_EPOCHS = 3                     # cooldown before unstaked coins release

# ---- Airdrop parameters ----
WELCOME_AIRDROP = 500.0               # free coins per new wallet
MAX_AIRDROP_TOTAL = MAX_SUPPLY * 0.01  # 1% of max supply = 5,000,000,000

# ---- Tap-to-mine parameters (Pi Network style) ----
TAP_SESSION_SECONDS = 24 * 3600       # sessions last 24 hours
TAP_BASE_RATE_PER_HOUR = 10.0         # base earning rate
TAP_STAKE_BOOST = 0.5                 # +50% while the tapper has coins staked

# ---- Referral parameters ----
REFERRER_BONUS = 100.0                # instant bonus per referral
REFEREE_BONUS = 250.0                 # extra for the new user (on top of welcome)
REFERRAL_BOOST_PER_ACTIVE = 0.10      # +10% tap rate per active referral
REFERRAL_BOOST_CAP = 1.0              # tap-rate referral boost capped at +100%

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "staking_state.json")


def current_epoch() -> int:
    """Integer epoch number based on (injectable) wall-clock time."""
    return int(_now() // EPOCH_SECONDS)


def epoch_reward(staked: float, epochs_elapsed: int) -> float:
    """APY reward for a staked amount over a number of epochs."""
    if staked <= 0 or epochs_elapsed <= 0:
        return 0.0
    return staked * APY * epochs_elapsed / EPOCHS_PER_YEAR


class Wallet:
    def __init__(self, name: str, balance: float = 0.0, address: str = None,
                 staked: float = 0.0, stake_epoch: int = 0,
                 last_settled_epoch: int = 0, unbonding: list = None,
                 airdrop_claimed: bool = False,
                 tap_session_start: float = 0.0,
                 tap_sessions: int = 0,
                 tap_earned_total: float = 0.0,
                 last_tap_time: float = 0.0,
                 referral_code: str = None,
                 referred_by: str = None,
                 referrals: list = None,
                 referral_earnings: float = 0.0):
        self.name = name
        self.address = address or ("qc1" + secrets.token_hex(8))
        self.balance = balance            # free, spendable coins
        self.staked = staked              # locked, earning rewards
        self.stake_epoch = stake_epoch
        self.last_settled_epoch = last_settled_epoch
        self.unbonding = unbonding or []  # [{"amount","release_epoch"}]
        # airdrops
        self.airdrop_claimed = airdrop_claimed
        # tap-to-mine
        self.tap_session_start = tap_session_start  # 0.0 = no active session
        self.tap_sessions = tap_sessions
        self.tap_earned_total = tap_earned_total
        self.last_tap_time = last_tap_time
        # referrals
        self.referral_code = referral_code or self._make_code()
        self.referred_by = referred_by
        self.referrals = referrals or []  # wallet names referred
        self.referral_earnings = referral_earnings

    def _make_code(self) -> str:
        # e.g. address qc1a1b2c3d4... -> QSR-A1B2C3
        return "QSR-" + self.address[3:9].upper()

    def pending_rewards(self) -> float:
        """Staking rewards earned since last settlement (not yet claimed)."""
        return epoch_reward(self.staked, current_epoch() - self.last_settled_epoch)

    def tap_active(self) -> bool:
        return (self.tap_session_start > 0 and
                _now() - self.tap_session_start < TAP_SESSION_SECONDS)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "address": self.address,
            "balance": self.balance,
            "staked": self.staked,
            "stake_epoch": self.stake_epoch,
            "last_settled_epoch": self.last_settled_epoch,
            "unbonding": self.unbonding,
            "airdrop_claimed": self.airdrop_claimed,
            "tap_session_start": self.tap_session_start,
            "tap_sessions": self.tap_sessions,
            "tap_earned_total": self.tap_earned_total,
            "last_tap_time": self.last_tap_time,
            "referral_code": self.referral_code,
            "referred_by": self.referred_by,
            "referrals": self.referrals,
            "referral_earnings": self.referral_earnings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Wallet":
        return cls(
            name=d["name"],
            balance=d["balance"],
            address=d["address"],
            staked=d.get("staked", 0.0),
            stake_epoch=d.get("stake_epoch", 0),
            last_settled_epoch=d.get("last_settled_epoch", 0),
            unbonding=d.get("unbonding", []),
            airdrop_claimed=d.get("airdrop_claimed", False),
            tap_session_start=d.get("tap_session_start", 0.0),
            tap_sessions=d.get("tap_sessions", 0),
            tap_earned_total=d.get("tap_earned_total", 0.0),
            last_tap_time=d.get("last_tap_time", 0.0),
            referral_code=d.get("referral_code"),
            referred_by=d.get("referred_by"),
            referrals=d.get("referrals", []),
            referral_earnings=d.get("referral_earnings", 0.0),
        )


class StakingPool:
    """Holds all wallets, settles rewards, tracks network stats, persists state."""

    def __init__(self):
        self.wallets: dict[str, Wallet] = {}   # name -> Wallet
        self.total_rewards_paid = 0.0
        self.total_airdropped = 0.0
        self.load()

    # ---------- persistence ----------
    def save(self):
        data = {
            "wallets": {n: w.to_dict() for n, w in self.wallets.items()},
            "total_rewards_paid": self.total_rewards_paid,
            "total_airdropped": self.total_airdropped,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def load(self):
        if not os.path.exists(STATE_FILE):
            return
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
            self.wallets = {n: Wallet.from_dict(w)
                            for n, w in data.get("wallets", {}).items()}
            self.total_rewards_paid = data.get("total_rewards_paid", 0.0)
            self.total_airdropped = data.get("total_airdropped", 0.0)
        except (json.JSONDecodeError, KeyError):
            self.wallets = {}
            self.total_rewards_paid = 0.0
            self.total_airdropped = 0.0

    # ---------- wallet management ----------
    def create_wallet(self, name: str, starting_balance: float = 10_000.0,
                      referrer_code: str = None) -> Wallet:
        if name in self.wallets:
            raise ValueError(f"Wallet '{name}' already exists.")
        referrer = self._find_by_code(referrer_code) if referrer_code else None
        if referrer_code and referrer is None:
            raise ValueError(f"Unknown referral code '{referrer_code}'.")
        wallet = Wallet(name=name, balance=starting_balance,
                        last_settled_epoch=current_epoch(),
                        referred_by=referrer_code)
        self.wallets[name] = wallet
        # Welcome airdrop (counts toward the global cap)
        self.claim_welcome_airdrop(name)
        if referrer is not None:
            # Referee bonus on top of the welcome airdrop
            self._grant_airdrop(wallet, REFEREE_BONUS, "referral referee bonus")
            # Referrer instant bonus + linkage
            self._grant_airdrop(referrer, REFERRER_BONUS, "referral bonus")
            referrer.referrals.append(name)
            referrer.referral_earnings += REFERRER_BONUS
        self.save()
        return wallet

    def get_wallet(self, name: str) -> Wallet:
        if name not in self.wallets:
            raise ValueError(f"No wallet named '{name}'.")
        return self.wallets[name]

    def _find_by_code(self, code: str):
        for w in self.wallets.values():
            if w.referral_code == code:
                return w
        return None

    # ---------- airdrops ----------
    def _grant_airdrop(self, wallet: Wallet, amount: float, kind: str):
        if self.total_airdropped + amount > MAX_AIRDROP_TOTAL:
            raise ValueError(
                f"Airdrop cap reached ({MAX_AIRDROP_TOTAL:,.0f} coins). "
                f"Cannot grant {amount:,.0f} ({kind}).")
        wallet.balance += amount
        self.total_airdropped += amount

    def claim_welcome_airdrop(self, name: str) -> float:
        """Idempotent: grants the welcome airdrop once per wallet."""
        wallet = self.get_wallet(name)
        if wallet.airdrop_claimed:
            return 0.0
        self._grant_airdrop(wallet, WELCOME_AIRDROP, "welcome airdrop")
        wallet.airdrop_claimed = True
        self.save()
        return WELCOME_AIRDROP

    def airdrop(self, names: list, amount: float) -> dict:
        """Bulk-distribute `amount` coins to each named wallet."""
        if amount <= 0:
            raise ValueError("Airdrop amount must be positive.")
        if not names:
            raise ValueError("No recipients given.")
        granted = {}
        for n in names:
            wallet = self.get_wallet(n)
            self._grant_airdrop(wallet, amount, "bulk airdrop")
            granted[n] = amount
        self.save()
        return granted

    # ---------- staking actions ----------
    def stake(self, name: str, amount: float) -> Wallet:
        wallet = self.get_wallet(name)
        if amount < MIN_STAKE:
            raise ValueError(f"Minimum stake is {MIN_STAKE} coins.")
        if amount > wallet.balance:
            raise ValueError(
                f"Insufficient balance: {wallet.balance:.2f} available.")
        self._settle(wallet)
        wallet.balance -= amount
        wallet.staked += amount
        if wallet.stake_epoch == 0:
            wallet.stake_epoch = current_epoch()
        self.save()
        return wallet

    def claim(self, name: str) -> float:
        """Claim pending staking rewards into free balance."""
        wallet = self.get_wallet(name)
        reward = self._settle(wallet)
        self.save()
        return reward

    def unstake(self, name: str, amount: float) -> int:
        """Begin unbonding `amount` coins. Rewards auto-claim first."""
        wallet = self.get_wallet(name)
        if amount <= 0:
            raise ValueError("Unstake amount must be positive.")
        if amount > wallet.staked:
            raise ValueError(f"Only {wallet.staked:.2f} coins staked.")
        self._settle(wallet)
        wallet.staked -= amount
        release_epoch = current_epoch() + UNBOND_EPOCHS
        wallet.unbonding.append({"amount": amount,
                                 "release_epoch": release_epoch})
        self.save()
        return release_epoch

    def withdraw_unbonded(self, name: str) -> float:
        """Move matured unbonding entries back to free balance."""
        wallet = self.get_wallet(name)
        now = current_epoch()
        released = 0.0
        still_locked = []
        for entry in wallet.unbonding:
            if entry["release_epoch"] <= now:
                released += entry["amount"]
            else:
                still_locked.append(entry)
        wallet.unbonding = still_locked
        wallet.balance += released
        self.save()
        return released

    def _settle(self, wallet: Wallet) -> float:
        reward = wallet.pending_rewards()
        if reward > 0:
            wallet.balance += reward
            self.total_rewards_paid += reward
        wallet.last_settled_epoch = current_epoch()
        return reward

    # ---------- tap-to-mine (Pi Network style) ----------
    def tap_rate_per_hour(self, name: str) -> float:
        """Current hourly tap rate incl. stake boost and referral boost."""
        wallet = self.get_wallet(name)
        boost = 0.0
        if wallet.staked > 0:
            boost += TAP_STAKE_BOOST
        boost += min(self.active_referral_count(name) *
                     REFERRAL_BOOST_PER_ACTIVE, REFERRAL_BOOST_CAP)
        return TAP_BASE_RATE_PER_HOUR * (1 + boost)

    def active_referral_count(self, name: str) -> int:
        """Referrals who tapped within the last 24 hours."""
        wallet = self.get_wallet(name)
        cutoff = _now() - TAP_SESSION_SECONDS
        count = 0
        for ref_name in wallet.referrals:
            ref = self.wallets.get(ref_name)
            if ref is not None and ref.last_tap_time >= cutoff:
                count += 1
        return count

    def tap(self, name: str) -> dict:
        """
        Pi-style tap: settle any accrued earnings; start a new 24h session
        if none is active. Returns a status dict.
        """
        wallet = self.get_wallet(name)
        earned = self._settle_tap(wallet)
        if wallet.tap_session_start == 0.0:
            wallet.tap_session_start = _now()
            wallet.tap_sessions += 1
            started = True
        else:
            started = False
        wallet.last_tap_time = _now()
        self.save()
        status = self.tap_status(name)
        status["earned_credited"] = earned
        status["session_started"] = started
        return status

    def _settle_tap(self, wallet: Wallet) -> float:
        """Credit tap earnings for elapsed session time. Returns amount."""
        if wallet.tap_session_start == 0.0:
            return 0.0
        elapsed = _now() - wallet.tap_session_start
        # Earnings accrue at the wallet's CURRENT rate for the elapsed window,
        # capped at one full session.
        hours = min(elapsed, TAP_SESSION_SECONDS) / 3600.0
        earned = self.tap_rate_per_hour(wallet.name) * hours
        if earned > 0:
            wallet.balance += earned
            wallet.tap_earned_total += earned
            self.total_rewards_paid += earned
        if elapsed >= TAP_SESSION_SECONDS:
            # Session expired: close it; next tap starts a fresh one
            wallet.tap_session_start = 0.0
        return earned

    def _tap_earned_dry(self, wallet: Wallet) -> float:
        """Earned for the elapsed session window WITHOUT crediting (read-only)."""
        if wallet.tap_session_start == 0.0:
            return 0.0
        elapsed = _now() - wallet.tap_session_start
        hours = min(elapsed, TAP_SESSION_SECONDS) / 3600.0
        return self.tap_rate_per_hour(wallet.name) * hours

    def tap_status(self, name: str) -> dict:
        """Read-only snapshot: no settling, no mutation."""
        wallet = self.get_wallet(name)
        if wallet.tap_session_start > 0:
            elapsed = _now() - wallet.tap_session_start
            active = elapsed < TAP_SESSION_SECONDS
            remaining = max(0.0, TAP_SESSION_SECONDS - elapsed)
            earned_this_session = self._tap_earned_dry(wallet)
        else:
            active = False
            remaining = 0.0
            earned_this_session = 0.0
        return {
            "active": active,
            "seconds_remaining": remaining,
            "earned_this_session": earned_this_session,
            "rate_per_hour": self.tap_rate_per_hour(name),
            "sessions_total": wallet.tap_sessions,
            "tap_earned_total": wallet.tap_earned_total,
        }

    # ---------- network stats ----------
    def stats(self) -> dict:
        self.withdraw_all_matured()
        total_staked = sum(w.staked for w in self.wallets.values())
        return {
            "wallets": len(self.wallets),
            "total_staked": total_staked,
            "total_rewards_paid": self.total_rewards_paid,
            "total_airdropped": self.total_airdropped,
            "airdrop_cap": MAX_AIRDROP_TOTAL,
            "apy": APY,
            "epoch_seconds": EPOCH_SECONDS,
            "current_epoch": current_epoch(),
        }

    def withdraw_all_matured(self):
        for name in list(self.wallets.keys()):
            self.withdraw_unbonded(name)

    # ---------- referral stats ----------
    def referral_stats(self, name: str) -> dict:
        wallet = self.get_wallet(name)
        active = self.active_referral_count(name)
        return {
            "code": wallet.referral_code,
            "total_referrals": len(wallet.referrals),
            "active_referrals": active,
            "lifetime_earnings": wallet.referral_earnings,
            "referral_boost_pct": min(active * REFERRAL_BOOST_PER_ACTIVE,
                                      REFERRAL_BOOST_CAP) * 100,
            "referred_by": wallet.referred_by,
        }
