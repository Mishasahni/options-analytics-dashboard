# Personal Options Analytics Platform

A locally-run, Opstra-style options portfolio analytics tool built on a clean,
layered architecture. Upload an Odin Desktop positions CSV, and the app
parses your open option positions, computes payoff and risk statistics, and
renders payoff/P&L charts -- all through a Streamlit UI.

## Architecture

```
CSV (or future API)
        |
        v
PositionDataProvider   (parser.py)   -- turns raw data into Position objects
        |
        v
Position                (position.py) -- one open option leg, extensible for Greeks
        |
        v
Portfolio                (portfolio.py) -- collection + grouping + valuation
        |
        v
PayoffEngine              (payoff.py)   -- payoff math, pure and stateless
AnalyticsEngine          (analytics.py) -- MTM, breakevens, max P/L, risk-reward
        |
        v
charts.py + app.py       -- matplotlib figures rendered in Streamlit
```

**The core design rule:** `Portfolio`, `AnalyticsEngine`, `PayoffEngine`, and
`charts.py` never import `parser.py` and know nothing about CSV files. They
only ever see `Position` objects. This means a future broker API integration
is added by writing a new class that implements `PositionDataProvider` (see
below) -- no other file changes.

## Files

| File | Responsibility |
|---|---|
| `position.py` | `Position` dataclass (one option leg) and `Greeks` extension point |
| `parser.py` | `PositionDataProvider` interface + `OdinCSVDataProvider` implementation |
| `portfolio.py` | `Portfolio`: holds positions, groups by expiry/symbol, delegates valuation/payoff |
| `payoff.py` | `PayoffEngine`: per-position and portfolio-wide payoff math |
| `analytics.py` | `AnalyticsEngine`: MTM, breakevens, max profit/loss, risk-reward, Greeks aggregation |
| `charts.py` | Matplotlib figure builders (payoff chart, current P&L chart, heatmap stub) |
| `utils.py` | Enums (`OptionType`, `PositionSide`, `InstrumentType`), lot sizes, numeric helpers |
| `app.py` | Streamlit UI: upload, filters, tables, charts, statistics |

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload an Odin Desktop "Positions" CSV export (a sample is included in
`sample_data/`). The parser automatically:

* strips whitespace from headers and cell values,
* drops blank rows, the `-----------` separator row, and the `(ALL)` totals row,
* drops rows with a blank Net Qty (fully closed / netted-to-zero positions),
* drops rows with blank Strike Price / Option Type (outright futures/cash
  rows, which are not options),
* supports multiple symbols (NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, and any
  stock) and multiple expiries in the same file.

## Extending to a live broker API

Implement the `PositionDataProvider` interface in a new file, e.g.
`broker_api_provider.py`:

```python
from parser import PositionDataProvider
from position import Position

class BrokerAPIDataProvider(PositionDataProvider):
    def __init__(self, api_client):
        self._api_client = api_client

    def load_positions(self) -> list[Position]:
        raw = self._api_client.get_positions()
        return [self._to_position(r) for r in raw]
```

Then swap the provider passed into `Portfolio`:

```python
portfolio = Portfolio(BrokerAPIDataProvider(my_client))
```

No changes are needed in `portfolio.py`, `payoff.py`, `analytics.py`,
`charts.py`, or `app.py`.

## Extending to Greeks / Black-Scholes pricing

`Position.greeks` and `AnalyticsEngine.portfolio_greeks()` already exist as
extension points but are unpopulated (all fields `None`) in this version,
since no pricing/implied-volatility engine exists yet. To add it:

1. Create `pricing.py` with a Black-Scholes-Merton implementation that takes
   spot, strike, time-to-expiry, rate, and implied vol, and returns a
   `Greeks` instance.
2. After loading positions (in `Portfolio.load_positions` or a new
   post-processing step), compute and assign `position.greeks` for each
   position.
3. `AnalyticsEngine.portfolio_greeks()` will automatically sum populated
   Greeks with no further code changes.
4. `charts.plot_payoff_heatmap()` is a stub that can then be implemented
   using the pricing engine to model payoff across (underlying price,
   valuation date) instead of only at expiry.

## Assumptions and conventions

* Position `quantity` is signed: positive = net long, negative = net short.
* `premium` is Odin's `Net Price` column: the blended average price for the
  currently open net quantity.
* Payoff at expiry for a position is
  `quantity * (intrinsic_value_at_expiry - premium)`, which correctly
  produces all four vanilla payoff shapes (long/short call, long/short put)
  from the sign of `quantity` alone -- no special-casing per shape.
* Lot sizes for the four supported indices are defined in `utils.py` as
  defaults and should be reviewed periodically, since exchanges revise them.
