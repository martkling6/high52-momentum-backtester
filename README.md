# 52-Week-High Momentum Research

Separates a literature-inspired monthly cohort model from exploratory EODHD stock tests. Python 3.10+, standard library only. No verified profitable result included.

## Original reference

George & Hwang (2004), The 52-Week High and Momentum Investing:
https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf

Original sample: CRSP stocks, 1963–2001. Monthly ranking by current price divided by highest price in past 12 months. Top/bottom 30%, equally weighted winner/loser baskets, six overlapping monthly cohorts, six-month holding. Tables I–IV have no skipped month; regression analysis skips one month (footnote 3). Our default skips one month to avoid using a known close as execution price. No SL or TP in this model. Long-only is a distinct adaptation.

## Quick start

```sh
python -m unittest discover -s tests -v
python demo.py
python engine.py --data data/demo.csv --manifest data/demo.manifest.json --config configs/long_only.json --out results/demo
```

Synthetic data verifies software only, never investment profitability.

## Monthly data contract

CSV: `date,symbol,score,return`. Date is the month identifier (first calendar day), return is that month's total simple return; score is known at the END of that month. Empty score means ineligible for new selection. Existing positions still need returns. Missing held-security returns cause failure: never silently zero-fill or delete delisted positions. `score` is in (0,1]. Supply historically eligible universe in each formation month's score rows. No current membership reconstruction or historical fundamental filter is provided.

Manifest `kind`: `synthetic`, `exploratory_static_survivors`, or `point_in_time_reviewed` with `delistings_reviewed=true`. This flag records a review, not an automatic guarantee. Vendor adjustment quality, delisting return, ticker changes and eligibility dates must be verified externally. The engine does not reconstruct delisting returns.

## EODHD adapter

Create `symbols.txt`, one symbol per line (at least 20). Key in EODHD_API_TOKEN only.

```sh
python download_eodhd.py --symbols symbols.txt --start 2000-01-01 --end 2025-12-31 --out data/eod.csv
python engine.py --data data/eod.csv --manifest data/eod.manifest.json --config configs/long_only.json --out results/long_only
python engine.py --data data/eod.csv --manifest data/eod.manifest.json --config configs/long_short.json --out results/long_short
```

A static current stock list produces survivorship/selection bias. The adapter uses adjusted-close / max(adjusted-close) over 365 days with at least 240 observations: **a total-return closing-high proxy**, not a verified split-adjusted price-high reproduction. It restricts to common monthly data, so newest listing can shorten sample. Corporate-action quality and complete calendar coverage are not certified. A completed calendar month-end is required as requested end date. This is only an exploratory pipeline; do not use its output as proof of the original effect.

## Portfolio approximation and costs

Each new cohort receives 1/6 capital; startup gradually ramps from one to six cohorts. Cohort members are equally weighted at each monthly calculation, with constant return-exposure weights within each month. This is not fixed-share execution. Long-short has long 100% plus short 100% gross once fully invested, rather than a zero-capital CAGR interpretation. We net opposite positions when cohorts overlap. Default trading friction: 10 bps on changes in net weights; short borrow: 2% annual divided by 12. No financing, collateral/short proceeds/cash interest, taxes or margin simulation. No borrowing availability check. Rates are assumptions, not verified broker history. Output `monthly.csv`, `selections.csv`, `summary.json`, `run.json`. Monthly drawdown can hide larger intramonth losses. Sharpe assumes zero risk-free rate. All returns are in the data currency; no EUR conversion.

The equal-weight universe return column is diagnostic only: it averages supplied current-month returns, with no trading costs or cohort schedule. Do not treat it as a comparable investable benchmark. A fair lagged cohort benchmark is implemented below; holding-period variants, cost grid and true point-in-time universe remain next research steps.

## GitHub

Import this folder into separate repo `high52-momentum-backtester`. Upload directories too, including configs, tests and .github. Add repository secret EODHD_API_TOKEN. Tests workflow runs automatically. No cross-strategy dependency on tsmom-backtester.

## Active research: Long-only versus matched passive cohorts

The manual workflow now runs only `long_only` and `passive_long`; legacy short code/config remains for reproducibility and is not executed. Passive cohorts use ALL score-eligible stocks from the same lagged formation month. Same six-month expiry, one-month skip, startup cash ramp, net target-weight cost model and cost rate. No short positions, no leverage. Same exposure does not mean same portfolio volatility; actual turnover and friction differ. Results: `comparison/periods.csv`, `paired_monthly.csv`, `comparison.json`. Paired months and gross exposure are checked before comparison. Formation eligibility never uses future-month membership. All comparisons remain subject to static-survivor bias and monthly-only drawdown. Target weights ignore drift for trading-cost calculation; this is a shared approximation, not verified broker execution. No claim of broad-market alpha or untouched holdout validation.
