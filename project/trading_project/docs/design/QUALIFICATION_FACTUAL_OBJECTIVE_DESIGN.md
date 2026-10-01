# DESIGN ONLY — Qualification / Factual Learning Objective (Module 6.2B-2)

```text
Status:   DESIGN PROPOSAL — NOT IMPLEMENTED
Scope:    Research-objective definition only
Debts:    RESEARCH-DEBT-020, -023, -024 (and -025 where binding)
Rule:     No code. No model. No geometry/execution. No trade label.
```

This document answers the central question: **what is the future that research
is allowed to watch, and how does it become a learning question without a magic
horizon or a trade assumption?**

It is a DESIGN PROPOSAL for the Product Owner. Nothing here authorizes a build.

---

## 1. The core thesis

We do **not** teach the brain "win = 1 / loss = 0". We also do not teach it "if
price rose within N bars = success". Both throw away the shape of the future.

Instead we define a **multi-dimensional factual outcome vector** — a structured
description of *how the hypothesis path actually unfolded*, observed causally
and ending only when the hypothesis itself factually ends (or is honestly
censored). Later geometry decides what, if anything, is exploitable; the brain
learns the shape of the future first, uncontaminated by entry/stop/target.

```text
Hypothesis at creation
        |
        v
Factual path (causal, as-of)
        |
        v
Termination event (structure-defined)  OR  right-censored at boundary
        |
        v
Outcome vector Y (multi-dimensional, factual, not a trade)
```

---

## 2. What already exists that we must build on (not reinvent)

CLOSED Module 6.2A-1 already records, factually and causally:

- three terminal lifecycle states:
  - `CONTRADICTED`
  - `SUPERSEDED`
  - `OBSERVED_DIRECTION_ESTABLISHED`
- a fourth non-terminal condition: `RIGHT_CENSORED_AS_OF_BOUNDARY`
- three path segments:
  - `PRE_ENDPOINT` (bars after creation, before the terminal bar)
  - `ENDPOINT_BAR` (the terminal bar itself)
  - `OBSERVED_THROUGH_AS_OF` (when censored — everything visible up to boundary)
- per-segment excursion facts already computed from a **non-executable research
  reference mark** (creation completed close, `reference_is_execution_price=False`):
  - `favorable_excursion_fraction`
  - `adverse_excursion_fraction`
  - extreme prices and their positions
  - `same_bar_order_ambiguous` (bar straddled the reference; intrabar order unknowable)
- four hypothesis types with an explicit `direction` (UP/DOWN):
  - `UPWARD/DOWNWARD_CONTINUATION_AFTER_PROJECT_BREAK`
  - `UPWARD/DOWNWARD_TRANSITION_AFTER_PROJECT_SHIFT`
- a closed as-of/visibility firewall, temporal eligibility gate, and walk-forward
  dataset (6.2A-0 through 6.2A-3).

The design below **reuses these facts**. It adds a learning objective layer on
top of them; it does not alter the CLOSED outcome contract.

---

## 3. The non-negotiable design laws

1. **No magic horizon.** The observation ends at a *factual termination event*
   or at the as-of boundary — never at an arbitrary bar count.
2. **No entry/stop/target contamination.** Excursions are measured from the
   research reference mark, not from a traded price. No fill, fee, slippage, or
   position assumption enters the objective.
3. **Censoring is a first-class outcome, not a missing row.** A hypothesis that
   never terminates before the data ends is `RIGHT_CENSORED`; it must never be
   silently dropped or recoded to 0.
4. **Competing causes are kept distinct.** `CONTRADICTED`, `SUPERSEDED`, and
   `DIRECTION_ESTABLISHED` are three different endings. They are never folded
   into one binary "worked / didn't".
5. **Order ambiguity is preserved.** When a bar straddles the reference, the
   within-bar ordering is unknowable and is flagged, not guessed.
6. **The objective is descriptive/factual, not a probability.** It records what
   happened; it does not claim a probability of what will happen.
7. **No statistical-independence claim.** Overlapping hypotheses are dependent;
   the objective records the dependence structure, it does not pretend samples
   are IID.
8. **Causal only.** Every component at row i depends only on information
   available at or before the observing as-of key.

---

## 4. The multi-dimensional outcome vector `Y`

`Y` is a set of *factual dimensions*, each separately typed and separately
interpretable. A future learner may use any subset; geometry later decides
exploitability. There is **no scalar collapse**.

### Dimension A — Factual termination class (categorical, resolves 020/023)

```text
termination_class ∈ {
  DIRECTION_ESTABLISHED,   # the hypothesis's expected direction factually confirmed by structure
  CONTRADICTED,            # opposing structure appeared first
  SUPERSEDED,              # a newer hypothesis replaced it in its own chain
  RIGHT_CENSORED           # none of the above before the as-of boundary
}
```

This is the *lifecycle* outcome. It answers: "how did this hypothesis actually
end (if it ended)?" It is taken directly from CLOSED lifecycle facts. We do not
invent a fifth class.

For censored rows we additionally record how much of the path *was* seen (see
Dimension D), so censoring is informative rather than blank.

### Dimension B — Directional realization (factual magnitude, normalized)

How much of the expected move actually materialized, and in which direction,
measured to the termination event (or as-of for censored):

```text
favorable_excursion_fraction       # existing fact (expected direction)
adverse_excursion_fraction         # existing fact (against it)
realized_directional_balance       # = favorable - adverse  (signed net excursion)
```

Crucially these are **context-normalized** so that "a 1% move" means different
things in a dead market vs a violent one. We normalize against a *causally
available* volatility unit already produced by Layer 1 (e.g. creation-bar /
recent realized true-range context), producing a dimensionless "how many
context-vol units moved". This is a scale/unit choice, not a threshold:

```text
favorable_in_context_units = favorable_excursion_fraction / context_vol_unit
adverse_in_context_units   = adverse_excursion_fraction / context_vol_unit
```

`context_vol_unit` must be defined from information available at creation (Layer
1 volatility), never from future bars. This is a design contract — the exact
normalizer is specified in the build and audited for look-ahead.

### Dimension C — Path character / ordering (this is the valuable part)

This is what binary labels destroy. We want the brain to learn *how* the path
felt, because that is what determines whether a correct call is even tradeable:

```text
adverse_before_favorable      # bool: did price go against the hypothesis first?
favorable_first_then_adverse  # bool: did it move correctly then reverse before termination?
capture_efficiency            # favorable / (favorable + adverse) — how "clean" was the path
adverse_drawdown_peak_ratio   # peak adverse before favorable extreme, relative to final favorable
time_to_favorable_extreme     # position offset (bars) of favorable extreme from creation
time_to_termination           # position offset of termination from creation
```

These dimensions are what let the system later discover statements like:

- "continuation usually works, but after a large adverse excursion first"
  → analysis is good, immediate chasing is bad; geometry needs a pullback entry.
- "expected move arrives fast with very little adverse"
  → a different, more aggressive geometry may apply.
- "direction is right but the available move is small"
  → possible informational edge that is not tradeable after costs.

`time_to_*` here is **not a magic horizon**: it is a factual measurement of
*when the observed extreme/termination occurred*, recorded as a feature of the
path, not a cutoff imposed on it. Hypotheses may legitimately take very
different lengths; that variation is signal, not something to normalize away.

When `same_bar_order_ambiguous` is true, any "which came first within the bar"
dimension is set to `UNKNOWABLE` rather than guessed (Dimension F).

### Dimension D — Maturity / observability depth (for censored rows)

For a `RIGHT_CENSORED` hypothesis we still record what was seen:

```text
observed_path_bar_count             # how many future bars were actually observed
observed_favorable_excursion        # best favorable move seen before censor
observed_adverse_excursion          # worst adverse seen before censor
censoring_reason                    # DATA_BOUNDARY | WALK_FORWARD_BOUNDARY
maturity_flag ∈ { MATURE, CENSORED }
```

This directly answers DEBT-023: censored rows carry a real, non-empty outcome
("we watched N bars, saw X favorable / Y adverse, then ran out of data") and are
eligible for censor-aware methods later — they are never deleted.

### Dimension E — Structural coherence (factual, not scored)

Did the path align with the structural story, independent of profit:

```text
terminal_state                    # existing CLOSED fact
establishment_before_contradiction # bool, where both occurred and order is knowable
supersession_chain_depth          # how deep in a replacement chain it ended
```

These come from the CLOSED narrative/lifecycle ledger. No weighting is attached.

### Dimension F — Epistemic / quality flags (never folded into the label)

```text
same_bar_order_ambiguous     # existing fact; within-bar order unknown
reference_mark_semantics     # always CREATION_CLOSE_NON_EXECUTABLE
provenance/source mode       # ACTUAL / PROXY separation preserved
```

These stay as separate columns so a later model can choose to down-weight or
stratify ambiguous rows, instead of the objective silently pretending the
ambiguity doesn't exist.

---

## 5. How this resolves each open debt (design intent)

### RESEARCH-DEBT-020 — Lifecycle termination semantics

Resolved at the **design** level by anchoring termination to the existing
factual lifecycle states rather than a TTL or bar count:

- continuation/transition hypotheses end on `CONTRADICTED`, `SUPERSEDED`, or
  `OBSERVED_DIRECTION_ESTABLISHED`;
- if none occurs before the as-of boundary, the row is `RIGHT_CENSORED`.

No fixed expiry/decay is introduced. (This *defines* the semantics; the
statistical treatment of censored rows is DEBT-023, kept separate.)

### RESEARCH-DEBT-023 — Censoring / competing-risk estimand

The objective makes the four termination classes explicit and preserves censored
rows with real content. This does **not** choose a survival/competing-risk
estimator yet — that is a later, separately-authorized model-design step. What
this design guarantees is that when that step happens, the data has:

- a clear event indicator (which class, or censor);
- an observed-time/offset measurement;
- no silent recoding or dropping.

In formal terms the design supports a **competing-risks-ready** outcome table
(event + observed path + censor indicator) without prematurely picking Fine-Gray,
cause-specific hazards, or multi-state models.

### RESEARCH-DEBT-024 — Overlapping-hypothesis dependence / non-IID

The objective does **not** delete or embargo hypotheses to force independence.
Instead it records the dependence keys so later validation can be
dependence-aware:

```text
supersession_chain_id / parent_hypothesis_id
label_interval_start / label_interval_end (already in 6.2A-2)
overlap_count_within_split (already in metadata)
shared_path_group_key        # hypotheses whose observed future paths overlap the same bars
```

This enables, later and by separate design: grouped/clustered evaluation,
supersession-chain folds, or temporal-block walk-forward. Raw sample count is
never presented as independent evidence.

### RESEARCH-DEBT-025 — Reference price / market time

The objective keeps `reference_is_execution_price = False` and the
`CREATION_ROW_COMPLETED_CLOSE_RESEARCH_REFERENCE_MARK`. Every excursion is
explicitly a non-executable research measurement. Venue timestamps, corrected
bars, intrabar versions, and contract rolls remain out of scope and are
documented as known limits; they must be resolved before any geometry/execution
layer, not by the learning objective.

---

## 6. The conceptual picture: outcome, not label

```text
                                FACTUAL OUTCOME VECTOR Y
+-------------------------------------------------------------------+
| A  termination_class     (4-state categorical, includes censor)   |
| B  directional_realization (favorable/adverse/net, context-normal)|
| C  path_character         (ordering, efficiency, timing)          |
| D  maturity/observability (mature vs censored + observed depth)   |
| E  structural_coherence   (terminal facts, chain depth)           |
| F  epistemic_flags        (ambiguity, reference semantics, mode)  |
+-------------------------------------------------------------------+
        |                                                      |
        |  no scalar collapse                                   |
        v                                                      v
  later LEARNING describes                        later GEOMETRY decides
  P(Y | evidence at creation)                     what subset is exploitable
  (with dependence-aware validation)              (entry/stop/target/fees)
```

The brain learns the *distribution/shape* of the future conditional on evidence.
Geometry is a separate, later consumer that asks questions like "among paths
with high favorable excursion and low adverse-first, is there a tradeable
construction after costs?" — questions we cannot honestly ask until Y exists.

---

## 7. What this design deliberately does NOT do

- It does not collapse Y to a scalar score or win/loss.
- It does not pick a statistical estimator, model, or loss.
- It does not set any qualification threshold.
- It does not define entry, stop, target, position size, fees, slippage, or fill.
- It does not claim the research reference mark is tradeable.
- It does not force IID by deleting/embargoing overlapping hypotheses.
- It does not guess intrabar order when a bar is ambiguous.
- It does not close DEBT-025 (venue/time alignment) — it walls it off.
- It does not authorize code. It is a design proposal only.

---

## 8. Proposed module identity (for later authorization)

```text
Module:           6.2B-2 — Factual Multi-Dimensional Research Objective
Predecessor:      6.2B-1 V1.1 CLOSED (descriptive calibration foundation)
Consumes:         6.2A-1 factual outcomes, 6.2A-2 intervals, 6.2A-3 dataset,
                  Layer 1 causal volatility context, B-0 reasoning snapshots
Output type:      factual outcome vector table + objective contract manifest
Predictive:       no
Probability:      no
Trade semantics:  no
Estimator:        not selected (competing-risks-ready only)
```

A future `BUILD ONLY` task block would specify: exact column schema and types,
the exact causal `context_vol_unit` normalizer, the precise event/offset
definitions, the dependence keys, and the full adversarial test plan
(truncation, future-mutation, censor-preservation, ambiguity-preservation,
A→A/A→B→A/fresh-instance/input-immutability, and dependence-key correctness).

---

## 9. Open design questions for the Product Owner

These need a decision before any BUILD authorization; they are deliberately not
silently chosen:

1. **Context normalizer for Dimension B:** use creation-bar normalized true
   range, a trailing causal window (e.g. recent realized range), or record both?
   (This is a unit choice, not a threshold — but it must be fixed and audited.)
2. **Establishment definition for transition hypotheses:** `OBSERVED_DIRECTION_ESTABLISHED`
   exists in CLOSED facts; do we accept it as-is for `DIRECTION_ESTABLISHED`, or
   does the design need an additional structural-strength descriptor (without
   weighting)? (Recommend accepting the CLOSED fact as-is to avoid patching a
   closed module.)
3. **Timing unit:** record offsets as bar positions only now, and defer real
   time/DST handling to DEBT-025? (Recommend yes.)
4. **Scope of first build:** all four hypothesis types at once, or one
   (e.g. continuation) first as a narrower audited pilot?

---

## 10. Recommendation

**Adopt this direction.** The user's instinct is correct: a multi-dimensional
factual outcome vector is strictly more powerful and more honest than a binary
label, and it is the only design that lets later geometry exploit *path shape*
rather than just terminal direction. It resolves DEBT-020 at the design level,
makes DEBT-023/024 tractable without prematurely choosing statistics, and keeps
DEBT-025 correctly walled off from learning.

Next step is a Product-Owner decision on the open questions in §9, after which a
separate, explicit `BUILD ONLY` task block for 6.2B-2 can be authorized.
