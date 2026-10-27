#!/usr/bin/env python3
"""Compare offline project settings with an explicit, typed local standard.

Missing settings are incomplete evidence, not clean projects. This compares
exported declarations; it does not prove SDK execution or server enforcement.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import SentryReadOnlyError, client_from_env, emit_json, load_json, run_cli  # noqa: E402

BOOL_KEYS = {
    "sendDefaultPii",
    "dataScrubber",
    "scrubIPAddresses",
    "maskAllText",
    "blockAllMedia",
    "networkCaptureBodies",
}
LIST_KEYS = {"sensitiveFields", "scrubFields", "networkDetailAllowUrls"}
SAMPLE_KEYS = {"tracesSampleRate", "profilesSampleRate", "sampleRate", "replaysSessionSampleRate"}
SUPPORTED = BOOL_KEYS | LIST_KEYS | SAMPLE_KEYS | {"tracesSampler"}


def _valid(key: str, value: Any, *, standard: bool = False) -> bool:
    if key in BOOL_KEYS:
        return type(value) is bool
    if key in LIST_KEYS:
        return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)
    if key in SAMPLE_KEYS:
        return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
    if standard:
        return isinstance(value, str) and value in {"present", "absent"}
    return value is None or type(value) is bool or isinstance(value, str)


def _presence(value: Any) -> str:
    return "absent" if value is None or value is False or value == "" or value == "absent" else "present"


def _projects(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and "projects" in payload:
        rows = payload["projects"]
    elif isinstance(payload, dict):
        rows = [payload]
    else:
        raise SentryReadOnlyError("Projects must be a list or project object")
    if not isinstance(rows, list) or not rows:
        raise SentryReadOnlyError("At least one observed project is required")
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SentryReadOnlyError("Each project must be an object")
        slug = row.get("slug", row.get("project", row.get("name")))
        if not isinstance(slug, str) or not slug.strip() or slug in seen:
            raise SentryReadOnlyError("Projects require distinct nonempty identifiers")
        settings = row.get("settings", {k: v for k, v in row.items() if k not in {"slug", "project", "name"}})
        if not isinstance(settings, dict):
            raise SentryReadOnlyError("Project settings must be an object")
        seen.add(slug)
        result.append({"slug": slug, "settings": settings})
    return result


def compare(payload: Any, standard: Any) -> dict[str, Any]:
    if not isinstance(standard, dict):
        raise SentryReadOnlyError("The written standard must be an object")
    standard = standard.get("settings", standard)
    if not isinstance(standard, dict) or not standard:
        raise SentryReadOnlyError("A nonempty written standard is required")
    if set(standard) - SUPPORTED or any(not _valid(k, v, standard=True) for k, v in standard.items()):
        raise SentryReadOnlyError("The standard contains unsupported keys or invalid policy types")
    rows = _projects(payload)
    findings = []
    dirty = set()
    incomplete = set()
    for row in rows:
        slug, settings = row["slug"], row["settings"]
        for key, wanted in sorted(standard.items()):
            if key not in settings or not _valid(key, settings.get(key)):
                incomplete.add(slug)
                findings.append(
                    {"project": slug, "key": key, "kind": "incomplete", "reason": "missing or invalid observed setting"}
                )
                continue
            found = settings[key]
            if key in {"sensitiveFields", "scrubFields"}:
                matches = set(wanted).issubset(set(found))
            elif key == "tracesSampler":
                matches = _presence(found) == wanted
            else:
                matches = found == wanted
            if not matches:
                dirty.add(slug)
                findings.append(
                    {
                        "project": slug,
                        "key": key,
                        "kind": "drift",
                        "found": _presence(found) if key == "tracesSampler" else found,
                        "expected": wanted,
                    }
                )
    return {
        "mode": "advisory",
        "assessment": "incomplete" if incomplete else "complete",
        "dirty_projects": sorted(dirty),
        "incomplete_projects": sorted(incomplete),
        "clean_projects": sorted(row["slug"] for row in rows if row["slug"] not in dirty | incomplete),
        "findings": findings,
        "compared_standard_keys": sorted(standard),
        "scope": "provided declarations only; runtime enforcement and other projects were not inspected",
        "sampling_order_restated": False,
        "applied": False,
        "writes": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", help="Offline JSON file, literal JSON, or '-' for stdin")
    parser.add_argument("--standard", help="Explicit written standard file or literal JSON")
    parser.add_argument("--project", help="Unsupported live selector; provide an offline export")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        client_from_env().refuse_write("project scrub settings update")
    if not args.projects or not args.standard or (args.projects == "-" and args.standard == "-"):
        raise SentryReadOnlyError("Provide projects and a written standard; at most one may read stdin")
    report = compare(load_json(args.projects), load_json(args.standard))
    emit_json(report)
    return 2 if report["dirty_projects"] or report["incomplete_projects"] else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
