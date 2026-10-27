#!/usr/bin/env python3
"""Extract severity inputs from a Sentry issue or event JSON.

Reads pasted JSON or, when implemented, the shared read-only client.
Does not invent timestamps, releases, or counts. Does not write.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "lib"
if not (_LIB / "sentry_readonly.py").is_file():
    raise SystemExit("Missing bundled offline runtime")
sys.path.insert(0, str(_LIB))
from sentry_readonly import SentryReadOnlyClient, SentryReadOnlyError, client_from_env  # noqa: E402
from sentry_readonly import emit_json, read_text, run_cli  # noqa: E402


def _int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise SentryReadOnlyError("Issue counts must be nonnegative integers")
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    if isinstance(value, int) and value >= 0:
        return value
    raise SentryReadOnlyError("Issue counts must be nonnegative integers")


def _tag(data: dict[str, Any], key: str) -> str | None:
    tags = data.get("tags")
    if isinstance(tags, dict):
        val = tags.get(key)
        return str(val) if val else None
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict) and item.get("key") == key and item.get("value"):
                return str(item["value"])
            if isinstance(item, (list, tuple)) and len(item) == 2 and item[0] == key and item[1]:
                return str(item[1])
    return None


def _release(data: dict[str, Any]) -> str | None:
    for candidate in (
        data.get("release"),
        (data.get("release") or {}).get("version") if isinstance(data.get("release"), dict) else None,
        _tag(data, "release"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _environment(data: dict[str, Any]) -> str | None:
    env = data.get("environment") or _tag(data, "environment")
    if isinstance(env, str) and env.strip():
        return env.strip()
    return None


def severity(data: dict[str, Any]) -> dict[str, Any]:
    """Rubric shared with references/severity-rubric.md. First match wins."""
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise SentryReadOnlyError("Issue metadata must be an object")
    status = data.get("status")
    level = data.get("level", metadata.get("level"))
    if status is not None and not isinstance(status, str):
        raise SentryReadOnlyError("Issue status must be a string")
    if level is not None and not isinstance(level, str):
        raise SentryReadOnlyError("Issue level must be a string")
    status = status.lower() if status else None
    level = level.lower() if level else None
    users = _int(data.get("userCount") if "userCount" in data else data.get("user_count"))
    count = _int(data.get("count"))
    env = (_environment(data) or "").lower()
    prod = env in {"production", "prod"}

    missing = [name for name, value in (("level", level), ("userCount", users), ("count", count)) if value is None]
    if level not in {None, "fatal", "error", "warning", "info", "debug"}:
        missing.append("recognized_level")
    if level == "error" and count is not None and count >= 1000 and not env:
        missing.append("environment")
    minimum = (
        "SEV-1"
        if level == "fatal" or (level == "error" and users is not None and users >= 100)
        else "SEV-2"
        if level == "error" or (users is not None and users >= 10) or (count is not None and count >= 100)
        else None
    )
    if missing:
        sev, why = "INCONCLUSIVE", "Missing evidence prevents complete classification under the local rubric"
    elif status in {"resolved", "ignored"}:
        sev, why = "SEV-4", f"status is {status}; not an active page"
    elif level == "fatal" or (level == "error" and users >= 100) or (level == "error" and count >= 1000 and prod):
        sev, why = "SEV-1", "fatal, or error with userCount>=100, or prod error with count>=1000"
    elif level == "error" or users >= 10 or count >= 100:
        sev, why = "SEV-2", "error, or userCount>=10, or count>=100"
    elif level == "warning":
        sev, why = "SEV-3", "warning below the SEV-2 counts"
    else:
        sev, why = "SEV-4", "info/debug/unknown level below the count gates"

    release = _release(data)
    first = data.get("firstSeen") or data.get("first_seen")
    last = data.get("lastSeen") or data.get("last_seen")
    event_ts = data.get("dateCreated") or data.get("timestamp")
    timeline = [t for t in (first, last, event_ts) if isinstance(t, str) and t]
    return {
        "severity": sev,
        "classification": "incomplete" if missing else "local_rubric",
        "missing_fields": missing,
        "minimum_severity_from_observed_evidence": minimum,
        "severity_reason": why,
        "status": status,
        "level": level or None,
        "userCount": users,
        "count": count,
        "environment": _environment(data),
        "suspect_release": release,
        "suspect_release_note": None if release else "unknown — do not invent a release",
        "timeline_timestamps": timeline,
        "postmortem_times_rule": "use only timeline_timestamps; do not invent times",
        "filtered_plus_dropped": "do not sum; this script does not read stats",
    }


def load_payload(args: argparse.Namespace, client: SentryReadOnlyClient) -> tuple[dict[str, Any], str]:
    if args.pasted:
        raw = read_text(args.pasted, inline=True)
        return client.fetch_event_json("pasted", pasted=raw), "advisory"
    if args.event_id:
        try:
            return client.fetch_event_json(args.event_id), "live"
        except SentryReadOnlyError as exc:
            raise SystemExit(f"advisory required: {exc}") from exc
    raise SystemExit("pass --pasted <file|json|-> or --event-id")


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue severity from payload only")
    parser.add_argument("--pasted", help="JSON file, raw JSON, or - for stdin")
    parser.add_argument("--event-id", help="Live read via sentry_readonly (no write)")
    parser.add_argument("--apply", action="store_true", help="Rejected")
    args = parser.parse_args()
    client = client_from_env()
    if args.apply:
        try:
            client.refuse_write("issue status update")
        except SentryReadOnlyError as exc:
            print(json.dumps({"ok": False, "wrote": False, "error": str(exc)}))
            return 2
    data, mode = load_payload(args, client)
    out = severity(data)
    out["mode"] = "advisory" if client.advisory or mode == "advisory" else mode
    out["writes"] = "none"
    emit_json(out)
    return 2 if out["classification"] == "incomplete" else 0


if __name__ == "__main__":
    raise SystemExit(run_cli(main))
