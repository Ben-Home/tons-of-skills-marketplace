#!/usr/bin/env python3
"""Find lexical event-ID references in a bounded local source scope.

Matches may be comments, reads or dead code. They do not prove a logging write.
A query template requires an operator-supplied log field and event identifier.
"""

import argparse
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import SentryReadOnlyError, emit_json, read_text, run_cli, source_files  # noqa: E402

SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".rb", ".go", ".java", ".kt"}
NEEDLE = re.compile(r"(?<![A-Za-z0-9_])(?:event_id|eventId|last_event_id|lastEventId)(?![A-Za-z0-9_])")


def main() -> int:
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--event-id", default="")
    parser.add_argument("--log-field", help="Field independently confirmed by the operator")
    args = parser.parse_args()
    event = args.event_id.strip()
    if event and re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", event) is None:
        raise SentryReadOnlyError("An event identifier must be 32 hex digits or a UUID")
    if args.log_field and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,127}", args.log_field) is None:
        raise SentryReadOnlyError("Unsupported log-field syntax")
    paths, errors = source_files(Path(args.root), SUFFIXES)
    hits = []
    total = 0
    for path in paths:
        try:
            text = read_text(str(path), limit=1024 * 1024)
            total += len(text.encode("utf-8"))
            if total > 32 * 1024 * 1024:
                errors.append({"reason": "total byte budget exceeded"})
                break
            for number, line in enumerate(text.splitlines(), 1):
                if NEEDLE.search(line):
                    hits.append({"file": str(path), "line": number, "kind": "lexical_candidate"})
                    if len(hits) >= 200:
                        errors.append({"reason": "result budget reached"})
                        break
            if len(hits) >= 200:
                break
        except (OSError, ValueError):
            errors.append({"path": str(path), "reason": "unreadable, oversized or invalid source"})
    template = f"{args.log_field}:{json.dumps(event)}" if event and args.log_field else None
    emit_json(
        {
            "assessment": "incomplete" if errors else "bounded_lexical_search",
            "verdict": "candidates_require_inspection" if hits else "no_candidates_in_selected_scope",
            "event_id": event or None,
            "query_template": template,
            "query": None,
            "query_note": "Operator-supplied field; confirm backend syntax and actual ingestion before use",
            "logging_write_proven": False,
            "hits": hits,
            "errors": errors,
            "scope": "selected source suffixes only; generated/dependency trees excluded; no absence proof",
            "datadog_install": False,
            "writes": "none",
        }
    )
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
