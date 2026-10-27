#!/usr/bin/env python3
"""Redact recognized credential shapes from an offline support-bundle draft.

This is not a general PII certification. Review the remaining content before
sharing it. The command neither writes a file nor sends the bundle anywhere.
"""

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import client_from_env, emit_json, read_text, redact_with_counts, run_cli  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default="-", help="Offline text file, or '-' for stdin (8 MiB limit)")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        client_from_env().refuse_write("upload support bundle")
    cleaned, counts = redact_with_counts(read_text(args.json))
    emit_json(
        {
            "ok": True,
            "wrote": False,
            "redactions": counts,
            "contains_sntrys": False,
            "text": cleaned,
            "scope": "recognized credential patterns only; remaining content needs review",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
