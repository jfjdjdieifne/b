# Module 6.1A V1.3 — Causal Evidence Vector / Feature Contract

Status: **CLOSED V1.3**

The certified V1 path uses a closed immutable catalog and explicit frozen
configuration. No arbitrary runtime FeatureSpec enters the engine. Groups are
environment, temporal, structure, liquidity, zones, dealing range, multiscale,
and explicit ACTUAL/PROXY/NONE order-flow mode.

Output is a new index-preserving DataFrame containing only `ev__` allowlisted
columns plus evidence feature count, available count, and availability
fraction. COUNT_SUPPORT fields are emitted but excluded from the denominator.
Zero/False/NONE are available facts; NaN/NA remains unavailable. No fill,
persistence, recomputation, category encoding, score, weight, model, signal, or
outcome enters V1.

The deterministic manifest fields are feature/output/source names, module,
semantic type, missingness, event-local flag, support/freshness links, mode,
directional semantics, expected domain, and epistemic status. Aggregate
availability fields are generated metadata outside the feature manifest.

ACTUAL and PROXY catalogs are disjoint; NONE admits neither. Outcome-like input
columns are ignored by allowlist and defense-in-depth FeatureSpec checks reject
obvious registration attempts.

```text
Module tests: 54 passed
Full suite: 344 passed
```

```text
........................................................................ [ 20%]
........................................................................ [ 41%]
........................................................................ [ 62%]
........................................................................ [ 83%]
........................................................                 [100%]
```

Exact truncation, future mutation, append/prefix, idempotence, manifest
stability, upstream domain validation, leak defense, and real 1.1 + 3.1/3.2
integration passed.

Open debts: `RESEARCH-DEBT-018` redundancy/collinearity and
`RESEARCH-DEBT-019` reliability versus support. V1 intentionally builds no
scorer or learned feature selection.

V1.1 replaced heuristic catalog metadata with explicit per-feature contracts, validates catalog/support/mode integrity, corrects liquidity/multiscale semantics and unit-interval absorption domains, hardens dtype/availability/manifest/leak tests, and adds real PROXY plus 2.1B→2.1C→4.2B→5.2 integration.

Final-audit completion added real CLOSED 4.1 and 4.2A primary-surface integration, exact event-local/support verification, real 2.1B→2.1C→4.2B→5.2 integration, PROXY integration, manifest external-mutation isolation, and outside-range dealing geometry. V1.1 config now splits `order_blocks` and `fvg` explicitly; no auto-detection.

V1.2 makes missingness metadata executable (`ALLOW_MISSING`/`NONMISSING`), introduces explicit non-trading directional semantics, strengthens static catalog integrity, and corrects epistemic status for absorption/opposition/proxy evidence. Generic missingness enforcement now precedes domain validation. Added category/missingness, numerical boundary, true future append, real composed pipeline, and exact forbidden-output tests. The V1 and V1.1 patch history remains documented above.

V1.3 audit correction: a real no-op placeholder test remained despite the V1.2 report claiming its removal. It is now removed and replaced with exhaustive valid/invalid/missing tests for all four certified category domains. Every PROXY FeatureSpec now carries `SOURCE_APPROXIMATION`, including support metadata, while ACTUAL upstream qualification remains unchanged. The proxy manifest is asserted field-by-field and static catalog integrity enforces the proxy epistemic contract.
