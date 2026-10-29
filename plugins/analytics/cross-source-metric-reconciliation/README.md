# Cross-Source Metric Reconciliation

A skill for the moment two systems report different numbers for the same thing
and someone has to decide which one to believe.

## The problem

Stripe says 1000. QuickBooks says 750. The gap gets called a rounding difference,
or the figure from the nicer dashboard wins, or the two are averaged and everyone
moves on. Each of those is a guess presented as a decision, and the same finding
comes back next month because nothing was actually explained.

## What this does

It aligns two or more exports period by period, computes every variance, and then
tests the variance against the five mechanisms that produce nearly all real gaps:

| Class | Shape | What it means |
|---|---|---|
| `TIMING` | this period's number equals the neighbour period's in the other source | a cut-off difference, not a dispute |
| `SCOPE` | a near-constant absolute offset | one export includes a population the other excludes |
| `DEFINITION_DRIFT` | a near-constant ratio | fees, tax, or gross versus net |
| `DUPLICATE` | the same period and label twice in one source | a write-path defect |
| `UNEXPLAINED` | none of the above | a human has to open both systems |

Naming the mechanism is the point. A flat 250 offset and a flat 2.9 percent offset
both read as "a small gap" in a summary, but the first is a missing entity and the
second is a disagreement about whether fees are deducted. Different owners,
different fixes.

## Install

```
/plugin marketplace add jeremylongshore/tons-of-skills-marketplace
/plugin install cross-source-metric-reconciliation@claude-code-plugins-plus
```

## Use

```bash
python3 scripts/reconcile.py --source stripe.csv --source quickbooks.csv
```

```csv
period,account,amount
2026-01,Stripe,1000.00
2026-02,Stripe,1200.00
```

With headers that do not match the defaults:

```bash
python3 scripts/reconcile.py \
  --source stripe.csv --source quickbooks.csv \
  --period-col created_at --value-col net_amount --label-col account
```

Exit codes carry meaning: `0` all rows classified, `1` at least one
`UNEXPLAINED`, `2` malformed input. Wire it into a close checklist so a silent
pass cannot be read as a clean month.

## Requirements

Python 3.9 or newer. Standard library only, nothing to install.

## Layout

```
plugins/analytics/cross-source-metric-reconciliation/
  .claude-plugin/plugin.json
  skills/reconciling-cross-source-metrics/
    SKILL.md
    scripts/reconcile.py
    references/variance-classes.md
    references/definition-drift.md
  README.md
  LICENSE
```

## Verified behaviour

The classifier was exercised against one fixture per class before submission:
a shifted series for `TIMING`, a flat 250 offset for `SCOPE`, a 2.9 percent fee
for `DEFINITION_DRIFT`, a double-posted row for `DUPLICATE`, uncorrelated noise
for `UNEXPLAINED`, plus a malformed header for the exit-2 path. The fixture for
`TIMING` correctly leaves the first period `UNEXPLAINED`, because that period has
no predecessor to shift from.

## License

MIT
