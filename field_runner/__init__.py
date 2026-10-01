"""BTC May 2026 LOCAL FIELD RUNNER — owner-authorized field tooling.

Lives OUTSIDE ``trading_project`` on purpose: the CLOSED project is consumed
exactly through its public APIs and is never modified by this package.
No engine, detector, or contract is re-implemented here; this package is
glue, input/output plumbing, fixture builders for runner tests, and reporting.

Runner status: IMPLEMENTED — PENDING OWNER RUN.
"""

FIELD_RUNNER_VERSION = "BTC_MAY2026_FIELD_RUNNER_V1"
FIELD_RUNNER_STATUS = "IMPLEMENTED_PENDING_OWNER_RUN"

# Contract constants consumed by reference (from the CLOSED adapter package).
TIE_ORDER_CONTRACT = "NOT_PROVEN"
EXECUTED_FLOW_LABEL = "EXECUTED_INITIATED_FLOW_FROM_BINANCE_SPOT"
