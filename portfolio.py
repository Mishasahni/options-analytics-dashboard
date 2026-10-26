"""
portfolio.py
------------
Responsibility: Own the collection of Position objects for the current
account, sourced from any PositionDataProvider (CSV today, an API later).
Offers grouping and valuation helpers used by the Analytics engine, Charts,
and the Streamlit UI. Portfolio never parses raw data itself -- that is the
DataProvider's job -- keeping this class agnostic to the data source.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Sequence
from datetime import date

import numpy as np

from parser import PositionDataProvider
from payoff import PayoffEngine
from position import Position


class Portfolio:
    """
    Holds the current set of open option positions and provides grouping,
    valuation, and payoff-delegation methods.

    The constructor takes a `PositionDataProvider`, not a file path or CSV
    text -- this is the seam that lets a future broker API plug in without
    any change to this class: just pass a different provider.
    """

    def __init__(
        self,
        provider: PositionDataProvider,
        payoff_engine: Optional[PayoffEngine] = None,
    ):
        self._provider = provider
        self._payoff_engine = payoff_engine or PayoffEngine()
        self._positions: List[Position] = []

    def load_positions(self) -> List[Position]:
        """Fetch positions from the configured provider and cache them."""
        self._positions = self._provider.load_positions()
        return self._positions

    @property
    def positions(self) -> List[Position]:
        """Currently loaded positions (call load_positions() first)."""
        return self._positions

    def is_empty(self) -> bool:
        return len(self._positions) == 0

    # -- grouping -------------------------------------------------------

    def group_by_expiry(
        self, positions: Optional[Sequence[Position]] = None
    ) -> Dict[date, List[Position]]:
        """Group the given positions (defaults to all) by expiry date."""
        target = positions if positions is not None else self._positions
        groups: Dict[date, List[Position]] = defaultdict(list)
        for position in target:
            groups[position.expiry].append(position)
        return dict(groups)

    def group_by_symbol(
        self, positions: Optional[Sequence[Position]] = None
    ) -> Dict[str, List[Position]]:
        """Group the given positions (defaults to all) by underlying symbol."""
        target = positions if positions is not None else self._positions
        groups: Dict[str, List[Position]] = defaultdict(list)
        for position in target:
            groups[position.symbol].append(position)
        return dict(groups)

    def filter(
        self,
        symbol: Optional[str] = None,
        expiry: Optional[date] = None,
    ) -> List[Position]:
        """Return positions matching the given optional filters."""
        result = self._positions
        if symbol is not None:
            result = [p for p in result if p.symbol == symbol]
        if expiry is not None:
            result = [p for p in result if p.expiry == expiry]
        return result

    # -- valuation --------------------------------------------------------

    def calculate_current_value(
        self, positions: Optional[Sequence[Position]] = None
    ) -> float:
        """
        Total unrealized P&L across the given positions (defaults to the
        whole portfolio), computed from market_price vs. premium.
        """
        target = positions if positions is not None else self._positions
        return sum(p.current_value() for p in target)

    def calculate_total_mtm(
        self, positions: Optional[Sequence[Position]] = None
    ) -> float:
        """Total broker-reported MTM across the given positions."""
        target = positions if positions is not None else self._positions
        return sum(p.mtm for p in target)

    # -- payoff delegation --------------------------------------------------

    def calculate_payoff(
        self,
        underlying_prices: Sequence[float],
        positions: Optional[Sequence[Position]] = None,
    ) -> np.ndarray:
        """
        Expiry payoff of the given positions (defaults to the whole
        portfolio) across `underlying_prices`. Delegates the actual math to
        PayoffEngine so Portfolio stays focused on position management.
        """
        target = positions if positions is not None else self._positions
        return self._payoff_engine.portfolio_payoff(target, underlying_prices)

    def representative_spot(
        self, positions: Optional[Sequence[Position]] = None
    ) -> float:
        """
        A representative current underlying price for the given positions,
        used to center payoff ranges. Uses the most recently loaded
        position's spot_price for the relevant symbol; if positions span
        multiple symbols, returns the mean of their spot prices.
        """
        target = positions if positions is not None else self._positions
        if not target:
            return 0.0
        spots = {p.symbol: p.spot_price for p in target}
        return float(np.mean(list(spots.values())))
