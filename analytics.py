"""
analytics.py
------------
Responsibility: Derive portfolio-level statistics (current MTM, expiry
payoff summary, breakevens, max profit/loss, risk-reward ratio) from a
PayoffCurve and a set of Positions. This module is the analytical brain of
the platform and depends only on payoff.py and position.py -- never on
parser.py or app.py -- so it works identically regardless of whether the
positions came from a CSV or a future live API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np

from payoff import PayoffCurve, PayoffEngine
from position import Greeks, Position

# A max profit/loss beyond this magnitude (relative to the payoff range)
# is treated as "unbounded" rather than a specific number, since a naked
# short/long option's payoff is only capped within the simulated range.
_UNBOUNDED_LABEL = "Unbounded"


@dataclass
class PortfolioStatistics:
    """Bundle of headline statistics for a portfolio or a filtered subset."""

    current_mtm: float
    current_value: float
    max_profit: Optional[float]
    max_loss: Optional[float]
    is_max_profit_unbounded: bool
    is_max_loss_unbounded: bool
    breakevens: List[float]
    risk_reward_ratio: Optional[float]
    net_premium: float
    greeks: Greeks


class AnalyticsEngine:
    """
    Computes portfolio statistics from Positions and their PayoffCurve.

    Greeks note: `portfolio_greeks` currently returns an all-None Greeks
    object. This is an explicit extension point -- once a pricing module
    (Black-Scholes / implied vol) exists, it can populate each Position's
    `greeks` field, and this method will sum them into the portfolio-level
    Greeks without any change to its signature or callers.
    """

    def __init__(self, payoff_engine: Optional[PayoffEngine] = None):
        self._payoff_engine = payoff_engine or PayoffEngine()

    def current_mtm(self, positions: Sequence[Position]) -> float:
        """Sum of broker-reported MTM across positions."""
        return float(sum(p.mtm for p in positions))

    def current_value(self, positions: Sequence[Position]) -> float:
        """Sum of computed unrealized value (market_price vs premium)."""
        return float(sum(p.current_value() for p in positions))

    def net_premium(self, positions: Sequence[Position]) -> float:
        """
        Net premium of the book: positive means net premium paid (net
        long), negative means net premium received (net short/credit).
        """
        return float(sum(p.quantity * p.premium for p in positions))

    def breakevens(self, curve: PayoffCurve) -> List[float]:
        """
        Underlying prices where the payoff curve crosses zero, found by
        linear interpolation between sign changes in the simulated range.
        Only breakevens *within* the simulated range are found; widen the
        PayoffEngine's spread if a breakeven is suspected to lie outside it.
        """
        prices = curve.underlying_prices
        payoff = curve.payoff
        crossings: List[float] = []
        for i in range(len(payoff) - 1):
            y0, y1 = payoff[i], payoff[i + 1]
            if y0 == 0:
                crossings.append(float(prices[i]))
                continue
            if y0 * y1 < 0:
                x0, x1 = prices[i], prices[i + 1]
                # Linear interpolation for the zero crossing.
                crossing = x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
                crossings.append(float(crossing))
        return crossings

    def max_profit_loss(self, curve: PayoffCurve) -> tuple:
        """
        Returns (max_profit, max_loss, profit_unbounded, loss_unbounded).
        "Unbounded" is flagged when the payoff is still trending away from
        zero at either edge of the simulated range (i.e. a naked long/short
        option whose profit or loss is not capped within the tested range).
        """
        payoff = curve.payoff
        max_profit = float(np.max(payoff))
        max_loss = float(np.min(payoff))

        profit_unbounded = payoff[-1] == max_profit and payoff[-1] > payoff[-2]
        loss_unbounded = payoff[0] == max_loss and payoff[0] < payoff[1]

        return max_profit, max_loss, profit_unbounded, loss_unbounded

    def risk_reward_ratio(
        self, max_profit: float, max_loss: float
    ) -> Optional[float]:
        """
        Reward-to-risk ratio (max_profit / abs(max_loss)). Returns None if
        max_loss is zero (undefined ratio) to avoid a divide-by-zero.
        """
        if max_loss == 0:
            return None
        return abs(max_profit / max_loss)

    def portfolio_greeks(self, positions: Sequence[Position]) -> Greeks:
        """
        Sums per-position Greeks into a portfolio-level Greeks object.
        Returns all-None fields until positions carry populated Greeks
        (see the class docstring's extension-point note).
        """
        fields = ("delta", "gamma", "theta", "vega", "rho", "implied_volatility")
        totals = {f: None for f in fields}
        for field_name in fields:
            values = [
                getattr(p.greeks, field_name)
                for p in positions
                if getattr(p.greeks, field_name) is not None
            ]
            if values:
                totals[field_name] = float(sum(values))
        return Greeks(**totals)

    def compute_statistics(
        self,
        positions: Sequence[Position],
        curve: PayoffCurve,
    ) -> PortfolioStatistics:
        """Compute the full PortfolioStatistics bundle in one call."""
        max_profit, max_loss, profit_unbounded, loss_unbounded = self.max_profit_loss(
            curve
        )
        return PortfolioStatistics(
            current_mtm=self.current_mtm(positions),
            current_value=self.current_value(positions),
            max_profit=max_profit,
            max_loss=max_loss,
            is_max_profit_unbounded=profit_unbounded,
            is_max_loss_unbounded=loss_unbounded,
            breakevens=self.breakevens(curve),
            risk_reward_ratio=self.risk_reward_ratio(max_profit, max_loss),
            net_premium=self.net_premium(positions),
            greeks=self.portfolio_greeks(positions),
        )
