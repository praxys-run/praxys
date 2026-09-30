# Activity-detail streaming baseline

`baseline.json` stores SHA-256 hashes of complete response dictionaries from
the **pre-streaming** module `/tmp/activity_detail_before_streaming.py`, whose
SHA-256 is `375bfb9c794844c5b0db249d113130f3da41a5c446fc867b8477a118ffcfc246`.
Engineering captured them on 2026-09-29 using `/usr/bin/python3`, isolated SQLite
and the synthetic `analysis_client` fixture. They were not derived from the new
implementation. The temporary original module is retained locally for independent
Quality; it is neither a committed duplicate nor a test dependency.

For each `(count, variant)` in `tests/test_activity_detail_streaming.py::SCENARIOS`,
`seed_stream_case` populated a fresh fixture. The capture called
`baseline.get_activity_detail(owner_id, db, "stream-regression")` and separately
called the current function on the same database, asserting full dictionary
equality. Only the baseline response was passed to `response_digest`: JSON with
recursively sorted keys, compact separators, `allow_nan=False`, UTF-8, and no
trailing newline, then SHA-256. Expected digests must not be regenerated from a
failing current implementation.

Cases cover 0/1/5,999/6,000/6,001/12,013 rows; earliest tied extrema; field and
time gaps across the 512-row fetch boundary; invalid numeric ranges; source
provenance; unverified starts; incomplete/non-monotonic distance; and tiny-tail
merging. Tests also assert the owner predicate, single window-count statement,
streaming execution options, and explicit kilometer rejection precedence.

The adjacent native fixture README and its 26-file evidence manifest remain
unchanged. These are executor regression checks, not independent verification.
