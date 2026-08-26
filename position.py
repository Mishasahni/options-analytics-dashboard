"""
position.py
-----------
Responsibility: Define the immutable-by-convention Position data model that
represents a single open option leg, independent of where it came from
(CSV today, a broker API tomorrow). This is the single unit of data that
flows from any DataProvider into the Portfolio and Analytics layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from utils import InstrumentType, OptionType, PositionSide, classify_instrument


@dataclass
class Greeks:
    """
    Placeholder container for option Greeks.

    Architecture note: Greeks are not computed yet (no Black-Scholes /
    implied-vol engine exists in this version). This class exists so that
    Position can carry an optional `greeks` field today, and a future
    `pricing.py` module (e.g. a Black-Scholes-Merton implementation) can
    populate it without any change to Position, Portfolio, or Analytics.
    """

    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    rho: Optional[float] = None
    implied_volatility: Optional[float] = None


@dataclass
class Position:
    """
    A single open option position (one strike, one expiry, one symbol).

    Sign convention:
        quantity > 0  -> net long (net bought) this many units.
        quantity < 0  -> net short (net sold) this many units.
    `premium` is the net average price per unit for the currently open
    quantity (i.e. the cost basis for a long position, or the credit
    received per unit for a short position).
    """

    symbol: str
    expiry: date
    strike: float
    option_type: OptionType
    quantity: float
    premium: float
    spot_price: float
    market_price: float
    mtm: float

    # Optional metadata, useful for traceability back to the broker export.
    lot_size: int = 1
    scrip_code: Optional[str] = None

    # Extension point for Greeks; populated later by a pricing engine.
    greeks: Greeks = field(default_factory=Greeks)

    @property
    def instrument_type(self) -> InstrumentType:
        """INDEX or STOCK, derived from the symbol."""
        return classify_instrument(self.symbol)

    @property
    def side(self) -> PositionSide:
        """LONG if net bought, SHORT if net sold."""
        return PositionSide.from_quantity(self.quantity)

    @property
    def lots(self) -> float:
        """Net quantity expressed in lots rather than units."""
        return self.quantity / self.lot_size if self.lot_size else 0.0

    @property
    def is_call(self) -> bool:
        return self.option_type == OptionType.CALL

    @property
    def is_put(self) -> bool:
        return self.option_type == OptionType.PUT

    def intrinsic_value_at(self, underlying_price: float) -> float:
        """Per-unit intrinsic value of this option at a given underlying price."""
        if self.is_call:
            return max(underlying_price - self.strike, 0.0)
        return max(self.strike - underlying_price, 0.0)

    def payoff_at(self, underlying_price: float) -> float:
        """
        Total (quantity-scaled) profit/loss of this position if held to
        expiry with the underlying settling at `underlying_price`.
        """
        return self.quantity * (self.intrinsic_value_at(underlying_price) - self.premium)

    def current_value(self) -> float:
        """
        Mark-to-market value implied by the current market price, i.e. the
        unrealized P&L based on `market_price` versus `premium`.
        Kept independent from `self.mtm` (the broker-reported figure) so the
        analytics engine can cross-check the two if desired.
        """
        return self.quantity * (self.market_price - self.premium)
