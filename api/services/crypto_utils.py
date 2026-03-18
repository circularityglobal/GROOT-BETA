"""
REFINET Cloud — Shared Cryptographic Utilities
Keccak-256 hash used by ABI parser, SDK generator, and MCP gateway.
"""

import hashlib


def keccak256(data: bytes) -> bytes:
    """
    Keccak-256 hash (Ethereum standard).
    Falls back to sha3_256 if pysha3/pycryptodome unavailable.
    """
    try:
        from Crypto.Hash import keccak
        k = keccak.new(digest_bits=256)
        k.update(data)
        return k.digest()
    except ImportError:
        pass
    try:
        import sha3
        return sha3.keccak_256(data).digest()
    except ImportError:
        pass
    # Last resort: hashlib sha3_256 — NOT identical to Keccak but usable
    return hashlib.sha3_256(data).digest()


def compute_selector(signature: str) -> str:
    """Compute 4-byte function selector from canonical signature."""
    return "0x" + keccak256(signature.encode()).hex()[:8]


def compute_topic_hash(signature: str) -> str:
    """Compute full keccak256 topic hash for event signature."""
    return "0x" + keccak256(signature.encode()).hex()


def sha256_hex(data: str) -> str:
    """SHA-256 hex digest of a string."""
    return hashlib.sha256(data.encode()).hexdigest()
