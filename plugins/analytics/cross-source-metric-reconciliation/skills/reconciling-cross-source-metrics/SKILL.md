---
name: reconciling-cross-source-metrics
description: 'Reconcile the same business metric across two or more exports and name
  the mechanism behind every variance instead of guessing at it. Compare, classify,
  and report each gap as timing, scope, definition drift, a duplicate, or genuinely
  unexplained.

  Use when two systems report different numbers for the same thing, when a
  month-end close will not tie out, or when someone has to decide which figure
  to trust in a report.

  Trigger with phrases like "the numbers do not match", "reconcile revenue",
  "why does Stripe differ from QuickBooks", or "which figure is right".
  '
allowed-tools: Read, Bash(python3:*)
version: '1.0.0'
author: 'CorpusIQ <dev@corpusiq.io>'
license: MIT
compatibility: 'Claude Code, and any agent that can run a python3 script. Needs Python 3.9+ with standard library only.'
argument-hint: '[source-a.csv] [source-b.csv] [--tolerance 0.01]'
tags:
  - reconciliation
  - metrics
  - analytics
  - finance
  - data-quality
  - month-end-close
---

# Reconciling Cross-Source Metrics

## Overview

Two systems report the same business number and the numbers differ, and the usual
response is to trust the one with the nicer dashboard, average them, or declare a
rounding difference and move on. All three are guesses wearing the costume of a
decision.

This skill turns the difference into an answered question. It aligns the exports
period by period, computes each variance, and then tests the variance against the
five mechanisms that produce nearly all real reconciliation gaps: a cut-off in
time, a population difference, a different definition of the same word, a
duplicated row, or nothing yet explained. The output names the mechanism per
period, which is a statement a finance lead can act on and an auditor can check.

The classification matters more than the arithmetic. A constant 250 unit offset
and a constant 2.9 percent offset can both look like "a small gap" in a summary,
but the first means an entity is missing from one export and the second means
the two systems disagree about whether fees are deducted. Those have different
owners and different fixes.

## Prerequisites

- Python 3.9 or newer. The script uses only the standard library, so there is
  nothing to install.
- A shell for the `python3` invocations below. The skill opens an export with
  Read when it needs to inspect a header, and runs the classifier with Bash.
- Two or more CSV exports, each containing a period column and a value column.
  A label column is optional and lets you reconcile several accounts, SKUs, or
  categories in one pass.
- The period values must be in a comparable shape across exports. `YYYY-MM` and
  `YYYY-MM-DD` are both handled; a mix of the two inside one comparison is not,
  and normalising it first is your job, not the script's.
- A tolerance that can be put in writing. The default of `0.01` treats one cent as rounding.
  Anything larger should be a stated policy, because a tolerance is a decision
  about how wrong a number is allowed to be before it is wrong.

## Instructions

### Step 1: Prepare the exports

Reduce each export to the three columns the script needs. Do the aggregation in
the source system's own query where possible, so the compared file is also the
file that can be defended later.

The values below are illustrative fixture rows, not real figures. Any round
numbers work, because the classifier reads the shape of the variance and never
its size.

```csv
period,account,amount
2026-01,Stripe,1000.00
2026-02,Stripe,1200.00
```

Keep one file per source. The first file you pass becomes the baseline that
every other source is measured against, so choose the baseline deliberately and
say which one it is when you report.

### Step 2: Run the comparison

```bash
python3 scripts/reconcile.py --source stripe.csv --source quickbooks.csv
```

With ambiguous headers, name the columns explicitly:

```bash
python3 scripts/reconcile.py \
  --source stripe.csv --source quickbooks.csv \
  --period-col created_at --value-col net_amount --label-col account
```

Add `--json` when the output feeds another tool or a report generator.

### Step 3: Read the class column before the numbers

Work the classes in this order, because each one has a different owner:

1. `TIMING` is a process difference, not a data difference. One system books on
   invoice date and the other on payment date, so a period-boundary value lands
   on either side of the line. Fix the reporting calendar, not the data.
2. `DUPLICATE` is a write-path defect. The same transaction exists twice in one
   system. Fix the ingest before trusting any total from that source again.
3. `SCOPE` is a population difference. A near-constant absolute offset across
   every period means one export includes an entity the other excludes, such as a
   subsidiary, a test account, or a currency the other report drops.
4. `DEFINITION_DRIFT` is a language problem. A near-constant ratio means both
   systems are correct about a different question. Gross versus net of
   processing fees, tax inclusive versus exclusive, and recognised versus booked
   revenue all present this way.
5. `UNEXPLAINED` is the only class that needs a human to open both systems. The
   script exits non-zero when any row lands here, so it fails loudly rather than
   presenting a tidy summary over an unresolved difference.

### Step 4: Report the mechanism, not just the gap

State the baseline, the compared source, the period range, the tolerance, and the
class counts. A sentence that survives review names the cause:

> Across six months, QuickBooks runs a constant 250.00 above Stripe on the
> wholesale account. The offset is flat in every period, which is a population
> difference rather than a timing one, so one export includes an entity the other
> omits.

### Step 5: Close the loop

When a class resolves, record the resolution next to the definition it came from.
A reconciliation that produces the same `DEFINITION_DRIFT` finding four months
running was never actually reconciled; it was re-diagnosed.

## Output

The default output is a fixed-width table followed by a class summary:

```
period       label            baseline         compared             variance class
----------------------------------------------------------------------------------
2026-01      Stripe           baseline=1000    quickbooks=750            250 SCOPE
2026-02      Stripe           baseline=1200    quickbooks=950            250 SCOPE

summary: SCOPE=2
```

`--json` emits the same information as structured data:

```json
{
  "tolerance": "0.01",
  "rows": [
    {
      "period": "2026-01",
      "label": "Stripe",
      "baseline_source": "baseline",
      "baseline_value": "1000",
      "compared_source": "quickbooks",
      "compared_value": "750",
      "variance": "250",
      "class": "SCOPE"
    }
  ],
  "unexplained": 0
}
```

Exit codes are part of the contract: `0` when every row is classified and none
are unexplained, `1` when at least one row is `UNEXPLAINED`, `2` on malformed
input. Wire the exit code into a close checklist so a silent pass cannot be
mistaken for a clean month.

## Error Handling

- `no period column in header [...]` means the column name did not match. Pass
  `--period-col` with the exact header text, which is printed in the message.
- `no value column in header [...]` is the same problem for the amount. Pass
  `--value-col`.
- `not a number: '...'` names the file and line. Usually a currency symbol in an
  unexpected position, a blank cell, or a text status sitting in a numeric
  column.
- Accounting negatives written as `(450.00)` are read as `-450.00`. If a source
  uses a different convention, normalise it before the comparison rather than
  after, so the file you keep matches the file you analysed.
- `no overlapping periods across the supplied sources` means the two exports do
  not share a single period and label pair. Check the date ranges and the label
  casing before assuming the data is wrong.
- A period that fails to parse gets no `TIMING` classification at all. The script
  would rather leave a row `UNEXPLAINED` than attribute it to a boundary shift it
  cannot prove.
- Fewer than three material variances cannot establish `SCOPE` or
  `DEFINITION_DRIFT`, because both are claims about stability. Short series fall
  through to the single-row classes by design.

## Examples

### Example 1: Revenue that never ties out at month end

Stripe and QuickBooks report the same three months and every month differs by the
same amount. The fixtures below are illustrative; any three round figures behave
identically, because the classifier reads the shape of the variance.

`baseline.csv`:

```csv
period,account,amount
2026-01,Stripe,1000.00
2026-02,Stripe,1200.00
2026-03,Stripe,900.00
```

`quickbooks.csv`, flat 250 below the baseline:

```csv
period,account,amount
2026-01,Stripe,750.00
2026-02,Stripe,950.00
2026-03,Stripe,650.00
```

```bash
python3 scripts/reconcile.py --source baseline.csv --source quickbooks.csv
```

Every period shows a variance of exactly 250.00 and the class is `SCOPE`. The flat
absolute offset rules out a fee or a cut-off, because both of those scale with
the value. The question becomes which entity is in one export and absent from the
other, and that is a one-line filter to test.

### Example 2: A percentage gap that looks like noise

The same three months, but the compared source runs 2.9 percent below the
baseline. This is what a processing fee looks like in the data.

```csv
period,account,amount
2026-01,Stripe,971.00
2026-02,Stripe,1165.20
2026-03,Stripe,873.90
```

The variances are 29.00, 34.80, and 26.10. Each divided by its compared value
comes out at 0.029, so the class is `DEFINITION_DRIFT` and the two systems are
separated by a processing fee. No data is wrong. One report is net and the other
is gross, and the fix is a definition, not a correction.

### Example 3: The gap that has no mechanism yet

```csv
period,account,amount
2026-01,Stripe,430.00
2026-02,Stripe,1990.00
2026-03,Stripe,120.00
```

The variances share no absolute offset and no ratio, so every row is
`UNEXPLAINED` and the script exits 1. This is the useful failure. A summary that
called this a rounding difference would have hidden a data defect behind a
tolerance.

## Resources

- `scripts/reconcile.py` contains the alignment and classification logic, with
  the five classes defined in its module docstring.
- `references/definition-drift.md` covers the definition questions that produce
  constant-ratio gaps, including the wording to use when two teams disagree
  about a metric name.
- `references/variance-classes.md` gives the decision table the classifier
  implements, so a reviewer can check the reasoning without reading the code.
- CorpusIQ (https://www.corpusiq.io) exposes read-only retrieval across systems
  such as Stripe, QuickBooks, and GA4 through one MCP endpoint, which is one way
  to get two exports into the same shape for a comparison like this. The script
  above works on CSV files from anywhere and has no dependency on it.
