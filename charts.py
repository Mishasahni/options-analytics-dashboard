"""
charts.py
---------
Responsibility: Turn PayoffCurve / Position data into matplotlib Figures.
This module has no knowledge of Streamlit -- it returns `Figure` objects
that any UI layer (Streamlit today, something else tomorrow) can render.
"""

from __future__ import annotations

from typing import Sequence

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from payoff import PayoffCurve
from position import Position

_PROFIT_COLOR = "#2E7D32"
_LOSS_COLOR = "#C62828"
_SPOT_LINE_COLOR = "#1565C0"
_ZERO_LINE_COLOR = "#616161"


def plot_payoff_chart(curve: PayoffCurve, title: str = "Portfolio Payoff at Expiry") -> Figure:
    """
    Render the classic options payoff diagram: P&L on the y-axis against
    underlying price on the x-axis, shaded green above zero and red below,
    with a vertical marker at the current spot price.
    """
    fig, ax = plt.subplots(figsize=(10, 5.5))

    x = curve.underlying_prices
    y = curve.payoff

    ax.plot(x, y, color="#212121", linewidth=1.5)
    ax.fill_between(x, y, 0, where=(y >= 0), color=_PROFIT_COLOR, alpha=0.25, interpolate=True)
    ax.fill_between(x, y, 0, where=(y < 0), color=_LOSS_COLOR, alpha=0.25, interpolate=True)

    ax.axhline(0, color=_ZERO_LINE_COLOR, linewidth=0.8)
    ax.axvline(
        curve.current_spot,
        color=_SPOT_LINE_COLOR,
        linestyle="--",
        linewidth=1.2,
        label=f"Spot: {curve.current_spot:,.2f}",
    )

    ax.set_title(title)
    ax.set_xlabel("Underlying Price")
    ax.set_ylabel("Profit / Loss")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


def plot_current_pnl_chart(positions: Sequence[Position], title: str = "Current P&L by Position") -> Figure:
    """
    Horizontal bar chart of each position's current unrealized P&L
    (market_price vs. premium), labeled by symbol/strike/type, colored
    green for profit and red for loss.
    """
    fig, ax = plt.subplots(figsize=(10, max(3.0, 0.35 * len(positions))))

    labels = [
        f"{p.symbol} {p.strike:g}{p.option_type.value} {p.expiry.strftime('%d-%b')}"
        for p in positions
    ]
    values = [p.current_value() for p in positions]
    colors = [_PROFIT_COLOR if v >= 0 else _LOSS_COLOR for v in values]

    y_pos = range(len(positions))
    ax.barh(y_pos, values, color=colors, alpha=0.8)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(0, color=_ZERO_LINE_COLOR, linewidth=0.8)
    ax.set_xlabel("Unrealized P&L")
    ax.set_title(title)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_payoff_heatmap(*args, **kwargs) -> Figure:
    """
    Extension point for a future payoff heatmap (e.g. underlying price vs.
    days-to-expiry, colored by P&L). Not implemented in this version because
    it requires a time-decay pricing model (Black-Scholes theta) that does
    not exist yet -- see analytics.py's portfolio_greeks() note. Once that
    pricing engine lands, implement this using PayoffEngine.portfolio_payoff
    evaluated across a 2D grid of (underlying_price, valuation_date).
    """
    raise NotImplementedError(
        "Payoff heatmap requires a time-decay pricing model; not yet implemented."
    )
