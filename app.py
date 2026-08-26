"""
app.py
------
Responsibility: Streamlit UI layer. Wires together OdinCSVDataProvider,
Portfolio, PayoffEngine, AnalyticsEngine, and charts.py to let the user
upload a CSV, filter positions, and view payoff/statistics. This file
contains no analytics logic itself -- it only orchestrates calls into the
other modules, which is what keeps the analytics engine reusable outside
Streamlit (e.g. from a script or a notebook).
"""

from __future__ import annotations

import io
from datetime import date
from typing import List, Optional

import streamlit as st

from analytics import AnalyticsEngine
from parser import OdinCSVDataProvider
from payoff import PayoffEngine
from portfolio import Portfolio
from position import Position
import charts

st.set_page_config(page_title="Options Analytics Platform", layout="wide")


def _load_portfolio(uploaded_file) -> Portfolio:
    """Build a Portfolio from an uploaded Streamlit file object."""
    text_buffer = io.StringIO(uploaded_file.getvalue().decode("utf-8-sig"))
    provider = OdinCSVDataProvider(text_buffer)
    portfolio = Portfolio(provider, payoff_engine=PayoffEngine())
    portfolio.load_positions()
    return portfolio


def _sidebar_filters(portfolio: Portfolio) -> tuple[Optional[str], Optional[date]]:
    """Render sidebar filter widgets and return the selected (symbol, expiry)."""
    st.sidebar.header("Filters")

    symbols = sorted({p.symbol for p in portfolio.positions})
    symbol_choice = st.sidebar.selectbox("Underlying / Symbol", ["All"] + symbols)
    symbol = None if symbol_choice == "All" else symbol_choice

    expiries = sorted({p.expiry for p in portfolio.positions})
    expiry_labels = ["All"] + [e.strftime("%d-%b-%Y") for e in expiries]
    expiry_choice = st.sidebar.selectbox("Expiry", expiry_labels)
    expiry = (
        None
        if expiry_choice == "All"
        else expiries[expiry_labels.index(expiry_choice) - 1]
    )

    return symbol, expiry


def _render_positions_table(positions: List[Position]) -> None:
    st.subheader(f"Open Option Positions ({len(positions)})")
    rows = [
        {
            "Symbol": p.symbol,
            "Expiry": p.expiry.strftime("%d-%b-%Y"),
            "Strike": p.strike,
            "Type": p.option_type.value,
            "Side": p.side.value,
            "Qty": p.quantity,
            "Premium": round(p.premium, 2),
            "LTP": round(p.market_price, 2),
            "Spot": round(p.spot_price, 2),
            "MTM": round(p.mtm, 2),
        }
        for p in positions
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_grouped_positions(portfolio: Portfolio) -> None:
    st.subheader("Grouped Positions")
    tab_expiry, tab_symbol = st.tabs(["By Expiry", "By Symbol"])

    with tab_expiry:
        for expiry, positions in sorted(portfolio.group_by_expiry().items()):
            with st.expander(f"{expiry.strftime('%d-%b-%Y')} ({len(positions)} legs)"):
                _render_positions_table(positions)

    with tab_symbol:
        for symbol, positions in sorted(portfolio.group_by_symbol().items()):
            with st.expander(f"{symbol} ({len(positions)} legs)"):
                _render_positions_table(positions)


def _render_statistics(analytics: AnalyticsEngine, positions: List[Position], curve) -> None:
    stats = analytics.compute_statistics(positions, curve)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current MTM", f"{stats.current_mtm:,.2f}")
    col2.metric("Net Premium", f"{stats.net_premium:,.2f}")

    max_profit_label = (
        "Unbounded" if stats.is_max_profit_unbounded else f"{stats.max_profit:,.2f}"
    )
    max_loss_label = (
        "Unbounded" if stats.is_max_loss_unbounded else f"{stats.max_loss:,.2f}"
    )
    col3.metric("Max Profit", max_profit_label)
    col4.metric("Max Loss", max_loss_label)

    col5, col6 = st.columns(2)
    rr_label = "N/A" if stats.risk_reward_ratio is None else f"{stats.risk_reward_ratio:.2f}"
    col5.metric("Risk-Reward Ratio", rr_label)
    breakeven_label = (
        ", ".join(f"{b:,.2f}" for b in stats.breakevens) if stats.breakevens else "None found"
    )
    col6.metric("Breakeven(s)", breakeven_label)


def main() -> None:
    st.title("Personal Options Analytics Platform")
    st.caption("Upload an Odin Desktop positions CSV to analyze your options book.")

    uploaded_file = st.file_uploader("Upload Odin CSV export", type=["csv"])
    if uploaded_file is None:
        st.info("Waiting for a CSV upload. Use the sample file in sample_data/ to try it out.")
        return

    portfolio = _load_portfolio(uploaded_file)
    if portfolio.is_empty():
        st.warning("No open option positions were found in this file.")
        return

    symbol, expiry = _sidebar_filters(portfolio)
    filtered_positions = portfolio.filter(symbol=symbol, expiry=expiry)

    if not filtered_positions:
        st.warning("No positions match the selected filters.")
        return

    payoff_engine = PayoffEngine()
    analytics = AnalyticsEngine(payoff_engine)

    spot = portfolio.representative_spot(filtered_positions)
    curve = payoff_engine.build_payoff_curve(filtered_positions, current_spot=spot)

    st.header("Portfolio Statistics")
    _render_statistics(analytics, filtered_positions, curve)

    st.header("Payoff Chart")
    st.pyplot(charts.plot_payoff_chart(curve))

    st.header("Current P&L by Position")
    st.pyplot(charts.plot_current_pnl_chart(filtered_positions))

    _render_positions_table(filtered_positions)
    _render_grouped_positions(portfolio)


if __name__ == "__main__":
    main()
