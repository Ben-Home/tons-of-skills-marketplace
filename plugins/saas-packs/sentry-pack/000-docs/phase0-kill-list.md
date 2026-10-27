# sentry-pack v1 → v2 migration map

**Status:** reconstructed 2026-10-04 from the dispositions recorded in the 30 v1 redirect stubs and
the pack README in PR #1599. The original working notes for this rebuild were produced in an
external sandbox and were never committed, so this file records the outcome, not the original
deliberation.

## 1. Scope

sentry-pack 1.x shipped 30 tutorial skills. sentry-pack 2.0.0 ships five operational skills and
removes all 30 compatibility-only definitions. Sixteen website aliases point to the matching operator; the fourteen Cut routes deliberately return 404. Saved native invocations must migrate explicitly.

## 2. Totals

Keep 5 · Merge 11 · Cut 14 (30 v1 skills).

- **Keep:** the v1 job continues as the core of a v2 skill.
- **Merge:** the v1 job folds into a v2 skill's inline procedures, checklists or references.
- **Cut:** no v2 equivalent; the stub explains why.

## 3. Migration map

| v1 skill | Disposition | v2 skill | Reason |
|---|---|---|---|
| `sentry-advanced-troubleshooting` | Keep | `sentry-event-forensics` | Missing or wrong event diagnosis is the core of the forensics job. |
| `sentry-cost-tuning` | Keep | `sentry-quota-leak-hunter` | Cost and quota tuning is the core of the quota job. |
| `sentry-data-handling` | Keep | `sentry-pii-scrub-enforcer` | PII handling is the core of the scrub-enforcer job. |
| `sentry-incident-runbook` | Keep | `sentry-issue-triage` | Incident triage is the core of the triage job. |
| `sentry-release-management` | Keep | `sentry-release-medic` | Release and sourcemap repair is the core of the release job. |
| `sentry-ci-integration` | Merge | `sentry-release-medic` | CI sourcemap upload folds into release-medic procedures. |
| `sentry-debug-bundle` | Merge | `sentry-event-forensics` | Support-bundle collection and redaction fold into forensics procedures. |
| `sentry-deploy-integration` | Merge | `sentry-release-medic` | Deploy markers and release finalization fold into release-medic procedures. |
| `sentry-load-scale` | Merge | `sentry-quota-leak-hunter` | Volume and scale concerns fold into the quota procedures and checklists. |
| `sentry-migration-deep-dive` | Merge | `sentry-event-forensics` | Migration breakage is diagnosed by forensics procedures. |
| `sentry-observability` | Merge | `sentry-issue-triage` | Log correlation folds into the triage log-correlator procedure. |
| `sentry-performance-tuning` | Merge | `sentry-quota-leak-hunter` | Sampling and transaction-volume tuning fold into the quota procedures and checklists. |
| `sentry-policy-guardrails` | Merge | `sentry-pii-scrub-enforcer` | Project-standard drift checks fold into scrub-enforcer procedures. |
| `sentry-rate-limits` | Merge | `sentry-quota-leak-hunter` | Rate-limit and spike handling folds into the quota procedures and checklists. |
| `sentry-security-basics` | Merge | `sentry-pii-scrub-enforcer` | Token and data-security checks fold into scrub-enforcer procedures. |
| `sentry-upgrade-migration` | Merge | `sentry-event-forensics` | SDK upgrade regressions are diagnosed by forensics procedures. |
| `sentry-architecture-variants` | Cut | — | Architecture picker. Out of scope for v2. |
| `sentry-common-errors` | Cut | — | The error catalog splits into forensics, quota and release references; it is not a skill. |
| `sentry-enterprise-rbac` | Cut | — | Token hygiene moves to PII references; the SSO/SCIM click-path is dropped. |
| `sentry-error-capture` | Cut | — | Onboarding cookbook. Not rebuilt. |
| `sentry-hello-world` | Cut | — | Onboarding hello-world. Not rebuilt. |
| `sentry-install-auth` | Cut | — | DSN and token setup folds into each v2 skill's Prerequisites. |
| `sentry-known-pitfalls` | Cut | — | Anti-patterns become a checklist reference on event-forensics (also cited by quota and PII). |
| `sentry-local-dev-loop` | Cut | — | Dev DSN and Spotlight setup are dropped; debug-mode steps live in event-forensics. |
| `sentry-multi-env-setup` | Cut | — | Per-environment sample rates move to quota references; environment-on-deploy moves to release-medic references. |
| `sentry-performance-tracing` | Cut | — | Install-shaped tracing setup is dropped; trace-gap diagnosis stays in event-forensics. |
| `sentry-prod-checklist` | Cut | — | The go-live list scatters into release and PII prerequisites. |
| `sentry-reference-architecture` | Cut | — | Pure reference. Out of scope for v2. |
| `sentry-reliability-patterns` | Cut | — | Design patterns, not a user task. Out of scope for v2. |
| `sentry-sdk-patterns` | Cut | — | Cookbook. Fingerprint and scope field names may appear in issue-triage references. |

## 4. Retirement decision

The review removes all thirty compatibility-only SKILL.md definitions in the v2 change. A redirect notice is migration metadata, not a useful callable skill. The 16 Keep/Merge jobs receive canonical website aliases; the 14 Cut jobs have explicit 404 decisions. The legacy 30-row database and its generated scaffolds are retired, with regeneration guards. Git history retains the old bodies.

Five self-contained offline operators remain. The former nested agent definitions are inline reference procedures, without native-agent discovery promises. No automated evaluation or schema grade is a privacy/security certification.
