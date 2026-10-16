#!/usr/bin/env python3
"""Create the Quasar (QSR) SPL token on Solana DEVNET only. Never mainnet."""
import json, time, sys, struct

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import create_account, CreateAccountParams, ID as SYSTEM_PROGRAM_ID
from solders.instruction import Instruction, AccountMeta
from solders.message import Message
from solders.transaction import Transaction
from solders.sysvar import RENT
from solana.rpc.api import Client

DEVNET = "https://api.devnet.solana.com"
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
ATA_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8jhy")
DECIMALS = 6
TOTAL_SUPPLY_TOKENS = 500_000_000_000
TOTAL_SUPPLY_BASE = TOTAL_SUPPLY_TOKENS * (10 ** DECIMALS)  # 5e17, fits u64
KEYPAIR_PATH = "/home/hatch/workspace/quasar-coin/solana-coin-authority.json"

assert TOTAL_SUPPLY_BASE < 2**64, "supply overflow!"

client = Client(DEVNET)

# 1. Authority keypair (dedicated for the coin)
authority = Keypair()
with open(KEYPAIR_PATH, "w") as f:
    json.dump(list(bytes(authority)), f)
print("authority pubkey:", authority.pubkey())

# 2. Airdrop devnet SOL for fees (retry on rate limit)
sig = None
for attempt in range(6):
    try:
        sig = client.request_airdrop(authority.pubkey(), 2_000_000_000).value
        print("airdrop sig:", str(sig)[:16], "...")
        break
    except Exception as e:
        print(f"airdrop attempt {attempt+1} failed: {str(e)[:100]}; waiting 20s")
        time.sleep(20)
if sig is None:
    sys.exit("AIRDROP FAILED after retries")
for _ in range(30):
    time.sleep(2)
    bal = client.get_balance(authority.pubkey()).value
    if bal > 0:
        break
print("authority balance (lamports):", client.get_balance(authority.pubkey()).value)

def send(ixs, signers):
    bh = client.get_latest_blockhash().value.blockhash
    msg = Message.new_with_blockhash(ixs, authority.pubkey(), bh)
    txn = Transaction(signers, msg, bh)  # signs with provided keypairs
    s = client.send_raw_transaction(bytes(txn))
    sig = s.value
    print("  tx:", str(sig)[:24], "...")
    for _ in range(30):
        time.sleep(2)
        st = client.get_signature_statuses([sig]).value[0]
        if st is not None and st.confirmation_status in ("confirmed", "finalized"):
            if st.err:
                raise RuntimeError(f"tx failed: {st.err}")
            return sig
    raise RuntimeError("tx not confirmed in time")

# 3. Create mint account + initialize mint (decimals=6, mint authority = authority, no freeze authority)
mint_kp = Keypair()
rent = client.get_minimum_balance_for_rent_exemption(82).value
ix_create = create_account(CreateAccountParams(
    from_pubkey=authority.pubkey(), to_pubkey=mint_kp.pubkey(),
    lamports=rent, space=82, owner=TOKEN_PROGRAM_ID))
init_data = bytes([0, DECIMALS]) + bytes(authority.pubkey()) + bytes([0])
ix_init = Instruction(TOKEN_PROGRAM_ID,
    init_data,
    [AccountMeta(mint_kp.pubkey(), True, False), AccountMeta(RENT, False, False)])
print("creating mint...")
send([ix_create, ix_init], [authority, mint_kp])
mint_addr = str(mint_kp.pubkey())
print("MINT ADDRESS:", mint_addr)

# 4. Create associated token account for authority
ata, _bump = Pubkey.find_program_address(
    [bytes(authority.pubkey()), bytes(TOKEN_PROGRAM_ID), bytes(mint_kp.pubkey())],
    ATA_PROGRAM_ID)
ix_ata = Instruction(ATA_PROGRAM_ID, b"",
    [AccountMeta(authority.pubkey(), True, True),
     AccountMeta(ata, False, True),
     AccountMeta(authority.pubkey(), False, False),
     AccountMeta(mint_kp.pubkey(), False, False),
     AccountMeta(SYSTEM_PROGRAM_ID, False, False),
     AccountMeta(TOKEN_PROGRAM_ID, False, False),
     AccountMeta(RENT, False, False)])
print("creating ATA...")
send([ix_ata], [authority])
print("ATA:", ata)

# 5. Mint full supply to ATA
mint_data = bytes([7]) + struct.pack("<Q", TOTAL_SUPPLY_BASE)
ix_mint = Instruction(TOKEN_PROGRAM_ID, mint_data,
    [AccountMeta(mint_kp.pubkey(), False, True),
     AccountMeta(ata, False, True),
     AccountMeta(authority.pubkey(), True, False)])
print("minting full supply...")
send([ix_mint], [authority])

# 6. Verify
time.sleep(3)
supply = client.get_token_supply(mint_kp.pubkey()).value
bal = client.get_token_account_balance(ata).value
print("VERIFIED supply:", supply.ui_amount_string, "| decimals:", supply.decimals)
print("VERIFIED ATA balance:", bal.ui_amount_string)

with open("/home/hatch/workspace/quasar-coin/mint-address.txt", "w") as f:
    f.write(mint_addr + "\n")
print("DONE. Mint:", mint_addr)
