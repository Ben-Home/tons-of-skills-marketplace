# Session query metadata boundaries

`assess-session-stats.py` checks the supplied query shape, not a live API or a health response. It requires explicit single project, environment and release selectors, metric fields and bounded interval/window metadata. It uses an estimated local 10,000-point review budget. This is not a claim about the current vendor API limit.

`query_checks_pass` can be true while `health_fine` is null. `api_read` is an operator claim, not authenticated evidence. `--mark-fine` is refused. Request actual response values, completeness/pagination evidence, the evaluation window and an organization-defined acceptance threshold before a separate release-health judgment.

Verify supported fields and query semantics against the [current sessions API documentation](https://docs.sentry.io/api/releases/retrieve-release-health-session-statistics/) before proposing an API query. No live request is performed by this pack.
