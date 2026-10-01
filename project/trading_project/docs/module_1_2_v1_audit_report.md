# Module 1.2 V1 — Causal Session Context Engine

Status: **CLOSED V1**

No historical implementation was reconstructed. Production calculation has no dependency on Modules 1.1, 0.2, or 0.3. Module 0.1 is imported only in self-verification/tests.

## Public API

```python
SessionDefinition(
    name: str,
    timezone: str,
    start_local: datetime.time,
    end_local: datetime.time,
)

CausalSessionContextEngine(sessions=...)
CausalSessionContextEngine.analyze(df) -> pd.DataFrame
```

There is no default session schedule.

## Output surface

Always:

- `hour_utc_sin`
- `hour_utc_cos`
- `weekday_sin`
- `weekday_cos`
- `active_session_count`

For every configured session:

- `session_<normalized_name>_active`

No raw integer hour, categorical exclusive session label, session score, progress, kill-zone score, or trading implication is produced.

## Design decisions

1. Input requires a timezone-aware, unique, monotonic `DatetimeIndex`; naive indexes, NaT, duplicates, and unsorted timestamps are rejected.
2. Session definitions use IANA `ZoneInfo` identities and immutable local wall-clock `datetime.time` boundaries.
3. Intervals are half-open `[start,end)`. `start>end` means crossing midnight. `start==end` is rejected; V1 does not define 24-hour sessions.
4. Sessions are multi-hot: overlaps remain simultaneously active and are summarized descriptively by `active_session_count`.
5. Session activity follows local wall-clock semantics under timezone-rule conversion. No fixed UTC offset or manual DST table is used.
6. Session progress is intentionally omitted because elapsed-duration semantics around DST ambiguous/nonexistent times require a separate contract.
7. UTC hour uses fractional hour (including minute/second/subsecond) on the 24-hour circle. UTC weekday uses the 7-day circle.
8. Session names must be explicit ASCII identifiers. Output keys are lowercase; normalization collisions are rejected rather than merged.
9. Pandas index `freq` is whole-index metadata that can change when only future timestamps become irregular. Output preserves labels/order/timezone/name but canonicalizes `freq=None` to prevent suffix-dependent metadata differences.
10. Engine state is immutable configuration only; every `analyze()` is deterministic and history-free.

## DST cases tested

- **London winter:** 2024-01-15 08:30 UTC = 08:30 GMT.
- **London summer:** 2024-07-15 07:30 UTC = 08:30 BST.
- **New York winter:** 2024-01-15 14:45 UTC = 09:45 EST.
- **New York summer:** 2024-07-15 13:45 UTC = 09:45 EDT.
- **US/UK mismatch:** 2024-03-20, after US DST begins (March 10) and before UK DST begins (March 31). The test contrasts March 6, March 20, and April 3 at the same UTC time.

## Results

Self-verification:

```text
MODULE 1.2 V1 SELF-VERIFICATION PASSED
Session context is timestamp-only, timezone-aware, and DST-rule based.
```

Module-specific suite:

```text
..........................                                               [100%]
```

26 tests passed.

Full suite:

```text
........................................................................ [ 72%]
...........................                                              [100%]
```

99 tests passed.

## Unresolved timezone/session semantics

1. **Nonexistent DST boundary:** a configured local boundary such as 02:30 during a spring-forward gap has no exact instant on that date. V1 activity is defined by each existing instant's converted local wall clock; it does not synthesize a missing boundary instant.
2. **Repeated fall-back clock times:** both occurrences map to the same local wall time and therefore share activity status. This is intentional wall-clock context, not elapsed-session-duration modeling.
3. **Timezone database versions:** historical/future results depend on the installed IANA tzdata rules. Reproducible deployments should pin/runtime-record tzdata versions.
4. **Session progress:** omitted rather than pretending wall-clock fraction equals elapsed-time fraction across DST transitions.
5. **Holiday/market calendars:** not modeled. Crypto remains 24/7; configured sessions are descriptive overlays only.
