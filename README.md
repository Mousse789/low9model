# low9model — Low-9 / High-9 TD Sequential scanner

A daily stock scanner for **TD Sequential setups** (九转序列) across US equities, on
both daily and weekly timeframes, with P/E enrichment, price sparklines, a ~2-year
backtest of each signal's hit-rate, and a self-contained interactive HTML dashboard.

- **Low 9** (TD Buy Setup): 9 consecutive bars each closing *below* the close 4 bars
  earlier → downtrend exhaustion, a possible bottom / bounce.
- **High 9** (TD Sell Setup): 9 consecutive bars each closing *above* the close 4 bars
  earlier → uptrend exhaustion, a possible top / drop.

Data comes from the public Yahoo Finance chart & quote endpoints. Standard library
only — no third-party Python packages required.

> Technical screen for research only — **not financial advice**. Signals fail often.

## Pipeline

The project is a 4-stage pipeline. Each stage reads/writes JSON, so you can run them
independently or chain them:

```bash
# 1. Scan the universe -> low9_hits.json
python3 low9_scanner.py --sleep 0.12 --json low9_hits.json

# 2. Enrich with trailing/forward P/E + market cap -> low9_hits_pe.json
python3 low9_fetch_pe.py --in low9_hits.json --out low9_hits_pe.json

# 3. Attach 6-month price sparklines -> low9_hits_full.json
python3 low9_fetch_series.py --in low9_hits_pe.json --out low9_hits_full.json

# 4. Build the interactive dashboard -> index.html
python3 low9_app_builder.py low9_hits_full.json index.html
```

Open `index.html` in any browser. There is also `low9_dashboard_builder.py`, a simpler
static dashboard variant that takes the same JSON.

## Files

| File | Purpose |
|------|---------|
| `low9_scanner.py` | Scans the liquid US + S&P 500 universe; computes daily/weekly setup counts and backtests every completed 9. |
| `low9_fetch_pe.py` | Adds trailing/forward P/E and market cap via Yahoo's crumb-authenticated quote endpoint. |
| `low9_fetch_series.py` | Adds a downsampled 6-month close series (`spark`) and window % change (`chg`) per hit. |
| `low9_app_builder.py` | Builds the vivid single-file interactive HTML app (filters, sorting, sparklines, charts). |
| `low9_dashboard_builder.py` | Simpler static single-file HTML dashboard. |

## Scanner options

```
--universe {liquid,sp500}   default: liquid (top-N liquid US + S&P 500)
--topn N                    default: 1000 (size of the liquid universe)
--limit N                   scan only the first N tickers (for testing)
--sleep S                   per-ticker delay in seconds (default 0.25)
--report                    print a text report to stdout
```

## Requirements

Python 3.8+. No external dependencies.

## License

MIT (or your preference — edit this section).
