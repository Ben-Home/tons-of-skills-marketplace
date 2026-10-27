#!/usr/bin/env python3
"""Print an offline, unapproved erasure review plan; never send a request.

An issue deletion is asynchronously queued and affects the entire issue. It is
not evidence of completed subject-wide erasure across every Sentry data surface.
"""

import argparse
import json
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import SentryReadOnlyError, client_from_env, emit_json, run_cli  # noqa: E402

REFERENCE = "https://docs.sentry.io/api/events/remove-an-issue/"


def build_plan(org: str, user_id: str, project: str | None, issue_ids: list[str]) -> dict:
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", org) is None:
        raise SentryReadOnlyError("Provide an explicit organization slug or ID")
    if project is not None and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", project) is None:
        raise SentryReadOnlyError("Unsupported project identifier")
    if not user_id or len(user_id) > 256 or any(ord(x) < 32 for x in user_id) or "sntrys_" in user_id:
        raise SentryReadOnlyError("Provide a bounded subject identifier, never a credential")
    if any(re.fullmatch(r"[1-9][0-9]{0,31}", value) is None for value in issue_ids) or len(issue_ids) != len(
        set(issue_ids)
    ):
        raise SentryReadOnlyError("Issue identifiers must be distinct positive integer strings")
    requests = [
        {
            "method": "DELETE",
            "url": f"https://sentry.io/api/0/organizations/{org}/issues/{value}/",
            "issue_id": value,
            "required_scope": "event:admin",
            "sent": False,
            "approval": "not_requested_or_granted_by_this_command",
            "subject_membership_verified": False,
            "project_membership_verified": False,
            "other_subjects_reviewed": False,
            "effect": "Queues deletion of the entire issue, including events belonging to other subjects",
            "completion": "not_verified; an accepted request alone is not a completion receipt",
        }
        for value in issue_ids
    ]
    return {
        "mode": "print-only",
        "org": org,
        "project": project,
        "subject_identifier_supplied": user_id,
        "search_hint": f"user.id:{json.dumps(user_id)} OR user.email:{json.dumps(user_id)}",
        "search_note": "Operator-supplied identifier; verify matching and query semantics before selecting data",
        "issue_deletes_not_sent": requests,
        "issue_ids_omitted": not issue_ids,
        "coverage": {
            surface: "not_verified"
            for surface in [
                "issues_and_events",
                "spans_and_transactions",
                "logs",
                "profiles",
                "replays",
                "feedback",
                "attachments_and_exports",
            ]
        },
        "per_subject_erasure_endpoint": "not_selected_or_assumed",
        "retention": "Inspect the organization's actual retention and asynchronous deletion status for each surface",
        "erasure_completed": False,
        "auto_delete": False,
        "applied": False,
        "writes": "none",
        "reference": REFERENCE,
        "next_step": "Verify authorization, subject/project scope, co-affected data and current provider behavior before any separate execution",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--project")
    parser.add_argument("--issue-id", action="append", default=[])
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    if args.send:
        client_from_env().refuse_write("send erasure request")
    emit_json(build_plan(args.org.strip(), args.user_id.strip(), args.project, args.issue_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
