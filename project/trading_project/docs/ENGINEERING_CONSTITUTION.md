# Engineering Constitution — External Source Verification

Before adding or materially changing a domain concept, algorithm, library-time
contract, or named methodology, research the open web and verify it against the
most authoritative available sources.

Priority:
1. original/primary specification or author;
2. official library/exchange/vendor documentation;
3. peer-reviewed research or recognized standards;
4. independent secondary sources only for cross-checking.

Named trading concepts (for example ICT terminology) must be checked against
primary creator material where available and must remain operational labels,
not unverified market truth. Sources and any disagreement/ambiguity must be
recorded in the module audit report. Internet research does not override the
project’s causal, no-magic, and empirical-audit requirements.

Module 5.2’s backward exact as-of contract was cross-checked against official
pandas `merge_asof` documentation: backward selection chooses the last key less
than or equal to the decision key, exact matches may be allowed, and keys must
be sorted:
https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.merge_asof.html

Absolute elapsed-time/DST behavior was cross-checked against the official
pandas time-series guide:
https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html
