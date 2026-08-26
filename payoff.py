"""
payoff.py
---------
Responsibility: Pure payoff mathematics. Computes the expiry P&L of a single
Position and of a collection of Positions across a configurable range of
underlying prices. This module knows nothing about CSVs, Streamlit, or
Portfolio internals -- it only operates on Position objects and numbers, so
it stays reusable and easy to unit-test in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import numpy as np

from position import Position
from utils import generate_price_range


@dataclass(frozen=True)
class PayoffCurve:
    """
    The result of a payoff simulation: parallel arrays of underlying prices
    and the corresponding total P&L, plus the current spot for reference.
    """

    underlying_prices: np.ndarray
    payoff: np.ndarray
    current_spot: float

    def payoff_at(self, underlying_price: float) -> float:
        """Interpolated payoff at an arbitrary underlying price."""
        return float(np.interp(underlying_price, self.underlying_prices, self.payoff))


class PayoffEngine:
    """
    Computes expiry payoff for individual positions and for an entire
    portfolio (the sum of all position payoffs), across a simulated range
    of underlying prices.

    Supports all four vanilla option payoff shapes via Position.payoff_at:
        Long Call, Short Call, Long Put, Short Put
    -- the sign of `quantity` on the Position determines long vs. short, and
    `option_type` determines call vs. put, so no special-casing is needed
    here; the math lives once, in Position.payoff_at / intrinsic_value_at.
    """

    def payoff_for_position(
        self, position: Position, underlying_prices: Sequence[float]
    ) -> np.ndarray:
        """Vector of P&L for a single position across `underlying_prices`."""
        prices = np.asarray(underlying_prices, dtype=float)
        return np.array([position.payoff_at(p) for p in prices])

    def portfolio_payoff(
        self,
        positions: Iterable[Position],
        underlying_prices: Sequence[float],
    ) -> np.ndarray:
        """
        Sum of every position's payoff across `underlying_prices`. Positions
        for different symbols/expiries are summed as-is; callers that want a
        payoff for a single underlying/expiry should pre-filter the list
        (see Portfolio.group_by_symbol / group_by_expiry).
        """
        prices = np.asarray(underlying_prices, dtype=float)
        total = np.zeros_like(prices, dtype=float)
        for position in positions:
            total += self.payoff_for_position(position, prices)
        return total

    def build_payoff_curve(
        self,
        positions: Iterable[Position],
        current_spot: float,
        spread: float = 2000.0,
        step: float = 50.0,
    ) -> PayoffCurve:
        """
        Convenience method: builds a symmetric price range around
        `current_spot` (default +/-2000 in steps of 50) and returns the full
        PayoffCurve for the given positions.
        """
        positions = list(positions)
        prices = generate_price_range(current_spot, spread, step)
        payoff = self.portfolio_payoff(positions, prices)
        return PayoffCurve(
            underlying_prices=prices, payoff=payoff, current_spot=current_spot
        )
