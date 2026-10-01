# RESEARCH-DEBT-022 — Entity-Level Narrative Provenance Contract

Module 6.1A primary aggregates do not carry immutable level/zone/FVG IDs across
rows. V1 therefore keeps liquidity and zone observations event-scoped and does
not fabricate entity stories. Persistent entity narratives require a separate
audited input contract over CLOSED normalized lifecycle tables, stable IDs,
causal availability, and exact truncation/state isolation.
