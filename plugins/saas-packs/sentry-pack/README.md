# Sentry Skill Pack

Version 2 provides five self-contained offline operators. Supply selected configuration, event or usage exports and local source/build evidence. The helpers do not read credentials, call Sentry, change files or send messages.

## Installation

```bash
/plugin install sentry-pack@claude-code-plugins-plus
```

## Operators

| Skill | Job | Evidence limit |
|---|---|---|
| `sentry-quota-leak-hunter` | Compare observed usage categories and propose reductions | Missing counts remain unknown; no verified invoice |
| `sentry-event-forensics` | Investigate missing events and source-map resolution | Redaction is pattern based; no privacy certification |
| `sentry-release-medic` | Review local build IDs, upload plans and query metadata | Local markers do not prove deployment; health is not assessed |
| `sentry-issue-triage` | Classify supplied issue facts and investigate correlation | Missing severity inputs stay inconclusive; lexical hits are not log writes |
| `sentry-pii-scrub-enforcer` | Review scrubbing evidence, settings drift and requested erasure plans | Missing settings are incomplete; no runtime or compliance guarantee |

Each skill contains its own Python 3.10+ runtime under `scripts/lib/`; an installed skill needs no pack-level module or API token. Helpers use bounded inputs, reject malformed JSON and refuse write flags. Read the individual SKILL.md for commands and nonzero/incomplete results. Permission hints do not replace script validation or independent review.

`references/roles/` contains procedures to perform inline when relevant. These are not registered native agents and do not require spawning agents. Supporting historical checklists retain their paths under `agents/<role>/skills/`; they are reference data. The pack registers no hooks, MCP servers or native agents.

## Migration from v1

All 30 compatibility-only SKILL.md definitions and the legacy tutorial database are retired. Sixteen matching website aliases lead to the five operators; fourteen tutorials have no direct replacement and deliberately return 404. Saved native invocations must migrate explicitly. No redirect notice is counted as a callable skill.

See [the complete map](000-docs/phase0-kill-list.md) and [the decision record](000-docs/001-AT-ADEC-sentry-v2-rebuild-decisions.md). The legacy generators refuse to recreate Sentry tutorial scaffolds or overwrite this curated pack.

## Verification

Run `python3 scripts/sync-runtime.py --check` from this pack to check runtime parity. Repository regressions in `tests/test_sentry_pack_scripts.py` exercise actual isolated helper invocations, missing evidence, malformed counts, secret redaction and lexical false positives. Advisory `eval-spec.yaml` files describe behavioral cases; their presence does not mean a model evaluation ran or passed.

## License

MIT
