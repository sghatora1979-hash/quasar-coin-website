"""
QUASAR CORE - wallet.py

Bitcoin-style wallets for the local Quasar learning chain:
- ECDSA keypairs on the secp256k1 curve (same curve Bitcoin uses)
- Addresses: Base58Check(version_byte + hash160(compressed_pubkey) + checksum)
  Version byte 0x3A makes every address start with 'Q'.

IMPORTANT - DEMO KEYS:
  These wallets are for a LOCAL, single-node, educational blockchain.
  The coins have NO monetary value and there is NO public network.
  Back up your wallet files if you care about your demo balance, but
  NEVER treat these keys as real-money keys.
"""

import hashlib
import json
import os
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError

# ---------------------------------------------------------------- constants
VERSION_BYTE = 0x3A          # -> addresses start with 'Q'
def _wallets_dir() -> str:
    """Location of the wallets/ directory.

    Override with the QUASAR_DATA_DIR environment variable so multiple
    nodes on one machine keep separate wallets.
    """
    base = os.environ.get("QUASAR_DATA_DIR")
    if not base:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "wallets")


WALLETS_DIR = _wallets_dir()
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


# ------------------------------------------------------------ base58check
def _b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n > 0:
        n, rem = divmod(n, 58)
        out = BASE58_ALPHABET[rem] + out
    pad = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * pad + out


def base58check_encode(payload: bytes) -> str:
    """payload -> base58(payload + first4(sha256(sha256(payload))))."""
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    return _b58encode(payload + checksum)


def hash160(data: bytes) -> bytes:
    """Bitcoin's hash160: ripemd160(sha256(data))."""
    sha = hashlib.sha256(data).digest()
    try:
        ripe = hashlib.new("ripemd160", sha).digest()
    except ValueError:
        # Some OpenSSL builds lack ripemd160; fall back to a pure-python path.
        from ecdsa.util import sigdecode_string  # noqa: F401  (keeps import local)
        raise RuntimeError(
            "ripemd160 is not available in this Python/OpenSSL build; "
            "the ecdsa pip package normally pulls pycryptodome-free builds that "
            "still rely on hashlib. Install pycryptodome for RIPEMD160 support."
        )
    return ripe


def address_from_pubkey(pubkey_bytes: bytes) -> str:
    """Compressed (33-byte) or uncompressed pubkey -> 'Q...' address."""
    return base58check_encode(bytes([VERSION_BYTE]) + hash160(pubkey_bytes))


def compressed_pubkey(vk: VerifyingKey) -> bytes:
    """33-byte compressed public key (0x02/0x03 prefix + 32-byte X)."""
    x = vk.pubkey.point.x()
    y = vk.pubkey.point.y()
    return bytes([0x02 | (y & 1)]) + x.to_bytes(32, "big")


# ----------------------------------------------------------------- wallet
class Wallet:
    """An ECDSA secp256k1 keypair with a Quasar address."""

    def __init__(self, private_key_hex: str):
        self._sk = SigningKey.from_string(
            bytes.fromhex(private_key_hex), curve=SECP256k1
        )
        self.private_key_hex = private_key_hex
        self.public_key_bytes = compressed_pubkey(self._sk.get_verifying_key())
        self.public_key_hex = self.public_key_bytes.hex()
        self.address = address_from_pubkey(self.public_key_bytes)

    @classmethod
    def generate(cls) -> "Wallet":
        sk = SigningKey.generate(curve=SECP256k1)
        return cls(sk.to_string().hex())

    # ------------------------------------------------------------- signing
    def sign_hash(self, msg_hash_hex: str) -> str:
        """Deterministically sign a 32-byte message hash (RFC 6979). Returns DER hex."""
        digest = bytes.fromhex(msg_hash_hex)
        sig = self._sk.sign_digest_deterministic(
            digest, hashfunc=hashlib.sha256
        )
        return sig.hex()

    @staticmethod
    def verify_signature(pubkey_hex: str, msg_hash_hex: str, sig_hex: str) -> bool:
        """Verify a signature against a compressed pubkey and message hash."""
        try:
            raw = bytes.fromhex(pubkey_hex)
            prefix, x = raw[0], int.from_bytes(raw[1:], "big")
            vk = VerifyingKey.from_public_point(
                _decompress_point(prefix, x), curve=SECP256k1, hashfunc=hashlib.sha256
            )
            return vk.verify_digest(
                bytes.fromhex(sig_hex), bytes.fromhex(msg_hash_hex)
            )
        except (BadSignatureError, Exception):
            return False

    # ----------------------------------------------------------- persistence
    def save(self, name: str) -> str:
        """Save wallet JSON to wallets/<name>.json. Returns the file path."""
        wallets_dir = _wallets_dir()
        os.makedirs(wallets_dir, exist_ok=True)
        path = os.path.join(wallets_dir, f"{name}.json")
        with open(path, "w") as f:
            json.dump(
                {
                    "name": name,
                    "address": self.address,
                    "private_key_hex": self.private_key_hex,
                    "public_key_hex": self.public_key_hex,
                    # DEMO KEYS - local learning chain only. Back up this file
                    # if you want to keep your demo coins. Never reuse these
                    # keys for anything with real value.
                },
                f,
                indent=2,
            )
        return path

    @classmethod
    def load(cls, name: str) -> "Wallet":
        path = os.path.join(_wallets_dir(), f"{name}.json")
        with open(path) as f:
            data = json.load(f)
        return cls(data["private_key_hex"])

    @classmethod
    def list_names(cls):
        wallets_dir = _wallets_dir()
        if not os.path.isdir(wallets_dir):
            return []
        return sorted(
            f[:-5] for f in os.listdir(wallets_dir) if f.endswith(".json")
        )


def _decompress_point(prefix: int, x: int):
    """Recover the full EC point from a compressed pubkey (x + parity bit)."""
    from ecdsa.ellipticcurve import Point
    curve = SECP256k1.curve
    p = curve.p()
    # y^2 = x^3 + ax + b  (secp256k1: a=0, b=7)
    y_sq = (pow(x, 3, p) + 7) % p
    y = pow(y_sq, (p + 1) // 4, p)  # p % 4 == 3 for secp256k1
    if (y & 1) != (prefix & 1):
        y = p - y
    return Point(curve, x, y, SECP256k1.order)
