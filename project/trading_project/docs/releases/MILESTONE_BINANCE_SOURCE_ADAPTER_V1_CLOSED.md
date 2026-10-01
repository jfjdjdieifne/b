# Milestone Release — Binance Source Adapter V1 CLOSED

## Closure authority

Independent final audit decision:

```text
ACCEPTED FOR CLOSURE
```

Product Owner explicitly authorized closure (OWNER AUTHORIZATION — CLOSURE ONLY). Closure changed
documentation, status, release files, and `MANIFEST.sha256` only. Production (`src/`) and tests
(`tests/`) were not modified during closure.

Accepted Binance Source Adapter V1 implementation/test hashes (the complete 7-file artifact —
4 source files + 3 test files; the certificate is not reduced):

```text
267384be8e6c32f5b6e0d0fa803f9974622797bea12ffa199501b739f9eb11bb  src/trading_system/sources/__init__.py
7c4eac638a8f651c651e4f3d2f4ddb12496ea9ca54037f44ff430bffcd71be7b  src/trading_system/sources/binance_spot_minute_facts_source.py
97b2afc3a2f6d7512cd24c6435bb3ec7c1e9aca526fa523a69333b3dcad45006  src/trading_system/sources/binance_spot_kline_ohlc_source.py
1da6b8724be31d8cddfd9ce50d030697ea1f4f09e87ce1fb579f498f6730bfda  src/trading_system/sources/binance_executed_flow_source.py
e277551cd0b51c75b2a0de05a1314f06a1695f5678548e078a9dded2280b6e23  tests/test_binance_spot_minute_facts_source.py
aa5947a135d7c4d4d496345e87f99b5ed02ffb47315f2d5508e728563a2f169e  tests/test_binance_spot_kline_ohlc_source.py
9bfa82a2a01c68074fc4402ff2bb428fdf0caffc058abc20b05a11896c158744  tests/test_binance_executed_flow_source.py
```

All accepted `src/` and `tests/` files are listed in:

```text
docs/releases/MODULE_BINANCE_SOURCE_ADAPTER_V1_ACCEPTED_SRC_TESTS.sha256
```

## Certified baseline

```text
1045 collected
1045 passed
exit code 0
```

Binance Source Adapter V1 dedicated coverage:

```text
45 passed
```

Arithmetic: prior CLOSED baseline 1000 + 45 adapter tests = 1045.

## Patch history

```text
V1          IMPLEMENTED — PENDING AUDIT (dual independent Binance Spot sources + executed/initiated
            flow source + exact cross-witness; 45 dedicated tests / 1045 full); independent final
            audit: ACCEPTED FOR CLOSURE
V1          CLOSED
```

## What closure certifies

Binance Source Adapter V1 establishes the **dual independent Binance Spot source layer and the
executed/initiated-flow source** over the CLOSED 3.1/3.2 public reuse boundary:

- **Binance published Kline OHLC source contract** — the 12-column Binance kline artifact schema
  (Spot >= 2025-01-01 microsecond timestamp unit; `close_time = open_time + interval - 1us`;
  canonical minute mapping at `CLOSE_TIME`). Kline is a Binance-published bar fact;
- **Binance executed/initiated-flow source contract** — `buy_volume` / `sell_volume` / `volume`
  derived from `buy_initiated_base_volume` / `sell_initiated_base_volume` / `base_volume` with
  `buy + sell == volume` exactness and single declared base-unit semantics;
- **exact cross-witness** between the kline source and the minute-facts source (Decimal exactness —
  no tolerance — for minute key, high, low, base volume, quote volume, taker-buy base, and
  taker-buy quote under literal-precision compatibility; `number_of_trades` / `agg_trade_count`
  declared `NON_COMPARABLE_PAIRS` and never compared; unambiguous O/C = EXPECTED_MATCH; ambiguous
  O/C never demanded equal);
- **SOURCE_INCONSISTENCY fail-closed** — any unexpected cross-witness divergence raises
  `SourceInconsistencyError`; no skip, no silent repair, no coercion;
- **CLOSE_TIME semantics** — canonical timeline mapping at kline `CLOSE_TIME` only; build-list
  coverage maps are half-open `[start, end)` from minute starts, never from closes;
- **generic source adapters** — symbol/period/market-type generic over any Binance Spot artifact
  satisfying the contract; no instance hard-coding inside production;
- **public reuse boundary for 3.1/3.2** — the executed-flow source consumes only the CLOSED public
  3.1/3.2 API; 3.1/3.2 were not modified.

Closure semantics preserved verbatim:

- `TIE_ORDER_CONTRACT = NOT_PROVEN` always. Ambiguous open/close stays ambiguous
  (`open_ambiguous` / `close_ambiguous`); reconstructed open/close are deterministic convention
  witnesses (`_reconstructed_open_witness` / `_reconstructed_close_witness`) and are never
  canonical OHLC; canonical O/C comes from the kline source exclusively; no tie-break is invented.
- **ACTUAL** here means only: `EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT` according to the source's
  own semantics (aggressor-side initiated executed base volume as published by Binance Spot).
- **ACTUAL does NOT mean:** order-book truth, buying pressure, institutional activity, whale
  activity, or market-wide flow.
- **Historical generating provenance: NOT_CERTIFIED** beyond the bound source artifacts.

## Accepted limitations (NON-BLOCKING — recorded as constraints/debts; not fixed during closure)

1. The verbal API labels were decided at BUILD time under the documented IMPLEMENTED policy
   (`EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT`, `NON_COMPARABLE_PAIRS`,
   `TAKER_BUY_LITERAL_PRECISION_INCOMPATIBLE`); open to auditor view, settled by owner acceptance.
2. `bind_rank` is presented as `open_effective_lower/upper` + `close_effective_lower/upper`
   (owner correction); `bind_rank` itself survives only inside `tie_break_canonical_convention`.
3. Internal `_reconstructed_open_witness` / `_reconstructed_close_witness` columns appear on
   `exact_frame` copies; the canonical builder copies the six official columns only.
4. The sealed-timeline count test reads the causal truth
   (`ReplayBoundarySystem.compute_exact_pre_visible_seq`) and does not hard-code the studied 30.
5. `sources/__init__.py` is the contract/entry-point module re-exporting the public loaders.
6. One fixture row uses byte-parse tolerance (TEST-FIXTURE-ONLY); production parsing is strict.
7. `.pytest_cache/` runtime noise is excluded from the manifest by convention.

These are recorded as constraints/debts. None were modified, hardened, or fixed during closure.

## What closure does NOT certify

- predictive edge;
- profitability;
- strategy;
- model;
- PnL;
- live availability.

## Open debts preserved

```text
RESEARCH-DEBT-020 / 021 / 022 / 023 / 024 / 025
```

No debt was silently closed. RESEARCH-DEBT-020..025 remain OPEN.

## Not started

```text
Reality Check (local pipeline reality check)         NOT STARTED
Stage 4C-2 HTF structure / MTF confluence            NOT STARTED
model / strategy / PnL                               NOT STARTED
RESEARCH-DEBT-020..025 processing                    NOT STARTED
```

## Final state

```text
Binance Source Adapter V1
CLOSED

Certified baseline:
1045 collected
1045 passed
```
