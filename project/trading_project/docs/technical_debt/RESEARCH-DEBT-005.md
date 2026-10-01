# RESEARCH-DEBT-005 — VPIN Data/Clock Contract

**Owner:** Deferred order-flow research  
**Status:** OPEN — NOT IMPLEMENTED

A legitimate VPIN implementation requires an explicit contract for:

- volume-bucket construction;
- trade/bulk aggressor classification semantics;
- causal bucket closure;
- partial-bucket carry between updates;
- exact normalization-horizon methodology;
- validation against source trade data.

Arbitrary rows are not automatically VPIN buckets. A rolling absolute delta divided by volume must not be labeled VPIN.
