# Variance classes

The classifier in `scripts/reconcile.py` tests each variance against five
mechanisms. This is the decision table it implements, in the order it applies
them, so a reviewer can check the reasoning without reading the code.

| Class | Test | What it means | Who owns the fix |
|---|---|---|---|
| `MATCH` | `abs(variance) <= tolerance` | No discrepancy to explain | Nobody |
| `DUPLICATE` | the compared source carries more than one row for the same period and label | A write-path defect: one transaction exists twice | Data engineering |
| `DEFINITION_DRIFT` | every material variance sits within one point of the median ratio | Both numbers are correct answers to different questions | Whoever owns the metric definition |
| `SCOPE` | every material variance sits within the tolerance of the median absolute offset, and at least three such rows exist | One export includes a population the other excludes | Whoever owns the reporting scope |
| `TIMING` | this period's baseline value equals the compared value of the adjacent period, in either direction | A cut-off difference, not a dispute about the amount | Whoever owns the reporting calendar |
| `UNEXPLAINED` | none of the above | Needs a human in both systems | Unassigned until investigated |

## Why the order matters

`DUPLICATE` is tested before the cross-period classes because a duplicated row
produces a variance that can coincidentally look stable. `DEFINITION_DRIFT` is
tested before `SCOPE` because a constant ratio and a constant offset both produce
a "stable gap" and the ratio is the more specific claim: fees and tax produce
proportional gaps, while entity exclusions produce flat ones.

`TIMING` is tested last among the explainable classes because it is the most
permissive test. A single matching neighbour is enough to fire it, so anything
more specific should get the chance to explain the gap first.

## Why three rows are required

`SCOPE` and `DEFINITION_DRIFT` are both claims about stability across periods. Two
points define a line, so two rows can always be described as "a stable ratio" and
that description would be meaningless. The script requires at least three material
variances before either class can fire. Shorter series fall through to the
single-row classes, which is the honest answer for a three-month-old company.

## Tolerance is a policy decision

The default tolerance of `0.01` treats one cent as rounding. Raising it is a
decision about how wrong a number may be before it is treated as wrong, so it
belongs in a written policy rather than in a command line flag someone typed
once. Two consequences worth stating up front:

- A tolerance larger than the smallest real transaction will hide a genuine
  missing row.
- A tolerance of zero will report floating-point residue as a defect in systems
  that store money as a float rather than a fixed-point decimal.
