# Module 2.1A V1.1 — Causal Adaptive Swing Detector

Status: **CLOSED V1.1**

No CLOSED module was modified. The detector still excludes HH/HL/LH/LL, BOS, CHoCH, liquidity, zones, and trading signals.

## V1.1 semantic split

Empirical history is now outcome-specific:

```text
continuation_reversal_history
    episodes replaced by a strict same-side extreme
    used for evidence and confirmation threshold

confirmed_reversal_history
    episodes ending in confirmed swings
    diagnostic only; never recalibrates V1.1 threshold
```

`EmpiricalConfirmationPolicy` now accepts explicit:

```python
EmpiricalConfirmationPolicy(
    quantile=<required>,
    prior_continuation_reversals=(),
    prior_confirmed_reversals=(),
)
```

The threshold and reversal evidence read only continuation history. On a confirmed event, the confirmed episode maximum is ranked against prior confirmed episodes and then pushed to that separate diagnostic tracker.

## Read-before-record order

On a confirmation row:

1. rank current reversal against prior continuation episodes;
2. read threshold from prior continuation episodes;
3. decide confirmation;
4. record current maximum in confirmed diagnostics only.

Therefore:

- `swing_continuation_history_count` is the pre-decision baseline count;
- `swing_confirmed_history_count` is the prior confirmed-diagnostic count;
- `swing_confirmed_history_percentile` is diagnostic only;
- end-of-bar `candidate_confirmed_history_count` includes the newly recorded confirmed episode;
- `candidate_continuation_history_count` remains unchanged by confirmation.

## Candidate-side naming

The public column is now:

```text
candidate_side = HIGH | LOW | UNDECIDED
```

It means only which wick-extreme candidate is being tracked. It is not trend, bullish/bearish direction, or market-structure classification. The old `candidate_direction` name is not retained as an alias.

## Outside/replacement-bar exclusion

A strict new extreme bar cannot confirm and contributes no opposite-wick reversal to:

- current episode maximum;
- continuation history;
- confirmed history;
- any later threshold.

The V1.1 adversarial sequence verifies that a HIGH update from 111 to 115 on a bar with low=90 does not leak `25/115` into history. Only a later unambiguous `1/115` reversal is finalized when the next strict high replaces the candidate.

## Episode definitions

A continuation episode finalizes only when a strict same-side extreme replaces it. Its maximum finite reversal fraction is pushed once.

A confirmed episode finalizes only when the injected policy confirms it. Its maximum is stored once in confirmed diagnostics and never in continuation calibration.

Per-bar evolving reversal observations are never pushed.

## Bootstrap limitation

- No policy: evidence-only, no confirmed swings.
- Empty continuation history: empirical policy cannot confirm.
- Explicit continuation priors are an external modeling assumption.
- Failed/replaced episodes can populate the continuation baseline.
- Confirmed episodes cannot bootstrap or drift that baseline.

## Results

Self-verification:

```text
MODULE 2.1A V1.1 SELF-VERIFICATION PASSED
Swing events are visible only at causal confirmation rows.
```

Module-specific suite:

```text
............................                                             [100%]
```

28 tests passed.

Full suite:

```text
........................................................................ [ 56%]
.......................................................                  [100%]
```

127 tests passed.

## New V1.1 tests

1. Confirmed swing does not change continuation threshold/count.
2. Failed/replaced episode changes continuation threshold exactly once.
3. Outside-bar ambiguous wick never appears in a later episode maximum or threshold.
4. Pre-decision continuation count and post-record confirmed count are separated.
5. Module 0.1 truncation/state audits rerun through the full suite.

## Meaning of “Adaptive”

“Adaptive” means empirical calibration from **PRIOR continuation episodes** when an explicit confirmation policy is supplied.

It does **not** mean:

- parameter-free
- automatically optimal
- self-bootstrapping
- learned from future outcomes

## Still-open design facts

1. Continuation-episode maximum reversal may contain duration bias; this is recorded as `RESEARCH-DEBT-002` and is not a causality/look-ahead defect.
2. HIGH and LOW continuation episodes share one dimensionless continuation distribution. Splitting by side would be a different estimator and remains an audit decision.
3. Initial candidate side is selected by the first bar extending only one initial boundary; this is state-machine initialization, not market direction.
4. Evidence-only mode cannot alternate without an explicit confirmation policy.
5. Caller-supplied priors require compatible provenance that V1.1 cannot verify.
6. Exact empirical ranking inherits `PERFORMANCE-DEBT-001`.
