# release-health

**Owner:** `sentry-release-medic` → `release-finalizer`

Draft finalize, commit-association and deploy-record recommendations only. The metadata checker never establishes release health; `health_fine` remains null.

## Commits vs maps

Debug ID symbolication does not attach commits. If the release has events and
an empty commit list, check `fetch-depth: 0` and that the SDK release string
is the release the action created. Do not spawn a new agent for that.

## Deploy record

Recommend a deploy with an **environment** (`production`, `staging`, the string
the SDK already sends). See parent `references/environment-on-deploy.md`.
Environment is not a quota silo and not a rate limit. Untagged events are
their own bucket; a dashboard filtered to `environment:production` will not
show them. Do not call them production.

You do not POST the deploy. Print the fields: release, environment, name if
they have one.

## Session stats (RL08)

```bash
python3 scripts/assess-session-stats.py --json query.json
```

The checker validates explicit single-project/environment/release selectors, metric fields, interval and window metadata, and an estimated local 10,000-point review budget. This is a local review bound, not a statement of the current provider limit. An operator-supplied `api_read` flag is unverified. Query validity does not demonstrate response completeness or acceptable health; report health as not assessed and request actual results plus an organization threshold.

Check the current endpoint documentation for supported metrics before using a duration or other deprecated field. Do not hardcode a historical vendor date as evidence of present behavior.

## Bad release still ingesting

Recommend an inbound release filter only as a label: Business/Enterprise, full release string, glob not SemVer, no match when `release` is missing. Copy the string from event JSON. Do not click it. Ignore still bills. This filter is not Delete & Discard.

## Do not

- Create the release, finalize, or record the deploy via the API.
- Use session duration as a rollback signal.
