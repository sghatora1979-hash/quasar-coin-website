"""
QUASAR CORE - transactions.py

Simplified Bitcoin-style UTXO transactions for the local Quasar chain.

- Amounts are integers in "quarks": 1 QSR = 100_000_000 quarks
  (integer math only - no floating point money, like Bitcoin's satoshis).
- A Transaction spends previously-created outputs (UTXOs) as inputs and
  creates new outputs. Inputs are signed by the sender's private key.
- Coinbase transactions have no inputs and create new coins (mining reward).

LOCAL LEARNING CHAIN ONLY - no network, no real value.
"""

import hashlib
import json

QUARKS_PER_QSR = 100_000_000  # 1 QSR = 10^8 quarks


def qsr_to_quarks(qsr: float) -> int:
    return int(round(qsr * QUARKS_PER_QSR))


def quarks_to_qsr(quarks: int) -> float:
    return quarks / QUARKS_PER_QSR


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TxInput:
    """References one unspent output: (prev_tx_hash, output_index)."""

    def __init__(self, prev_tx_hash: str, prev_output_index: int,
                 signature: str = "", pubkey_hex: str = ""):
        self.prev_tx_hash = prev_tx_hash
        self.prev_output_index = prev_output_index
        self.signature = signature      # hex, signs this transaction's hash
        self.pubkey_hex = pubkey_hex    # compressed pubkey of the spender

    def to_dict(self):
        return {
            "prev_tx_hash": self.prev_tx_hash,
            "prev_output_index": self.prev_output_index,
            "signature": self.signature,
            "pubkey_hex": self.pubkey_hex,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d["prev_tx_hash"], d["prev_output_index"],
                   d.get("signature", ""), d.get("pubkey_hex", ""))


class TxOutput:
    """Creates value: <amount quarks> locked to <address>."""

    def __init__(self, address: str, amount_quarks: int):
        self.address = address
        self.amount_quarks = int(amount_quarks)

    def to_dict(self):
        return {"address": self.address, "amount_quarks": self.amount_quarks}

    @classmethod
    def from_dict(cls, d):
        return cls(d["address"], d["amount_quarks"])


class Transaction:
    """A signed value transfer. tx_hash = sha256 of the unsigned content."""

    def __init__(self, inputs, outputs):
        self.inputs = inputs    # list[TxInput]
        self.outputs = outputs  # list[TxOutput]

    # ------------------------------------------------------------ hashing
    def _unsigned_dict(self):
        return {
            "inputs": [
                {"prev_tx_hash": i.prev_tx_hash,
                 "prev_output_index": i.prev_output_index,
                 "pubkey_hex": i.pubkey_hex}
                for i in self.inputs
            ],
            "outputs": [o.to_dict() for o in self.outputs],
        }

    def tx_hash(self) -> str:
        canonical = json.dumps(self._unsigned_dict(), sort_keys=True,
                               separators=(",", ":"))
        return sha256_hex(canonical)

    # ------------------------------------------------------------ signing
    def sign_input(self, index: int, wallet) -> None:
        """Sign input `index` with a Wallet (sets signature + pubkey)."""
        txin = self.inputs[index]
        txin.pubkey_hex = wallet.public_key_hex
        txin.signature = ""  # signature never covers itself
        txin.signature = wallet.sign_hash(self.tx_hash())

    # -------------------------------------------------------- verification
    def is_coinbase(self) -> bool:
        return len(self.inputs) == 0

    def verify(self, utxo_lookup) -> tuple:
        """
        Verify this transaction against the UTXO set.
        utxo_lookup(prev_tx_hash, prev_output_index) -> (address, amount_quarks) | None
        Returns (ok: bool, reason: str).
        """
        if self.is_coinbase():
            return True, "coinbase"
        if not self.outputs:
            return False, "no outputs"
        if any(o.amount_quarks <= 0 for o in self.outputs):
            return False, "non-positive output"

        total_in = 0
        seen = set()
        msg = self.tx_hash()
        # Lazy import to avoid a hard cycle (node.py imports both).
        from wallet import Wallet, address_from_pubkey

        for txin in self.inputs:
            key = (txin.prev_tx_hash, txin.prev_output_index)
            if key in seen:
                return False, "duplicate input in tx"
            seen.add(key)
            utxo = utxo_lookup(*key)
            if utxo is None:
                return False, f"input not in UTXO set: {key}"
            addr, amount = utxo
            total_in += amount
            if not txin.signature or not txin.pubkey_hex:
                return False, "missing signature/pubkey"
            # The pubkey must belong to the address that owns the UTXO.
            if address_from_pubkey(bytes.fromhex(txin.pubkey_hex)) != addr:
                return False, "pubkey does not match UTXO owner"
            if not Wallet.verify_signature(txin.pubkey_hex, msg, txin.signature):
                return False, "bad signature"

        total_out = sum(o.amount_quarks for o in self.outputs)
        if total_out > total_in:
            return False, "outputs exceed inputs"
        return True, f"ok (fee={total_in - total_out} quarks)"

    # ------------------------------------------------------ serialization
    def to_dict(self):
        return {"inputs": [i.to_dict() for i in self.inputs],
                "outputs": [o.to_dict() for o in self.outputs],
                "tx_hash": self.tx_hash(),
                "tx_type": "transfer"}

    @classmethod
    def from_dict(cls, d):
        # Dispatch: a serialized founder-claim must come back as one,
        # wherever it is deserialized (blocks, mempool, P2P).
        if d.get("tx_type") == "founder_claim" or d.get("founder_claim"):
            return FounderClaimTransaction.from_dict(d)
        return cls([TxInput.from_dict(i) for i in d["inputs"]],
                   [TxOutput.from_dict(o) for o in d["outputs"]])


class CoinbaseTransaction(Transaction):
    """Mining reward: creates new coins from nothing. No inputs, one output."""

    def __init__(self, miner_address: str, reward_quarks: int, height: int):
        super().__init__([], [TxOutput(miner_address, reward_quarks)])
        # The height is part of the hashed content (like Bitcoin's BIP-34):
        # it guarantees every block's coinbase has a unique tx_hash, so two
        # identical rewards never collide in the UTXO set.
        self.height = height

    def _unsigned_dict(self):
        d = super()._unsigned_dict()
        d["coinbase_height"] = self.height
        return d

    def to_dict(self):
        d = super().to_dict()
        d["coinbase_height"] = self.height
        d["tx_type"] = "coinbase"
        return d

    @classmethod
    def from_dict(cls, d):
        tx = cls(d["outputs"][0]["address"],
                 d["outputs"][0]["amount_quarks"],
                 d.get("coinbase_height", 0))
        return tx


class FounderClaimTransaction(Transaction):
    """Founder-allocation claim: creates new coins from the founder
    allocation (NOT from mining). No inputs. Exactly one output, to
    the founder address recorded in the genesis block.

    A unique `nonce` is part of the hashed content, so two claims for
    the same amount never share a tx_hash and can never collide in
    the UTXO set.

    This class only checks STRUCTURE (one positive output, right
    address). Vesting — cumulative claims vs
    supply.founder_unlocked_quarks(height) — is consensus state
    checked by node.py at block-inclusion and full-chain validation
    time, because it depends on chain height and prior claims.

    TESTNET ONLY. Test coins, no monetary value.
    """

    def __init__(self, founder_address: str, claim_quarks: int,
                 nonce: int = 0):
        super().__init__([], [TxOutput(founder_address, int(claim_quarks))])
        self.nonce = int(nonce)

    def is_coinbase(self) -> bool:
        # NOT a coinbase: it draws on the founder allocation, not the
        # mining schedule. (Base class would return True because there
        # are no inputs — that would misroute it in validation.)
        return False

    def _unsigned_dict(self):
        d = super()._unsigned_dict()
        d["founder_claim"] = True
        d["founder_claim_nonce"] = self.nonce
        return d

    def verify(self, utxo_lookup, founder_address=None) -> tuple:
        """Structural check only (see class docstring for vesting)."""
        if len(self.outputs) != 1:
            return False, "founder claim must have exactly one output"
        if self.outputs[0].amount_quarks <= 0:
            return False, "founder claim must be positive"
        if (founder_address is not None
                and self.outputs[0].address != founder_address):
            return False, "founder claim must pay the founder address"
        return True, "ok (structural; vesting checked by node)"

    def to_dict(self):
        d = super().to_dict()
        d["tx_type"] = "founder_claim"
        d["founder_claim_nonce"] = self.nonce
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(d["outputs"][0]["address"],
                   d["outputs"][0]["amount_quarks"],
                   d.get("founder_claim_nonce", 0))
