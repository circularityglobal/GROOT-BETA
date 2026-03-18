"""
REFINET Cloud — Shamir Secret Sharing over GF(256)
Splits a byte-string secret into n shares with threshold k.
Any k shares reconstruct the secret; fewer than k reveal nothing.

Uses the irreducible polynomial x^8 + x^4 + x^3 + x + 1 (0x11B),
the same field used by AES.
"""

import os

# ── GF(256) Arithmetic ────────────────────────────────────────────

_EXP = [0] * 512  # exp table (doubled for mod-free multiplication)
_LOG = [0] * 256

def _init_tables():
    """Pre-compute log/exp tables for GF(256) with generator 3 and polynomial 0x11B."""
    x = 1
    for i in range(255):
        _EXP[i] = x
        _EXP[i + 255] = x  # duplicate for wrap-around
        _LOG[x] = i
        # Multiply by generator 3 (x + 1) in GF(256)
        # 3 is a primitive element for polynomial 0x11B
        x = ((x << 1) ^ x)  # x * 3 = x * 2 + x
        if x & 0x100:
            x ^= 0x11B
        x &= 0xFF
    _LOG[0] = 0  # log(0) is undefined but we guard against it

_init_tables()


def _gf_mul(a: int, b: int) -> int:
    """Multiply two elements in GF(256)."""
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _gf_inv(a: int) -> int:
    """Multiplicative inverse in GF(256)."""
    if a == 0:
        raise ValueError("Cannot invert zero in GF(256)")
    return _EXP[255 - _LOG[a]]


# ── Polynomial Evaluation & Interpolation ─────────────────────────

def _eval_poly(coeffs: list[int], x: int) -> int:
    """Evaluate polynomial at x in GF(256). coeffs[0] is constant term."""
    result = 0
    for c in reversed(coeffs):
        result = _gf_mul(result, x) ^ c
    return result


def _lagrange_interpolate(points: list[tuple[int, int]]) -> int:
    """
    Lagrange interpolation at x=0 in GF(256).
    points: list of (x_i, y_i) pairs.
    Returns the secret (constant term).
    """
    secret = 0
    k = len(points)
    for i in range(k):
        xi, yi = points[i]
        num = 1
        den = 1
        for j in range(k):
            if i == j:
                continue
            xj = points[j][0]
            num = _gf_mul(num, xj)        # product of x_j (since we evaluate at 0)
            den = _gf_mul(den, xi ^ xj)   # xi - xj in GF(256) is xi XOR xj
        lagrange = _gf_mul(num, _gf_inv(den))
        secret ^= _gf_mul(yi, lagrange)
    return secret


# ── Public API ────────────────────────────────────────────────────

def split_secret(secret: bytes, k: int, n: int) -> list[tuple[int, bytes]]:
    """
    Split ``secret`` into ``n`` shares; any ``k`` can reconstruct.

    Parameters
    ----------
    secret : bytes
        The secret to split (e.g. a 32-byte private key).
    k : int
        Threshold — minimum shares needed for reconstruction.
    n : int
        Total number of shares to generate (max 255).

    Returns
    -------
    list of (index, share_bytes)
        index is 1..n. Each share_bytes has the same length as secret.
    """
    if k < 2:
        raise ValueError("Threshold must be >= 2")
    if n < k:
        raise ValueError("Share count must be >= threshold")
    if n > 255:
        raise ValueError("Maximum 255 shares (GF(256) constraint)")
    if not secret:
        raise ValueError("Secret must not be empty")

    secret_len = len(secret)
    shares: list[list[int]] = [[] for _ in range(n)]

    for byte_idx in range(secret_len):
        # Random polynomial of degree k-1 with secret byte as constant term
        coeffs = [secret[byte_idx]] + list(os.urandom(k - 1))

        for share_idx in range(n):
            x = share_idx + 1  # evaluation points 1..n
            y = _eval_poly(coeffs, x)
            shares[share_idx].append(y)

    return [(i + 1, bytes(shares[i])) for i in range(n)]


def reconstruct_secret(shares: list[tuple[int, bytes]], k: int) -> bytes:
    """
    Reconstruct the secret from ``k`` or more shares.

    Parameters
    ----------
    shares : list of (index, share_bytes)
        At least ``k`` shares. Each share_bytes must have the same length.
    k : int
        The threshold used during splitting.

    Returns
    -------
    bytes
        The reconstructed secret.
    """
    if len(shares) < k:
        raise ValueError(f"Need at least {k} shares, got {len(shares)}")

    # Use exactly k shares
    used = shares[:k]
    secret_len = len(used[0][1])

    if any(len(s[1]) != secret_len for s in used):
        raise ValueError("All shares must have the same length")

    result = bytearray(secret_len)
    for byte_idx in range(secret_len):
        points = [(s[0], s[1][byte_idx]) for s in used]
        result[byte_idx] = _lagrange_interpolate(points)

    return bytes(result)
