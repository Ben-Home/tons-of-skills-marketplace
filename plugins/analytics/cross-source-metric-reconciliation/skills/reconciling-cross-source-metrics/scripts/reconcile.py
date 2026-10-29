#!/usr/bin/env python3
"""Reconcile the same business metric across two or more source exports.

Inputs are CSV files with a header containing a period column and a value
column. Each file is one source (Stripe, QuickBooks, Shopify, a warehouse
export). The script aligns the sources on (period, label), computes the
variance, and then names the mechanism that produces it:

  TIMING             this period's value equals the neighbouring period's
                     value in the other source, so the gap is a cut-off
                     difference, not a dispute about the number
  SCOPE              a near-constant ABSOLUTE offset across every period,
                     which points at an entity the other source excludes
  DEFINITION_DRIFT   a near-constant RATIO across every period, which
                     points at a different definition of the same number
                     (gross vs net of fees, tax inclusive vs exclusive)
  DUPLICATE          one source carries the same (period, label) twice and
                     the other carries it once
  UNEXPLAINED        none of the above holds, so a human has to look

Classification needs the whole series for a label, not one row, because
SCOPE and DEFINITION_DRIFT are statements about stability across periods.
A single row can only ever be TIMING, DUPLICATE or UNEXPLAINED.

Usage:
  python reconcile.py --source stripe.csv --source quickbooks.csv
  python reconcile.py --source a.csv --source b.csv --value-col amount \
      --period-col period --label-col account --json

Exits 0 when every period reconciles inside the tolerance, 1 when at least
one variance is unexplained, 2 on malformed input.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple

PERIOD_ALIASES = ("period", "date", "month", "week", "created_at", "posted_at")
VALUE_ALIASES = ("amount", "value", "total", "net", "net_amount", "gross", "revenue")
LABEL_ALIASES = ("label", "account", "category", "name", "sku", "status")

Key = Tuple[str, str]


def pick_column(header: List[str], requested: str | None,
                aliases: Tuple[str, ...], role: str) -> str:
    lowered = {h.strip().lower(): h for h in header}
    if requested:
        if requested.strip().lower() not in lowered:
            raise ValueError("%s column %r not in header %r" % (role, requested, header))
        return lowered[requested.strip().lower()]
    for alias in aliases:
        if alias in lowered:
            return lowered[alias]
    raise ValueError("no %s column in header %r; pass --%s-col" % (role, header, role))


def to_decimal(raw: str) -> Decimal:
    cleaned = raw.strip().replace(",", "").replace("$", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    if cleaned in ("", "-"):
        raise ValueError("empty amount")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("not a number: %r" % raw)


class Source:
    """One export: summed amounts per (period, label), plus raw row counts."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.totals: Dict[Key, Decimal] = defaultdict(Decimal)
        self.rows: Dict[Key, int] = defaultdict(int)

    def add(self, key: Key, amount: Decimal) -> None:
        self.totals[key] += amount
        self.rows[key] += 1


def load_source(path: Path, period_col: str | None, value_col: str | None,
                label_col: str | None) -> Source:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("%s has no header row" % path)
        pcol = pick_column(reader.fieldnames, period_col, PERIOD_ALIASES, "period")
        vcol = pick_column(reader.fieldnames, value_col, VALUE_ALIASES, "value")
        try:
            lcol: str | None = pick_column(reader.fieldnames, label_col, LABEL_ALIASES, "label")
        except ValueError:
            lcol = None

        source = Source(path.stem)
        for lineno, row in enumerate(reader, start=2):
            period = (row.get(pcol) or "").strip()
            if not period:
                continue
            label = ((row.get(lcol) or "") if lcol else "").strip()
            try:
                amount = to_decimal(row.get(vcol) or "")
            except ValueError as exc:
                raise ValueError("%s line %d: %s" % (path.name, lineno, exc))
            source.add((period, label), amount)
    return source


def shift_period(period: str) -> str | None:
    """One step later in the same calendar shape, or None when unparseable.

    None means TIMING cannot be claimed, which is the safe direction: a
    silent non-match is better than a wrong attribution.
    """
    text = period.strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        head = text[0:10]
        try:
            year, month, day = int(head[0:4]), int(head[5:7]), int(head[8:10])
        except ValueError:
            return None
        if day >= 28:
            return None
        return "%04d-%02d-%02d" % (year, month, day + 1) + text[10:]
    if len(text) == 7 and text[4] == "-":
        try:
            year, month = int(text[0:4]), int(text[5:7])
        except ValueError:
            return None
        month += 1
        if month > 12:
            return "%04d-01" % (year + 1)
        return "%04d-%02d" % (year, month)
    return None


def near_ratio(values: List[Decimal], tolerance: Decimal) -> bool:
    """True when every value is within 1 percentage point of the median."""
    if len(values) < 3:
        return False
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    if median == 0:
        return False
    spread = abs(ordered[-1] - ordered[0])
    return spread <= max(tolerance, abs(median) * Decimal("0.01"))


def near_absolute(values: List[Decimal], tolerance: Decimal) -> bool:
    """True when every value is within the tolerance of the median."""
    if len(values) < 3:
        return False
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    return abs(ordered[-1] - ordered[0]) <= max(tolerance, abs(median) * Decimal("0.01"))


def reconcile(sources: List[Source], tolerance: Decimal) -> List[Dict[str, object]]:
    baseline = sources[0]
    labels = sorted({label for key in baseline.totals for _, label in [key]})
    periods = sorted({period for period, _ in baseline.totals})
    rows: List[Dict[str, object]] = []

    for other in sources[1:]:
        for label in labels:
            series: List[Tuple[str, Decimal, Decimal]] = []
            for period in periods:
                mine = baseline.totals.get((period, label))
                theirs = other.totals.get((period, label))
                if mine is None or theirs is None:
                    continue
                series.append((period, mine, theirs))

            variances = [mine - theirs for _, mine, theirs in series]
            ratios: List[Decimal] = []
            for _, mine, theirs in series:
                if theirs != 0:
                    ratios.append((mine - theirs) / theirs)

            material = [v for v in variances if abs(v) > tolerance]
            drift = near_ratio(ratios, tolerance) if len(material) >= 3 else False
            scope = near_absolute(material, tolerance) if len(material) >= 3 else False

            for period, mine, theirs in series:
                variance = mine - theirs
                if abs(variance) <= tolerance:
                    kind = "MATCH"
                elif other.rows.get((period, label), 0) > 1:
                    kind = "DUPLICATE"
                elif drift:
                    kind = "DEFINITION_DRIFT"
                elif scope:
                    kind = "SCOPE"
                elif timing_match(baseline, other, period, label, tolerance):
                    kind = "TIMING"
                else:
                    kind = "UNEXPLAINED"

                rows.append({
                    "period": period,
                    "label": label,
                    "baseline_source": baseline.name,
                    "baseline_value": str(mine),
                    "compared_source": other.name,
                    "compared_value": str(theirs),
                    "variance": str(variance),
                    "class": kind,
                })
    return rows


def timing_match(baseline: Source, other: Source, period: str, label: str,
                 tolerance: Decimal) -> bool:
    """Compare across the period boundary in both directions."""
    forward = shift_period(period)
    candidates = []
    if forward is not None:
        candidates.append((baseline.totals.get((forward, label)),
                           other.totals.get((period, label))))
    backwards = [p for p in (shift_period(period),)
                 if p is not None]
    for step in backwards:
        previous = [k for k in baseline.totals
                    if k[1] == label and shift_period(k[0]) == period]
        for prev_key in previous:
            candidates.append((baseline.totals.get(prev_key),
                               other.totals.get((period, label))))
    for mine, theirs in candidates:
        if mine is None or theirs is None:
            continue
        if abs(mine - theirs) <= tolerance:
            return True
    return False


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", required=True,
                        help="CSV export path; repeat per source. The first is the "
                             "baseline the others are compared against.")
    parser.add_argument("--period-col")
    parser.add_argument("--value-col")
    parser.add_argument("--label-col")
    parser.add_argument("--tolerance", default="0.01",
                        help="absolute amount treated as rounding; default 0.01")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    if len(args.source) < 2:
        print("need at least two --source files to reconcile", file=sys.stderr)
        return 2

    try:
        tolerance = Decimal(args.tolerance)
    except InvalidOperation:
        print("--tolerance is not a number: %r" % args.tolerance, file=sys.stderr)
        return 2

    loaded: List[Source] = []
    for path_str in args.source:
        try:
            loaded.append(load_source(Path(path_str), args.period_col,
                                      args.value_col, args.label_col))
        except (OSError, ValueError) as exc:
            print("cannot read %s: %s" % (path_str, exc), file=sys.stderr)
            return 2

    rows = reconcile(loaded, tolerance)
    if not rows:
        print("no overlapping periods across the supplied sources", file=sys.stderr)
        return 2

    unexplained = [r for r in rows if r["class"] == "UNEXPLAINED"]

    if args.json:
        print(json.dumps({"tolerance": str(tolerance), "rows": rows,
                          "unexplained": len(unexplained)}, indent=2))
    else:
        header = "%-12s %-16s %-16s %-16s %12s %s" % (
            "period", "label", "baseline", "compared", "variance", "class")
        print(header)
        print("-" * (len(header) + 8))
        for row in rows:
            print("%-12s %-16s %-16s %-16s %12s %s" % (
                row["period"], str(row["label"])[:16],
                "%s=%s" % (str(row["baseline_source"])[:10], row["baseline_value"]),
                "%s=%s" % (str(row["compared_source"])[:10], row["compared_value"]),
                row["variance"], row["class"]))
        counts: Dict[str, int] = {}
        for row in rows:
            counts[str(row["class"])] = counts.get(str(row["class"]), 0) + 1
        print()
        print("summary: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())))

    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
