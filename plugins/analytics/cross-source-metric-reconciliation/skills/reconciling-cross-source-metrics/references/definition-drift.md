# Definition drift

`DEFINITION_DRIFT` is the class where no data is wrong. Two systems answer the
same question with different words, and the reconciliation is a conversation
about language rather than a correction of a number.

It presents as a near-constant ratio across every period. Once you see that
shape, the useful work is naming which definition each system uses.

## The pairs that produce it

**Gross versus net of processing fees.** The payment processor reports the
amount charged; the accounting ledger reports the amount received. The gap is
the fee rate and it scales with volume, which is exactly what a stable ratio
looks like. Neither system is wrong.

**Tax inclusive versus tax exclusive.** One system books the amount the customer
paid, the other books the amount the business earned. The ratio is the tax rate.

**Booked versus recognised.** A subscription billed annually appears in full on
the invoice date in one system, and in twelve monthly slices in the other. Over
a full year the totals agree and every individual month differs. This one can
look like `TIMING` on a single period and only shows its real shape when a
quarter or more is in view.

**Refund treatment.** Returns deducted at source in one system and booked as a
separate line in the other. Totals match; the period distribution does not.

**Currency handling.** One export converts to the reporting currency at the
transaction date, the other at month end. A stable monthly deviation appears
whenever the rate moved in the same direction across periods.

## The wording that ends the argument

Most definition disagreements are not disagreements at all. Two people are each
correct about a different number, and neither has said which one they mean. The
sentence that resolves it names both:

> When we say revenue in this report, we mean gross amount charged, inclusive of
> tax, before processing fees, converted at the transaction date. If a reader
> expects net of fees, this report is not the one they want.

Write that sentence into the metric definition, not into the reconciliation
note. A note explains one month. A definition prevents the same finding next
month, which is the difference between reconciling and re-diagnosing.

## When it is not drift

If the ratio moves by more than a point across periods, the two systems are not
just using different definitions. Something else is happening, and the row should
be `UNEXPLAINED` until someone can say what. A constant ratio is evidence of a
definition difference precisely because it is stable. Instability is evidence
that the explanation is incomplete.

## A test that settles it quickly

Take one period, divide the variance by the compared value, and check whether the
result matches a rate you already know: a payment fee percentage, a tax rate, a
currency spread. When the number matches a rate that appears in a contract, the
finding is confirmed without opening either system.
