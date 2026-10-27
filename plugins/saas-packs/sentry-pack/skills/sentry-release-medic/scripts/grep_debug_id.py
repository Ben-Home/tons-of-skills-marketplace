#!/usr/bin/env python3
"""Inspect bounded local JS/source-map files for syntactically valid Debug IDs.

A matching word is not a Debug ID. Local marker presence does not establish
what was deployed, executed, or uploaded to a Sentry project.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import client_from_env, emit_json, parse_json, read_text, run_cli  # noqa: E402

UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
MARKER = re.compile(r"^[ \t]*//[#@][ \t]*debugId=(" + UUID + r")[ \t]*$", re.MULTILINE)
ID = re.compile(UUID)
JS = {".js", ".mjs", ".cjs", ".html", ".htm"}
SKIP = {".git", "node_modules", "coverage"}
MAX_FILES = 256
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
REFERENCE = "https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/debug-ids/"


def discover(roots: list[Path]) -> tuple[list[Path], list[dict]]:
    paths = set()
    errors = []
    visited = 0
    for root in roots:
        if root.is_symlink() or not root.exists():
            errors.append({"path": str(root), "reason": "missing path or symlink"})
            continue
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for directory, dirs, names in os.walk(
                root, followlinks=False, onerror=lambda _: errors.append({"reason": "unreadable directory"})
            ):
                visited += 1
                if visited > 2048:
                    errors.append({"reason": "directory budget exceeded"})
                    break
                for name in list(dirs):
                    child = Path(directory) / name
                    if name in SKIP:
                        dirs.remove(name)
                    elif child.is_symlink():
                        dirs.remove(name)
                        errors.append({"path": str(child), "reason": "symlink directory not inspected"})
                dirs.sort()
                for name in sorted(names):
                    path = Path(directory) / name
                    if path.suffix.lower() in JS | {".map"}:
                        candidates.append(path)
                if len(candidates) > MAX_FILES:
                    errors.append({"reason": "file budget exceeded"})
                    break
        for path in candidates:
            if path.suffix.lower() in JS | {".map"}:
                paths.add(Path(os.path.abspath(path)))
    if len(paths) > MAX_FILES:
        errors.append({"reason": "file budget exceeded"})
    return sorted(paths)[:MAX_FILES], errors


def scan(paths: list[Path], errors: list[dict]) -> dict:
    js_hits = []
    map_hits = []
    unmarked_js = []
    total = 0
    inspected = 0
    for path in paths:
        try:
            text = read_text(str(path), limit=MAX_FILE_BYTES)
            total += len(text.encode("utf-8"))
            if total > MAX_TOTAL_BYTES:
                errors.append({"reason": "total byte budget exceeded"})
                break
            inspected += 1
            if path.suffix.lower() in JS:
                ids = sorted({match.lower() for match in MARKER.findall(text)})
                if ids:
                    js_hits.append({"path": str(path), "debug_ids": ids})
                else:
                    unmarked_js.append(str(path))
            else:
                data = parse_json(text)
                if not isinstance(data, dict):
                    raise ValueError("source map must be an object")
                value = data.get("debug_id", data.get("debugId"))
                if value is not None:
                    if not isinstance(value, str) or ID.fullmatch(value) is None:
                        raise ValueError("invalid source-map Debug ID")
                    map_hits.append({"path": str(path), "debug_id": value.lower()})
        except (OSError, ValueError, UnicodeError):
            errors.append({"path": str(path), "reason": "unreadable, oversized or invalid artifact"})
    if not paths:
        errors.append({"reason": "no supported artifacts were supplied"})
    js_ids = {value for row in js_hits for value in row["debug_ids"]}
    map_ids = {row["debug_id"] for row in map_hits}
    return {
        "ok": not errors,
        "verdict": "INCOMPLETE"
        if errors
        else "MIXED"
        if js_hits and unmarked_js
        else "PRESENT"
        if js_hits
        else "ABSENT",
        "artifact_marker_observed": bool(js_hits),
        "js_files_without_marker": unmarked_js,
        "running_bytes_injected": None,
        "files_scanned": inspected,
        "js_debugId_hits": js_hits,
        "map_debug_id_hits": map_hits,
        "locally_matching_debug_ids": sorted(js_ids & map_ids),
        "errors": errors,
        "scope": "marker-shaped lines only (not a JS parser); deployment, runtime registration and server uploads were not verified",
        "map_only_does_not_count": bool(map_hits) and not js_hits,
        "reference": REFERENCE,
        "wrote": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="*")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        client_from_env().refuse_write("inject or upload source maps")
    paths, errors = discover([Path(value) for value in args.path])
    report = scan(paths, errors)
    emit_json(report)
    return 0 if report["verdict"] == "PRESENT" else 2


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
