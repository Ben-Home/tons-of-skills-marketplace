# Sentry v2 operational rebuild decision

Status: proposed in PR #1599; integration review updated 2026-10-26. This record describes the candidate implementation, not a claim that the PR is merged or deployed.

## Scope and value

Retain five distinct operator jobs: usage comparison, event forensics, release evidence, issue triage and PII/settings review. Retire all thirty compatibility-only definitions and the thirty-row legacy tutorial database. Sixteen former jobs have real operator destinations; fourteen have no direct replacement. The migration map records every disposition.

## Runtime and discovery

Each skill installs its own bounded standard-library parser runtime. The canonical developer copy is `scripts/lib/sentry_readonly.py`; `scripts/sync-runtime.py` reproduces the five local copies and checks parity. No token is loaded, no live transport is implemented and write flags are refused.

The previous nested agent definitions were not registered by the plugin manifest. They are now twenty-one conditional inline reference procedures. Historical CHECKLIST.md resources retain their paths as data; they are not standalone skills or native agents. See the [official plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference) for registration semantics.

## Evidence boundaries

Missing counts/settings are unknown or incomplete, never silently zero or clean. A pasted api_read flag does not authenticate a response; query-shape checks leave release health unassessed. Local lexical markers cannot prove deployed injection, actual logging writes or complete runtime scrubbing. Redaction is bounded pattern matching. Erasure plans do not verify identity, authorization, complete surface coverage or deletion completion.

## Migration and verification

Website aliases are canonical routing data, not callable redirect skills. Legacy generation entrypoints refuse Sentry before writing scaffolds. Focused CLI regressions cover isolated installation and substantive false-pass failures. Advisory behavioral specs are unexecuted unless accompanied by actual run evidence. Native schema scores measure their stated rubric and do not certify privacy, correctness or security. Generated score/catalog artifacts must come from the canonical writers and an actual source-specific native run.
