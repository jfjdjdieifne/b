# D1 — ICT/SMC Domain Source-of-Truth Audit

**Status: PRELIMINARY SOURCE AUDIT — ACCEPTED**

**Scope:** research/documentation only. No `src/`, tests, or CLOSED module was modified.

This is not a FINAL source-of-truth certification. `RED=0` means no verified contradiction was found within the evidence available to this audit; it does **not** mean every ICT definition was verified from a primary source.

## Method and epistemic limits

This audit separates methodology attribution from empirical truth. A verified ICT definition establishes how the methodology describes a concept; it does **not** establish institutional causation or predictive edge. Primary-source priority was applied, but reliable full official-video transcripts/timestamps were not consistently accessible. No quote or timestamp was invented. See `SOURCES.md`.

## Findings by concept

### 1. Buy-Side / Sell-Side Liquidity
- **Primary terminology:** BSL/SSL appears consistently in ICT teaching metadata/community lineage; exact primary transcript not captured.
- **Primary source:** official ICT channel; 2022 Mentorship Episode 3.
- **Confidence:** MEDIUM.
- **Observable fact:** confirmed/high-side or low-side price references and subsequent OHLC interaction.
- **Interpretation:** stops/resting orders above highs or below lows are not observable from OHLC.
- **Project:** Module 2.2 `HIGH_SIDE`/`LOW_SIDE` candidates.
- **Relationship:** INTENTIONAL_DEPARTURE; honest factual naming.
- **Severity / impact:** GREEN / NONE.

### 2. Liquidity sweep / raid
- **Confidence:** MEDIUM-LOW; official transcript/timestamp not verified.
- **Observable:** strict wick-through, close relation, reclaim.
- **Interpretation:** stop raid/manipulation intent.
- **Project:** factual wick-only/close/reclaim events in 2.2; avoids “sweep” as proof.
- **Relationship:** INTENTIONAL_DEPARTURE.
- **Severity / impact:** GREEN / NONE.

### 3. Displacement
- **Primary terminology:** ICT uses displacement/energetic movement in mentorship material; exact universal formula was not verified.
- **Confidence:** MEDIUM.
- **Observable:** price displacement and candle geometry.
- **Project:** 4.1 scale-invariant displacement evidence.
- **Relationship:** APPROXIMATION; project metric is not claimed as literal primary formula.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY.

### 4. Market Structure Shift (MSS)
- **Primary source:** official 2022 Mentorship Episode 3 title explicitly says “Market Structure Shifts.”
- **Confidence:** HIGH for terminology; MEDIUM for detailed rule due transcript limitation.
- **Observable:** confirmed structural-level close break plus prior sequence state.
- **Project:** 2.1C operational structural-break model.
- **Relationship:** APPROXIMATION.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY.

### 5. BOS
- **Primary attribution:** secondary comparisons commonly distinguish broader SMC “Break of Structure” from ICT’s MSS/displacement framing. No strong primary ICT transcript proving BOS as canonical ICT terminology was captured.
- **Confidence:** LOW as primary ICT attribution.
- **Project:** 2.1C explicitly calls BOS an operational V1 label.
- **Relationship:** TERMINOLOGY_ONLY / intentional operational use.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY.

### 6. CHoCH / Change of Character
- **Primary attribution:** no reliable primary ICT evidence found. Secondary sources conflict: some market it as ICT; an ICT-vs-SMC comparison attributes CHoCH mainly to broader SMC and MSS to ICT.
- **Confidence:** LOW.
- **Project:** 2.1C operational `CHOCH_*`, already documented as non-universal.
- **Relationship:** TERMINOLOGY_ONLY.
- **Severity / impact:** YELLOW / VERSIONED_PATCH_REQUIRED **for documentation naming/alias clarification only**, not algorithmic behavior.

### 7. Order Block
- **Primary terminology:** strongly associated with ICT, but no verified primary transcript supporting “most recent opposite candle in the causal leg” as the complete literal definition.
- **Confidence:** MEDIUM for term; LOW-MEDIUM for selector rule.
- **Observable:** historical opposite-body candle, immutable zone, later interactions.
- **Interpretation:** institutional orders/source.
- **Project:** 4.1 explicitly calls it a candidate and declares the selector heuristic.
- **Relationship:** APPROXIMATION.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY; `RESEARCH-DEBT-009` remains appropriate.

### 8. Mitigation Block
- **Primary evidence:** insufficient verified primary text.
- **Project:** NOT_IMPLEMENTED; touch is factual and not called mitigation.
- **Severity / impact:** GRAY / FUTURE_MODULE.

### 9. Breaker Block
- **Primary evidence:** term is widely attributed to ICT, but precise prerequisite sequence was not verified from primary transcript.
- **Project:** NOT_IMPLEMENTED; far-side violation/reclaim facts only.
- **Relationship:** NOT_IMPLEMENTED.
- **Severity / impact:** GRAY / FUTURE_MODULE; `RESEARCH-DEBT-008` required.

### 10. Fair Value Gap
- **Primary terminology:** strongly established in ICT material lineage.
- **Confidence:** MEDIUM-HIGH for term; MEDIUM for exact primary transcript.
- **Observable:** three-candle non-overlap geometry.
- **Project:** 4.2A strict `low[i] > high[i-2]` / inverse geometry, causal creation at bar three.
- **Relationship:** MATCH on operational geometry, intentional departure on “inefficiency” claims.
- **Severity / impact:** GREEN / NONE.

### 11. Inverse/Inversion FVG
- **Primary evidence:** insufficient verified official transcript for exact role-reversal prerequisites.
- **Project:** NOT_IMPLEMENTED; facts preserved under `RESEARCH-DEBT-010`.
- **Severity / impact:** GRAY / FUTURE_MODULE.

### 12. Consequent Encroachment (CE)
- **Primary terminology:** commonly used for midpoint/50% of an imbalance; direct official transcript not captured.
- **Confidence:** MEDIUM-LOW.
- **Observable:** arithmetic midpoint.
- **Project:** 4.2A exposes midpoint as geometry only, no CE event/signal.
- **Relationship:** INTENTIONAL_DEPARTURE.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY.

### 13. Dealing Range
- **Primary terminology:** established in ICT ecosystem; multiple range-selection formulations/eras likely.
- **Confidence:** MEDIUM for term, LOW-MEDIUM for one canonical pairing rule.
- **Project:** 4.2B sequential opposite confirmed-swing pairing.
- **Relationship:** APPROXIMATION; explicit candidate model.
- **Severity / impact:** YELLOW / DOCUMENTATION_ONLY; debts 012/013 remain.

### 14. Premium / Discount
- **Primary terminology:** established ICT dealing-range geometry.
- **Observable:** location relative to range midpoint.
- **Project:** un-clipped affine position/midpoint displacement; no signal.
- **Relationship:** MATCH geometrically, INTENTIONAL_DEPARTURE interpretively.
- **Severity / impact:** GREEN / NONE.

### 15. OTE
- **Primary source:** official/public ICT OTE Pattern Recognition playlist identified.
- **Primary ratios:** secondary ICT materials repeatedly cite a Fibonacci retracement region around 0.62–0.79 and commonly a 0.705 level, but exact primary video transcript/timestamps were not verified here.
- **Confidence:** HIGH for OTE terminology; MEDIUM-LOW for exact ratios in this audit.
- **Project:** NOT_IMPLEMENTED by design; no Fibonacci hardcoding.
- **Relationship:** INTENTIONAL_DEPARTURE / NOT_IMPLEMENTED.
- **Severity / impact:** GRAY / FUTURE_MODULE. Source fidelity does not require implementation.

### 16. PD Arrays
- **Primary terminology:** widely associated with ICT price-delivery arrays; complete canonical list varies across material/era and was not verified here.
- **Project:** individual factual candidates exist; no unified PD-array authority matrix.
- **Severity / impact:** GRAY / FUTURE_MODULE.

### 17. Kill Zones / Sessions
- **Primary terminology:** ICT teaching strongly emphasizes named time windows; exact schedules can vary by instrument/era/DST.
- **Project:** 1.2 accepts explicit IANA-timezone session definitions and assigns no predictive importance.
- **Relationship:** INTENTIONAL_DEPARTURE; safer general temporal context.
- **Severity / impact:** GREEN / NONE.

### 18. Judas Swing
- **Primary attribution:** commonly associated with ICT but no reliable primary transcript captured.
- **Project:** NOT_IMPLEMENTED.
- **Severity / impact:** GRAY / FUTURE_MODULE.

### 19. Balanced Price Range
- **Primary evidence:** insufficient primary verification in available research interface.
- **Project:** NOT_IMPLEMENTED; overlapping gaps are retained but not interpreted as BPR.
- **Severity / impact:** GRAY / FUTURE_MODULE.

### 20. Liquidity Void
- **Primary evidence:** insufficient verified primary definition.
- **Project:** NOT_IMPLEMENTED; no attempt to equate gaps/large candles automatically with liquidity voids.
- **Severity / impact:** GRAY / FUTURE_MODULE.

## Current-project crosswalk

| Module | Domain relationship | Audit result |
|---|---|---|
| 1.2 Sessions | General explicit session context, not ICT kill-zone signal | GREEN |
| 2.1A Swings | Causal operational swing confirmation, not asserted ICT fractal formula | YELLOW |
| 2.1B HH/HL/LH/LL | Generic factual sequence terminology | GREEN |
| 2.1C BOS/CHoCH | Operational labels; MSS is better-supported primary ICT terminology | YELLOW |
| 2.2 Liquidity | Factual HIGH_SIDE/LOW_SIDE candidates; avoids claiming orders | GREEN |
| 4.1 OB | Deterministic approximation, openly heuristic | YELLOW |
| 4.2A FVG | Three-candle geometry close to common ICT formulation | GREEN |
| 4.2B Range/P-D | Sequential candidate approximation; midpoint geometry factual | YELLOW |
| Debt 008 Breaker | Correctly deferred | GRAY |
| Debt 010 IFVG | Correctly deferred | GRAY |
| OTE | Intentionally not implemented | GRAY |

## Severity totals

```text
GREEN:  5
YELLOW: 7
RED:    0
GRAY:   8
TOTAL: 20
```

## RED findings

None. No current implementation was found to materially contradict a verified primary definition in a way requiring an immediate algorithmic patch.

## VERSIONED_PATCH_REQUIRED findings

No unresolved production patch is required.

The prior 2.1C terminology finding was resolved by D1.1 through documentation only: `BOS_*` and `CHOCH_*` remain stable API labels but are explicitly identified as project operational semantics. Primary ICT attribution of CHoCH remains unresolved in the review backlog.

## Additional primary-source review required

- Exact ICT order-block qualifiers across mentorship eras.
- Breaker and mitigation prerequisites.
- IFVG role-reversal sequence and terminology.
- Consequent Encroachment precise usage.
- OTE exact Fibonacci levels from official primary video timestamps.
- Canonical PD-array taxonomy.
- Kill-zone schedules by era/instrument and DST treatment.
- Judas Swing, Balanced Price Range, and Liquidity Void primary definitions.

## D1.1 terminology disposition

The documentation-only terminology correction is now applied:

- `BOS_UP/BOS_DOWN` = project **continuation-direction structural break** labels.
- `CHOCH_UP/CHOCH_DOWN` = project **opposite-direction structural shift candidate** labels.
- Neither label is represented as a literal ICT quotation or canonical Huddleston rule.
- Production names remain unchanged to avoid non-semantic API churn.

## Layer 6 eligibility rule

Existing factual/operational modules may enter Layer 6 empirical testing when consumed strictly under their **project feature names and documented project semantics**, without claims of literal ICT fidelity.

Concepts marked `NOT_IMPLEMENTED` are blocked from receiving Layer 6 weights until both a definition and an audited implementation exist. This currently includes Mitigation Block, Breaker interpretation, IFVG, OTE, unified PD Arrays, Judas Swing, Balanced Price Range, and Liquidity Void.

## Recommendation

```text
PRELIMINARY SOURCE AUDIT — ACCEPTED
```

The factual project features are eligible for empirical Layer 6 design under project semantics, but this task does **not** start Layer 6. Outstanding primary-source attribution work remains mandatory through `PRIMARY_REVIEW_BACKLOG.md`. No production algorithm patch is justified by D1/D1.1.
