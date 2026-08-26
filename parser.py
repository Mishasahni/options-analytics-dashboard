"""
parser.py
---------
Responsibility: Convert a raw data source into a clean list of Position
objects. Defines the `PositionDataProvider` interface that decouples the
Analytics/Portfolio layer from *how* data is obtained, and provides
`OdinCSVDataProvider`, the first concrete implementation, which parses Odin
Desktop CSV exports. A future `BrokerAPIDataProvider` (or similar) can be
added later by implementing the same interface -- no other module needs to
change.
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Union

import pandas as pd

from position import Position
from utils import OptionType, lot_size_for, safe_float

# Odin exports strike/option-type columns blank for outright futures/stock
# (non-option) rows; those are out of scope for this options-only platform.
_REQUIRED_OPTION_COLUMNS = ("Strike Price", "Option Type")

# Column names as they appear in Odin exports *after* whitespace stripping.
_EXPECTED_COLUMNS = {
    "Scrip Code",
    "Symbol",
    "Ser/Exp",
    "Strike Price",
    "Option Type",
    "Buy Qty",
    "Buy Lot",
    "Buy Avg.",
    "Sell Qty",
    "Sell Lot",
    "Sell Avg.",
    "Net Qty",
    "Net Weight",
    "Net Price",
    "Market Price",
    "Net Lot",
    "Group",
    "MTM G/L",
    "Spot Price",
}

_EXPIRY_FORMAT = "%d%b%Y"  # e.g. "30JUN2026"


class PositionDataProvider(ABC):
    """
    Abstract interface for anything that can supply a list of open option
    Positions. The Portfolio class depends only on this interface, never on
    a concrete provider, so swapping CSV for a live broker API later is a
    matter of writing a new subclass -- Portfolio/Analytics/Payoff/Charts
    code does not change.
    """

    @abstractmethod
    def load_positions(self) -> List[Position]:
        """Return the current list of open option positions."""
        raise NotImplementedError


class OdinCSVDataProvider(PositionDataProvider):
    """
    Parses Odin Desktop "Positions" CSV exports into Position objects.

    Handles the real-world messiness of these exports:
      * trailing/leading whitespace in column headers and cell values
      * blank rows
      * the "-----------" separator row before the totals row
      * the "(ALL)" aggregate/totals row
      * rows with a blank Net Qty (fully closed / netted-to-zero positions)
      * rows with blank Strike Price / Option Type (outright futures or
        cash-market rows, which are not options and are out of scope)
    """

    def __init__(self, source: Union[str, Path, io.StringIO]):
        """
        `source` may be a filesystem path, a Path object, or an in-memory
        text buffer (e.g. `io.StringIO` from a Streamlit file upload).
        """
        self._source = source

    def load_positions(self) -> List[Position]:
        raw_df = self._read_raw()
        clean_df = self._clean(raw_df)
        return [self._row_to_position(row) for _, row in clean_df.iterrows()]

    # -- internal helpers ---------------------------------------------------

    def _read_raw(self) -> pd.DataFrame:
        """Read the CSV as all-string data; numeric parsing happens later
        via `safe_float` so stray formatting never raises here."""
        return pd.read_csv(
            self._source,
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=True,
        )

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace, drop non-data rows, and keep only open option
        positions."""
        df = df.copy()

        # Strip whitespace from column headers.
        df.columns = [str(c).strip() for c in df.columns]

        missing = _EXPECTED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Odin CSV is missing expected column(s): {sorted(missing)}"
            )

        # Strip whitespace from every string cell.
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        # Drop fully blank rows.
        df = df[~(df == "").all(axis=1)]

        # Drop the "-----------" separator row (dashes in the Symbol cell).
        df = df[~df["Symbol"].str.fullmatch(r"-+")]

        # Drop the "(ALL)" aggregate/totals row.
        df = df[df["Symbol"].str.upper() != "(ALL)"]

        # Keep only option rows: Strike Price and Option Type both present.
        for col in _REQUIRED_OPTION_COLUMNS:
            df = df[df[col] != ""]

        # Keep only OPEN positions: a blank Net Qty means the buy/sell legs
        # netted to zero (fully closed) and Odin leaves it empty.
        df = df[df["Net Qty"] != ""]

        return df.reset_index(drop=True)

    def _row_to_position(self, row: pd.Series) -> Position:
        symbol = row["Symbol"].strip().upper()
        expiry = datetime.strptime(row["Ser/Exp"].strip().upper(), _EXPIRY_FORMAT).date()
        strike = safe_float(row["Strike Price"], default=0.0)
        option_type = OptionType.from_raw(row["Option Type"])
        quantity = safe_float(row["Net Qty"], default=0.0)
        premium = safe_float(row["Net Price"], default=0.0)
        spot_price = safe_float(row["Spot Price"], default=0.0)
        market_price = safe_float(row["Market Price"], default=0.0)
        mtm = safe_float(row["MTM G/L"], default=0.0)

        return Position(
            symbol=symbol,
            expiry=expiry,
            strike=strike,
            option_type=option_type,
            quantity=quantity,
            premium=premium,
            spot_price=spot_price,
            market_price=market_price,
            mtm=mtm,
            lot_size=lot_size_for(symbol),
            scrip_code=row.get("Scrip Code", "").strip() or None,
        )
