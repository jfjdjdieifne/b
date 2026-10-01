# LOCAL MINUTE PIPELINE — Converter (source boundary only)

`aggtrades_to_minute_facts.py` converts a Binance Spot **public-data aggTrades** CSV
(8 columns, no header, timestamps in **microseconds**) into a **1-minute fact-table
CSV** + a machine-readable **sidecar JSON**. Standard library only; streaming,
bounded memory; integer fixed-point from the original decimal strings.

This is a **SOURCE CONVERTER ONLY**. It does not run or reimplement any project
engine (volatility/session/swing/BOS/liquidity/order-flow/OB/FVG/HTF/...). Those
CLOSED engines are consumed later through their public contracts by an official
Source Adapter inside the project.

## Run

```bat
convert_aggtrades.bat "D:\MarketData\BTCUSDT-aggTrades-2026-05.csv"
:: or with an explicit output prefix:
convert_aggtrades.bat "D:\MarketData\BTCUSDT-aggTrades-2026-05.csv" "D:\out\facts"
:: or directly:
python tools\aggtrades_to_minute_facts.py "D:\MarketData\BTCUSDT-aggTrades-2026-05.csv" --out "D:\out\facts"
```

Outputs `<prefix>.csv` + `<prefix>.sidecar.json` (default prefix: `outputs\minute_facts_<source-stem>`).
Paths with spaces are supported. The source file is never modified or copied.

## Contract highlights

- **minute** = `floor(transact_time_us / 60_000_000)`; interval **[start, end)** in
  trade-time membership. `bar_close_availability = NOT_CLAIMED_BY_CONVERTER`.
- **Fail closed** on any corruption (row number + error class; no silent skip /
  repair / coercion / auto-sort). Exit codes: 0 OK, 2 usage, 3 corruption.
- **Official sentinel** rows (`price=0 AND qty=0 AND first=-1 AND last=-1`,
  changelog 2022-04-12) are counted + recorded in the sidecar, never aggregated,
  never silently dropped.
- **Tie order**: `TIE_ORDER_CONTRACT = NOT_PROVEN` (no official guarantee for
  equal `transact_time_us` rows). Policy = ambiguity metadata: deterministic
  `(transact_time_us, agg_trade_id)` pick + `open_ambiguous`/`close_ambiguous` flags.
- **Flow naming**: `executed/initiated` only (`is_buyer_maker=False` →
  `buy_initiated`). No pressure/participant/book-state claims.
- **Empty minutes** are absent (no synthetic bars); missing ranges are counted in
  the sidecar.
- Reconciliation is exact (integer fixed-point; Σ base/quote match the source).

## Tests

```bat
python -m pytest tools/tests_local/ -q
```

35 adversarial tests with manual fixtures (the owner's real file is never used).
Mutation proofs and memory/scale measurements are documented in
`deliverables/19_LOCAL_MINUTE_PIPELINE_IMPLEMENTED.md`.
