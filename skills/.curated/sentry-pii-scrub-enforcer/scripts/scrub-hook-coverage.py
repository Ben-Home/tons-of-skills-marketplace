#!/usr/bin/env python3
"""Locate JS/TS SDK configuration markers in bounded offline source files.

This lexical search cannot prove hook registration, execution, effective PII
scrubbing, Replay enablement or an outage. Inspect the indicated call sites.
"""

import argparse
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import SentryReadOnlyError, client_from_env, emit_json, read_text, run_cli, source_files  # noqa: E402

HOOKS = (
    "beforeSendTransaction",
    "beforeSendSpan",
    "beforeSendLog",
    "beforeSendMetric",
    "beforeSend",
    "beforeBreadcrumb",
)
SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}


def scan_text(text: str) -> dict:
    hooks = {name: bool(re.search(r"(?<![A-Za-z0-9_])" + name + r"(?![A-Za-z0-9_])", text)) for name in HOOKS}
    values = sorted({match == "true" for match in re.findall(r"\bsendDefaultPii\s*:\s*(true|false)\b", text)})
    return {
        "hooks": hooks,
        "hook_markers": hooks,
        "sendDefaultPii_observed_literals": values,
        "sendDefaultPii": values[0] if len(values) == 1 else None,
        "sendDefaultPii_runtime_value": None,
        "replay_markers": bool(
            re.search(r"\breplayIntegration\b|\bsentryReplayIntegration\b|\bmaskAllText\b|sentry-unmask", text)
        ),
        "has_init_marker": bool(re.search(r"\bSentry\.init\s*\(", text)),
        "null_return_marker": bool(
            re.search(r"\bbeforeSend\s*:\s*(?:\(\)\s*=>\s*null|function\s*\([^)]*\)\s*\{\s*return\s+null)", text)
        ),
        "effective_hook_coverage": "not_verified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--pasted", help="Literal JS/TS source")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        client_from_env().refuse_write("SDK scrub patch")
    if bool(args.root) == (args.pasted is not None):
        raise SentryReadOnlyError("Provide exactly one source root or pasted source")
    files = []
    errors = []
    if args.pasted is not None:
        if not args.pasted or len(args.pasted.encode("utf-8")) > 1024 * 1024:
            raise SentryReadOnlyError("Pasted source must contain 1 byte to 1 MiB")
        files.append({"file": "<pasted>", **scan_text(args.pasted)})
    else:
        paths, errors = source_files(Path(args.root), SUFFIXES)
        total = 0
        for path in paths:
            try:
                text = read_text(str(path), limit=1024 * 1024)
                total += len(text.encode("utf-8"))
                if total > 32 * 1024 * 1024:
                    errors.append({"reason": "total byte budget exceeded"})
                    break
                row = scan_text(text)
                if row["has_init_marker"] or row["replay_markers"] or any(row["hooks"].values()):
                    files.append({"file": str(path), **row})
            except (OSError, ValueError):
                errors.append({"path": str(path), "reason": "unreadable, oversized or invalid source"})
    emit_json(
        {
            "assessment": "incomplete" if errors else "lexical_observations_only",
            "files": files,
            "errors": errors,
            "replay_on": None,
            "spawn_replay_privacy": False,
            "beforeSend_covers_replay": False,
            "null_beforeSend_is_outage": None,
            "scope": "JS/TS lexical candidates, including possible comments or strings; registration and behavior require inspection",
            "sdk_hook_support": "verify against the application's pinned SDK",
            "applied": False,
            "writes": "none",
        }
    )
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
