==============================================================
BTC MAY 2026 FIELD RUNNER - OWNER QUICK START (ASCII/English)
==============================================================

LATEST UPDATE (2026-09-29): this package includes the EXACT
PERFORMANCE V2 patches + faster test suite. Read
UPDATE_NOTES_2026-09-29.txt first. STATUS: PATCHED - PENDING_OWNER_RE_AUDIT.

STATUS: IMPLEMENTED - PENDING OWNER RUN

WHAT THIS IS
------------
A local field runner that executes the ALREADY CLOSED trading_project
engines through their public APIs on your BTCUSDT May 2026 data and writes
a field report under outputs/btc_may_2026_reality/.

No engine is re-implemented. No model. No strategy. No PnL. No signals.
TIE_ORDER_CONTRACT = NOT_PROVEN everywhere.

REQUIREMENTS
------------
- Python 3.10+ with pandas + numpy (same environment as trading_project).
- Windows: use run_btc_may_2026.bat (ASCII only; Arabic notes are in
  README_RESULT_AR.txt generated inside the output folder).

ONE COMMAND
-----------
1. Extract this package (keep folder layout).
2. Put your data files in .\data\ :
     - minute-facts CSV  (any name containing "minute", e.g.
       minute_facts_BTCUSDT-aggTrades-2026-05.csv is fine)
     - its sidecar JSON  (e.g. <same-stem>.sidecar.json)
     - raw aggTrades CSV is OPTIONAL (FAST mode): the raw identity is proven
       through the sidecar provenance chain (source_sha256 / converter_sha256)
3. Run:
       run_btc_may_2026.bat
   or:
       python run_btc_may_2026.py

FAST MODE (default) vs RAW MODE:
- FAST (default): raw aggTrades file NOT required. Accepted only if ALL hold:
  SHA256(minute-facts CSV) == sidecar.output_csv_sha256 == expected a6a06c4c...
  sidecar.source_sha256     == expected raw 86d4f3d3...
  sidecar.converter_sha256  == expected converter 0048779b...
- RAW (--mode raw): the raw aggTrades CSV MUST be present and its SHA256 is
  verified directly against 86d4f3d3...
- Artifact-role errors (never mislabeled): MINUTE_FACTS_HASH_MISMATCH,
  RAW_AGGTRADES_HASH_MISMATCH, SIDECAR_SOURCE_BINDING_MISMATCH,
  CONVERTER_BINDING_MISMATCH, SIDECAR_OUTPUT_BINDING_MISMATCH.
  A minute-facts file whose NAME contains "aggTrades" is NEVER treated as raw.

The runner will:
- verify input SHA256 identities (your owner-declared hashes; override with
  --allow-hash-mismatch only if YOU replaced the files);
- download the official Binance monthly klines
  (data.binance.vision, ZIP + .CHECKSUM, checksum verified before use)
  OR ask you for a local file when the network is unavailable:
      --klines-csv PATH   or   --klines-zip PATH --klines-checksum PATH
- load/validate everything through the CLOSED Binance Source Adapter V1
  (exact cross-witness, SOURCE_INCONSISTENCY fail-closed, canonical OHLC
  from published klines only);
- seal the timeline via its public API (consumer-side seal);
- run the CLOSED engines that are legally runnable;
- write the report folder.

OUTPUTS (outputs/btc_may_2026_reality/)
--------------------------------------
SUMMARY.json               counts + identities + branch statuses
DETECTION_AUDIT.csv        decision-side as-of sample (NO future facts)
OUTCOME_FILM_SAMPLE.csv    what happened later (SEPARATE file)
DETECTION_ENTITIES files   entities_*.csv (for charting later)
chart_overlay.csv          per-minute chart-ready overlay
README_RESULT_AR.txt       plain-Arabic explanation of the run
MACHINE_VALIDATION.json    hashes, contracts, runtime, warnings

SWING POLICY (IMPORTANT)
------------------------
The CLOSED swing detector requires an explicit confirmation quantile.
Nothing is invented: unless you set swing_quantile in
field_runner/config/field_run_config.json the swings branch is reported
NOT_CONFIGURED (and its dependent branches with it). If you choose a value
it is recorded as OWNER_SUPPLIED (not sacred) in the outputs.

Sessions schedule is the same idea: config file only; empty = NOT_CONFIGURED.

NOTHING HERE CLAIMS predictive edge, profitability, strategy, or PnL.
Detector output = operational project definition, not sole market truth.

Send back: SUMMARY.json + MACHINE_VALIDATION.json (+ any small files asked).
