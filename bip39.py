"""BIP39 mnemonic -> entropy (pure Python, stdlib only).

The 32-byte entropy is used DIRECTLY as the secp256k1 private key,
byte-identical to what the website wallet (quasar-wallet.js) derives,
so a phrase created on the website mines to the same address here.
"""
import hashlib
import os

_WORDLIST = None


def _load_wordlist():
    global _WORDLIST
    if _WORDLIST is None:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "wordlist.txt")
        with open(p, "r", encoding="utf-8") as f:
            _WORDLIST = [w.strip() for w in f if w.strip()]
        if len(_WORDLIST) != 2048:
            raise RuntimeError("wordlist.txt must have 2048 words")
    return _WORDLIST


def mnemonic_to_private_hex(phrase):
    """24 words -> 64-char private key hex. Raises ValueError if invalid."""
    words = phrase.strip().lower().split()
    if len(words) != 24:
        raise ValueError("need exactly 24 words (got %d)" % len(words))
    wl = _load_wordlist()
    bits = ""
    for w in words:
        try:
            idx = wl.index(w)
        except ValueError:
            raise ValueError("unknown word: %r" % w)
        bits += bin(idx)[2:].zfill(11)
    ent_bits, chk_bits = bits[:256], bits[256:]
    entropy = int(ent_bits, 2).to_bytes(32, "big")
    chk = bin(hashlib.sha256(entropy).digest()[0])[2:].zfill(8)
    if chk != chk_bits:
        raise ValueError("bad checksum - words may be mistyped or out of order")
    return entropy.hex()
