#!/usr/bin/env python3
"""Check offline release-health query metadata, without declaring a release healthy.

A user-supplied api_read flag is a claim, not an authenticated response. Scope
and datapoint-budget checks cannot establish crash-free rates or completeness.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import client_from_env, emit_json, read_text, run_cli  # noqa: E402

CAP = 10_000
PERIOD = re.compile(r"([1-9][0-9]*)([dhm])")


def _seconds(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = PERIOD.fullmatch(value)
    if match is None:
        return None
    return int(match[1]) * {"d": 86400, "h": 3600, "m": 60}[match[2]]


def _single(value: Any, *, numeric: bool = False) -> bool:
    if isinstance(value, list):
        return len(value) == 1 and _single(value[0], numeric=numeric) and not isinstance(value[0], list)
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return numeric and value > 0
    return isinstance(value, str) and bool(value.strip()) and value.strip() not in {"*", "-1"}


def assess(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload.get("query", payload)
    if not isinstance(query, dict):
        raise ValueError("query must be an object")
    reasons = []
    api_read = payload.get("api_read") is True
    if not api_read:
        reasons.append("The supplied metadata does not claim an API read")
    scoped = all(_single(query.get(key), numeric=key == "project") for key in ("project", "environment", "release"))
    if not scoped:
        reasons.append("Select exactly one project, one environment and one release")
    fields = query.get("fields", query.get("field"))
    if isinstance(fields, str):
        fields = [fields]
    valid_fields = isinstance(fields, list) and bool(fields) and all(isinstance(x, str) and x.strip() for x in fields)
    if not valid_fields:
        reasons.append("Explicit metric fields are required")
    duration = valid_fields and any("session.duration" in field for field in fields)
    if duration:
        reasons.append("This checker does not assess session.duration")
    group_by = query.get("groupBy", query.get("groupby", []))
    if isinstance(group_by, str):
        group_by = [group_by]
    if not isinstance(group_by, list) or not all(isinstance(x, str) and x.strip() for x in group_by):
        reasons.append("groupBy must contain strings")
    window = _seconds(query.get("statsPeriod", query.get("stats_period")))
    interval = _seconds(query.get("interval"))
    buckets = (window + interval - 1) // interval + 1 if window is not None and interval is not None else None
    if buckets is None:
        reasons.append("Explicit positive window and interval are required (d, h or m)")
    groups = payload.get("groups_returned")
    if type(groups) is not int or groups < 1:
        reasons.append("An observed positive group count is required")
        groups = None
    points = buckets * groups if buckets is not None and groups is not None else None
    if points is not None and points >= CAP:
        reasons.append("Estimated datapoints meet or exceed the local 10000-point review budget")
    if any(payload.get(key) is True for key in ("truncated", "partial", "has_more")):
        reasons.append("The supplied response is marked partial or truncated")
    return {
        "ok": not reasons,
        "mode": "advisory",
        "query_checks_pass": not reasons,
        "api_read_claimed": api_read,
        "api_read_verified": False,
        "scoped_to_project_environment_release": scoped,
        "estimated_buckets": buckets,
        "estimated_datapoints": points,
        "local_datapoint_budget": CAP,
        "response_completeness": "not_verified",
        "health_fine": None,
        "health_status": "not_assessed",
        "health_note": "Query metadata does not establish release health; inspect actual metrics against the operator's criteria",
        "reasons": reasons,
        "wrote": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", required=True, help="Offline metadata file, or '-' for stdin")
    parser.add_argument("--mark-fine", action="store_true", help="Refused: metadata cannot establish release health")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        client_from_env().refuse_write("record deploy or change release health")
    payload = client_from_env().fetch_project_settings("session-metadata", pasted=read_text(args.json))
    report = assess(payload)
    if args.mark_fine:
        report["reasons"].append("Refusing --mark-fine: no health verdict is produced by this checker")
        report["ok"] = False
    emit_json(report)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
