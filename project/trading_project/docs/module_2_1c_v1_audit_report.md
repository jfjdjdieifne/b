# Module 2.1C V1.1 — Causal Structural Break Engine

Status: **CLOSED V1.1**

No CLOSED module was modified.

## V1.1 production validation change

Production `CausalStructuralBreakEngine.analyze()` no longer instantiates or executes `ConfirmedSwingSequenceEngine`.

It validates consumed Module 2.1A/2.1B contracts directly:

- allowed `structure_event_type` values;
- allowed HIGH/LOW sequence-class families;
- event flag/type/class correspondence;
- simultaneous HIGH+LOW rejection;
- current structure price/origin/confirmation equality with 2.1A metadata;
- confirmation position equals current row;
- same-DataFrame positional bounds;
- first-event `UNCLASSIFIED`/no-comparison semantics;
- later same-type comparison availability;
- previous same-type metadata links to the last confirmed same-type event;
- missing metadata on non-event rows;
- finite log-change presence for positive comparable prices.

V1.1 deliberately does not recalculate HH/LH/EH/HL/LL ordering in production. Exact upstream recomputation remains available in tests/self-verification only.

## Exact processing order

1. Snapshot sequence-derived state and latest eligible references known before the row.
2. Evaluate factual first wick/close breaches against those prior references.
3. Interpret first close breaches using `structure_state_before`.
4. Rank all current first overshoots against prior wick/close histories.
5. Push finite first-event magnitudes only after all same-row reads.
6. Process the current Module 2.1B sequence event.
7. Recompute `structure_state_after` from sequence classes only.
8. Install newly confirmed HIGH/LOW references for subsequent rows only.

Raw breaks do not independently invalidate or rebuild sequence-derived state in V1.1.

## Sequence-derived state table

```text
latest HIGH   latest LOW   state
-----------   ----------   ----------------
missing       any          UNDEFINED
any           missing      UNDEFINED
HH            HL           UP_STRUCTURE
LH            LL           DOWN_STRUCTURE
other pair                 MIXED
```

EH/EL remain neutral/conflicting and lead to `MIXED` after both comparable sides exist.

## Latest-reference monitoring

`monitored_high_*` and `monitored_low_*` describe only the latest confirmed structural references. They are not a complete persistent lifecycle registry.

A same-type replacement removes the superseded level from 2.1C monitoring on subsequent rows. Historical output rows remain unchanged. Full historical liquidity-level lifecycle belongs to Module 2.2.

Positional outputs are now allocated and stored directly as nullable `Int64`, without float intermediates.

## Wick evidence clarification

`high_wick_break_evidence` / `low_wick_break_evidence` rank the first wick overshoot for **any** first wick breach, including a bar that also closes beyond the level.

This is not sweep evidence.

`high_wick_only_breach_event` / `low_wick_only_breach_event` separately identify the factual wick-breach-without-same-bar-close condition.

Wick and close distributions remain separate. HIGH/LOW sides share each dimensionless distribution. Same-row events all read the same prior history before any same-row push.

## Terminology note — D1.1

`BOS_UP`, `BOS_DOWN`, `CHOCH_UP`, and `CHOCH_DOWN` are **project operational structural interpretation labels**. They are not claimed to reproduce literal/canonical Michael J. Huddleston terminology or exact ICT rules.

Project-semantic documentation aliases:

```text
BOS_UP / BOS_DOWN
    continuation-direction structural break

CHOCH_UP / CHOCH_DOWN
    opposite-direction structural shift candidate
```

These descriptions are project semantics, not ICT quotations. The preliminary source audit found stronger primary evidence for the term **Market Structure Shift (MSS)** than for primary ICT attribution of **CHoCH**. Production fields remain unchanged to avoid API churn; this note changes no algorithm.

## Interpretation table

```text
pre-state        HIGH first close     LOW first close
---------------  -------------------  -------------------
UP_STRUCTURE     BOS_UP               CHOCH_DOWN
DOWN_STRUCTURE   CHOCH_UP             BOS_DOWN
MIXED            UNCLASSIFIED_BREAK   UNCLASSIFIED_BREAK
UNDEFINED        UNCLASSIFIED_BREAK   UNCLASSIFIED_BREAK
```

Both sides receiving first close breaches on one row yields `AMBIGUOUS_DOUBLE_BREAK`, while raw side facts remain visible. These labels are V1.1 operational definitions, not universal theory claims.

## Benchmark

Deterministic 20,000-row fixture, 7 timed runs after warm-up:

```text
V1 median:   311.019 ms
V1.1 median: 314.574 ms
Difference:  +3.555 ms (+1.14%)
```

The measured result is effectively performance-neutral on this runtime. The architectural gain is removal of mandatory duplicate 2.1B execution; no semantic optimization was introduced. Full details: `docs/benchmarks/module_2_1c_v1_to_v1_1.md`.

## Results

Self-verification:

```text
MODULE 2.1C V1.1 SELF-VERIFICATION PASSED
Prior eligible levels are evaluated before current swing events.
```

Module-specific suite:

```text
.........................                                                [100%]
```

25 tests passed.

Full clean-project suite:

```text
........................................................................ [ 40%]
........................................................................ [ 80%]
....................................                                     [100%]
```

180 tests passed.

## Added V1.1 tests

- malformed direct 2.1B contract rejection;
- production analyze succeeds while `ConfirmedSwingSequenceEngine.analyze` is monkeypatched to fail;
- malformed surface still rejects under that monkeypatch;
- superseded reference disappears from latest-reference monitoring;
- first wick overshoot enters wick evidence even when the same bar also closes beyond;
- direct nullable `Int64` positional output dtypes;
- prior causal/truncation/state/end-to-end chain tests remain passing.

## Unresolved design issues

1. Interpretation labels remain explicit operational definitions requiring empirical evaluation.
2. Latest-reference monitoring intentionally retires superseded levels; full registry behavior is outside 2.1C.
3. HIGH/LOW share distributions within each break kind; side-specific histories would define another estimator.
4. Zero-price breach magnitudes remain factual but cannot enter magnitude history.
5. Cross-chunk continuation is unsupported.
6. Direct validation checks linkage/availability semantics but intentionally does not recalculate 2.1B price-order classification.
7. Double close breaks preserve ambiguity rather than infer intrabar order.
