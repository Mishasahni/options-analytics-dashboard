"""
utils.py
--------
Responsibility: Hold cross-cutting enums, constants, and small stateless
helper functions (numeric parsing, lot-size lookup, symbol classification)
that are shared by the parser, position, portfolio, analytics, and payoff
modules. Nothing in this module depends on any other project module, which
keeps it safe to import from anywhere without creating circular imports.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

import numpy as np


class OptionType(str, Enum):
    """The two flavours of vanilla options this platform understands."""

    CALL = "CE"
    PUT = "PE"

    @classmethod
    def from_raw(cls, raw: str) -> "OptionType":
        """Parse a broker-supplied option type string (e.g. ' CE ') safely."""
        cleaned = raw.strip().upper()
        if cleaned in ("CE", "CALL", "C"):
            return cls.CALL
        if cleaned in ("PE", "PUT", "P"):
            return cls.PUT
        raise ValueError(f"Unrecognized option type: {raw!r}")


class PositionSide(str, Enum):
    """Whether the net position is a net buyer (long) or net seller (short)."""

    LONG = "LONG"
    SHORT = "SHORT"

    @classmethod
    def from_quantity(cls, quantity: float) -> "PositionSide":
        return cls.LONG if quantity >= 0 else cls.SHORT


class InstrumentType(str, Enum):
    """Distinguishes index derivatives from single-stock derivatives."""

    INDEX = "INDEX"
    STOCK = "STOCK"


# Known index underlyings supported explicitly by the platform. Anything not
# in this set is treated as InstrumentType.STOCK.
INDEX_SYMBOLS: frozenset[str] = frozenset(
    {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"}
)

# Approximate current F&O lot sizes for supported indices. These change
# periodically at the exchange's discretion; treat this as a default lookup
# that a user can override, not a source of truth.
DEFAULT_INDEX_LOT_SIZES: dict[str, int] = {
    "NIFTY": 75,
    "BANKNIFTY": 30,
    "FINNIFTY": 65,
    "MIDCPNIFTY": 140,
}

# Sentinel used instead of a magic number when a lot size is genuinely unknown.
UNKNOWN_LOT_SIZE: int = 1


def classify_instrument(symbol: str) -> InstrumentType:
    """Classify a trading symbol as an index or a stock underlying."""
    return (
        InstrumentType.INDEX
        if symbol.strip().upper() in INDEX_SYMBOLS
        else InstrumentType.STOCK
    )


def lot_size_for(symbol: str) -> int:
    """Best-effort lot size lookup; falls back to UNKNOWN_LOT_SIZE (1)."""
    return DEFAULT_INDEX_LOT_SIZES.get(symbol.strip().upper(), UNKNOWN_LOT_SIZE)


def safe_float(value, default: Optional[float] = None) -> Optional[float]:
    """
    Convert a broker CSV cell to a float, tolerating blanks, stray
    whitespace, and thousands separators. Returns `default` (None unless
    overridden) when the cell cannot be interpreted as a number.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value) if not _is_nan(value) else default
    text = str(value).strip().replace(",", "")
    if text == "" or text == "-":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _is_nan(value) -> bool:
    try:
        return bool(np.isnan(value))
    except TypeError:
        return False


def generate_price_range(
    center: float, spread: float, step: float
) -> np.ndarray:
    """
    Build a symmetric array of underlying prices around `center`, e.g.
    center=25000, spread=2000, step=50 -> 23000, 23050, ..., 27000.
    Used by the payoff engine to build its default simulation grid.
    """
    if step <= 0:
        raise ValueError("step must be positive")
    low = center - spread
    high = center + spread
    # +step/2 nudge guards against float rounding excluding the last point.
    return np.arange(low, high + step / 2, step)
