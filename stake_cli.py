"""
QUASAR COIN - staking demo CLI.

Run:  python3 stake_cli.py

Demo wallet 'demo' starts with 10,000 coins + 500 welcome airdrop.
Stake at 12% APY, Pi-style tap-to-mine, airdrops, and referrals.
State persists in staking_state.json.

Educational only. Coins have no value. Not launched.
"""

import time

from staking import (StakingPool, EPOCH_SECONDS, APY, MIN_STAKE, UNBOND_EPOCHS,
                     TAP_SESSION_SECONDS, current_epoch)


def fmt(c: float) -> str:
    return f"{c:,.4f}"


def show_wallet(pool: StakingPool, name: str):
    w = pool.get_wallet(name)
    pending = w.pending_rewards()
    print(f"\n--- Wallet '{w.name}' ---")
    print(f"  address : {w.address}")
    print(f"  referral code : {w.referral_code}"
          + (f" (referred by {w.referred_by})" if w.referred_by else ""))
    print(f"  balance : {fmt(w.balance)}  (free)")
    print(f"  staked  : {fmt(w.staked)}")
    print(f"  pending staking rewards : {fmt(pending)}")
    print(f"  tap earned total : {fmt(w.tap_earned_total)} "
          f"({w.tap_sessions} sessions)")
    if w.unbonding:
        print("  unbonding:")
        for e in w.unbonding:
            wait = max(0, e["release_epoch"] - current_epoch()) * EPOCH_SECONDS
            print(f"    {fmt(e['amount'])} -> releases in ~{wait}s")
    print()


def watch_rewards(pool: StakingPool, name: str, epochs: int = 6):
    """Live ticker: print pending rewards once per epoch."""
    print(f"\nWatching rewards for '{name}' "
          f"({epochs} epochs x {EPOCH_SECONDS}s). Ctrl+C to stop early.\n")
    try:
        for _ in range(epochs):
            w = pool.get_wallet(name)
            print(f"  epoch {current_epoch()} | staked {fmt(w.staked)} | "
                  f"pending rewards {fmt(w.pending_rewards())}")
            time.sleep(EPOCH_SECONDS - (time.time() % EPOCH_SECONDS) + 0.05)
    except KeyboardInterrupt:
        print("\nStopped watching.")
    print()


def main():
    pool = StakingPool()
    name = "demo"

    if name not in pool.wallets:
        pool.create_wallet(name, starting_balance=10_000.0)
        print("Created wallet 'demo': 10,000.00 + 500.00 welcome airdrop.\n")
    else:
        print("Loaded existing wallet 'demo' (state restored).\n")

    while True:
        print("======== QUASAR STAKING ========")
        print(" 1. Stake coins")
        print(" 2. Check rewards")
        print(" 3. Watch rewards live")
        print(" 4. Unstake (3-epoch cooldown)")
        print(" 5. Withdraw matured unbonded coins")
        print(" 6. Show wallet")
        print(" 7. Claim welcome airdrop")
        print(" 8. Run airdrop (bulk)")
        print(" 9. Tap to mine (Pi-style 24h session)")
        print("10. Tap session status")
        print("11. My referral code")
        print("12. Refer a friend (simulate)")
        print("13. Referral stats")
        print("14. Network stats")
        print(" 0. Exit")
        choice = input("> ").strip()

        try:
            if choice == "1":
                amt = float(input(f"Amount to stake (min {MIN_STAKE}): "))
                pool.stake(name, amt)
                print(f"Staked {fmt(amt)} coins at {APY*100:.0f}% APY.\n")
            elif choice == "2":
                w = pool.get_wallet(name)
                print(f"Pending rewards: {fmt(w.pending_rewards())} coins.\n")
            elif choice == "3":
                watch_rewards(pool, name)
            elif choice == "4":
                amt = float(input("Amount to unstake: "))
                rel = pool.unstake(name, amt)
                wait = (rel - current_epoch()) * EPOCH_SECONDS
                print(f"Unbonding {fmt(amt)} coins. "
                      f"Releases in ~{wait}s ({UNBOND_EPOCHS} epochs).\n")
            elif choice == "5":
                got = pool.withdraw_unbonded(name)
                print(f"Withdrew {fmt(got)} matured coins to balance.\n")
            elif choice == "6":
                show_wallet(pool, name)
            elif choice == "7":
                got = pool.claim_welcome_airdrop(name)
                if got > 0:
                    print(f"Welcome airdrop claimed: {fmt(got)} coins!\n")
                else:
                    print("Already claimed.\n")
            elif choice == "8":
                names = [n.strip() for n in
                         input("Wallet names (comma-separated): ").split(",")
                         if n.strip()]
                amt = float(input("Coins per wallet: "))
                granted = pool.airdrop(names, amt)
                print(f"Airdropped to {len(granted)} wallets.\n")
            elif choice == "9":
                r = pool.tap(name)
                if r["session_started"]:
                    print("⛏️  New 24h tap session started! Come back "
                          "tomorrow and tap again.\n")
                else:
                    print(f"Session already active "
                          f"({r['seconds_remaining']/3600:.1f}h left). "
                          f"Credited {fmt(r['earned_credited'])} coins so far.\n")
            elif choice == "10":
                s = pool.tap_status(name)
                print(f"\n  active: {s['active']}")
                print(f"  time remaining: {s['seconds_remaining']/3600:.2f}h")
                print(f"  rate: {fmt(s['rate_per_hour'])}/hour")
                print(f"  sessions: {s['sessions_total']}, "
                      f"total earned: {fmt(s['tap_earned_total'])}\n")
            elif choice == "11":
                w = pool.get_wallet(name)
                print(f"\nYour referral code: {w.referral_code}\n")
                print("Share it! You get 100 coins per friend who joins, "
                      "and +10% tap rate per active friend (max +100%).\n")
            elif choice == "12":
                w = pool.get_wallet(name)
                friend = input("Friend's wallet name: ").strip()
                pool.create_wallet(friend, starting_balance=10_000.0,
                                   referrer_code=w.referral_code)
                print(f"\n'{friend}' joined with your code! "
                      f"+100.00 coins for you, +250.00 bonus for them "
                      f"(on top of their 500.00 welcome airdrop).\n")
            elif choice == "13":
                s = pool.referral_stats(name)
                print(f"\n--- Referrals for '{name}' ---")
                print(f"  code: {s['code']}")
                print(f"  total referrals : {s['total_referrals']}")
                print(f"  active referrals: {s['active_referrals']}")
                print(f"  tap-rate boost  : +{s['referral_boost_pct']:.0f}%")
                print(f"  lifetime earnings: {fmt(s['lifetime_earnings'])}\n")
            elif choice == "14":
                s = pool.stats()
                print("\n--- Network ---")
                print(f"  wallets           : {s['wallets']}")
                print(f"  total staked      : {fmt(s['total_staked'])}")
                print(f"  total rewards paid: {fmt(s['total_rewards_paid'])}")
                print(f"  total airdropped  : {fmt(s['total_airdropped'])}"
                      f" / {s['airdrop_cap']:,.0f} cap")
                print(f"  APY               : {s['apy']*100:.0f}%")
                print(f"  epoch             : {s['current_epoch']} "
                      f"({s['epoch_seconds']}s each)\n")
            elif choice == "0":
                print("Bye! State saved.")
                break
            else:
                print("Unknown option.\n")
        except ValueError as e:
            print(f"Error: {e}\n")
        except KeyboardInterrupt:
            print("\nBye! State saved.")
            break


if __name__ == "__main__":
    main()
