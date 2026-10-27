# Event/log correlation

1. Select a bounded source root and supplied event ID. Run the parent `scripts/find-event-id-log.py`.
2. Treat matches as lexical candidates: they may be comments, reads or unrelated identifiers. No source line is emitted and no logging write is proven.
3. Absence means no candidate in the completed selected search, not that the codebase never writes the ID. Keep inaccessible/truncated scope explicit.
4. Only an independently confirmed `--log-field` enables a query template. Verify the target logging backend, ingestion and field mapping before running it separately.
5. Return scope, candidate locations, unknowns and the next diagnostic. Do not install instrumentation, change files or execute a remote query.
