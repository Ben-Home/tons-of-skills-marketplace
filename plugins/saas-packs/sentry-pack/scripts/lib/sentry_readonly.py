"""Canonical offline runtime; sync-runtime.py bundles identical skill-local copies.

No credentials are read and no live transport is implemented. An individual
skill never searches outside its own directory for executable dependencies.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 8 * 1024 * 1024
SNTRYS = re.compile(r"sntrys_[A-Za-z0-9._-]+")
SECRET_ASSIGN = re.compile(
    r"(\b(?:SENTRY_AUTH_TOKEN|access_token|auth_token|api_key|client_secret)"
    r"[\"']?\s*[:=]\s*)(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;]+)",
    re.IGNORECASE,
)
QUOTED_AUTH = re.compile(r"([\"']Authorization[\"']\s*:\s*)(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')", re.I)
BEARER = re.compile(r"(Authorization:\s*Bearer\s+)([^\s,;\"']+)", re.I)
QUERY_SECRET = re.compile(r"([?&](?:token|access_token|api_key|secret)=)[^&#\s\"']+", re.I)
SECRET_KEYS = {"sentryauthtoken", "authorization", "accesstoken", "authtoken", "apikey", "clientsecret"}


class SentryReadOnlyError(ValueError):
    """Input is incomplete or unsupported; no action was taken."""


def redact_with_counts(text: str) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    text, counts["sntrys"] = SNTRYS.subn("[REDACTED_SNTRYS]", text)

    def assignment(match: re.Match[str]) -> str:
        value = match.group(2)
        quote = value[0] if value[0] in "\"'" else ""
        return match.group(1) + quote + "[REDACTED]" + quote

    text, counts["auth_token_assign"] = SECRET_ASSIGN.subn(assignment, text)
    text, counts["authorization_value"] = QUOTED_AUTH.subn(assignment, text)
    text, counts["bearer"] = BEARER.subn(r"\1[REDACTED]", text)
    text, counts["query_secret"] = QUERY_SECRET.subn(r"\1[REDACTED]", text)
    return text, counts


def redact_text(text: str) -> str:
    return redact_with_counts(text)[0]


def sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if re.sub(r"[^a-z0-9]", "", str(key).lower()) in SECRET_KEYS else sanitized(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitized(item) for item in value]
    return redact_text(value) if isinstance(value, str) else value


def emit_json(payload: Any) -> None:
    print(json.dumps(sanitized(payload), indent=2, allow_nan=False))


def read_text(source: str, *, inline: bool = False, limit: int = MAX_INPUT_BYTES) -> str:
    if inline and source.lstrip().startswith(("{", "[")):
        raw = source.encode("utf-8")
    elif source == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        raw = stream.read(limit + 1)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
    else:
        if os.path.islink(source):
            raise SentryReadOnlyError("Input symlinks are not accepted")
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise SentryReadOnlyError("Input must be a regular file within the documented byte limit")
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(limit + 1)
        finally:
            os.close(descriptor)
    if len(raw) > limit:
        raise SentryReadOnlyError("Input exceeds the documented byte limit")
    return raw.decode("utf-8", errors="strict")


SOURCE_EXCLUSIONS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__"}


def source_files(root: Path, suffixes: set[str]) -> tuple[list[Path], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    if root.is_symlink() or not root.exists():
        return [], [{"path": str(root), "reason": "missing path or symlink"}]
    if root.is_file():
        return ([root], []) if root.suffix.lower() in suffixes else ([], [{"reason": "unsupported file suffix"}])
    found: list[Path] = []
    directories = 0
    for directory, dirs, names in os.walk(
        root, followlinks=False, onerror=lambda _: errors.append({"reason": "unreadable directory"})
    ):
        directories += 1
        if directories > 2048:
            errors.append({"reason": "directory budget exceeded"})
            break
        for name in list(dirs):
            child = Path(directory) / name
            if name in SOURCE_EXCLUSIONS:
                dirs.remove(name)
            elif child.is_symlink():
                dirs.remove(name)
                errors.append({"path": str(child), "reason": "symlink directory not inspected"})
        dirs.sort()
        for name in sorted(names):
            path = Path(directory) / name
            if path.suffix.lower() in suffixes:
                found.append(path)
                if len(found) > 512:
                    errors.append({"reason": "file budget exceeded"})
                    return found[:512], errors
    return found, errors


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SentryReadOnlyError("Duplicate JSON object keys are unsupported")
        result[key] = value
    return result


def _float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise SentryReadOnlyError("JSON numbers must be finite")
    return number


def _constant(_value: str) -> None:
    raise SentryReadOnlyError("Nonstandard JSON constants are unsupported")


def parse_json(raw: str) -> Any:
    if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
        raise SentryReadOnlyError("JSON exceeds the documented byte limit")
    try:
        result = json.loads(raw, object_pairs_hook=_object, parse_float=_float, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise SentryReadOnlyError("Malformed or excessively nested JSON") from exc
    pending = [(result, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise SentryReadOnlyError("JSON nesting exceeds 64 levels")
        values = item.values() if isinstance(item, dict) else item if isinstance(item, list) else ()
        pending.extend((value, depth + 1) for value in values)
    return result


def load_json(source: str) -> Any:
    return parse_json(read_text(source, inline=True))


def run_cli(main) -> int:
    try:
        result = main()
        return 0 if result is None else result
    except (OSError, ValueError, TypeError, RecursionError, OverflowError) as exc:
        detail = str(exc) if isinstance(exc, SentryReadOnlyError) else "Input is unavailable, malformed or unsupported"
        emit_json({"ok": False, "status": "incomplete", "error": detail, "wrote": False})
        return 2


class SentryReadOnlyClient:
    """Compatibility parser for offline exports; never a live API client."""

    def __init__(self, token: str | None = None, org: str | None = None) -> None:
        self.token = None
        self.org = org
        self.advisory = True

    @staticmethod
    def _parse_json(raw: str, *, what: str) -> dict[str, Any]:
        data = parse_json(raw)
        if not isinstance(data, dict):
            raise SentryReadOnlyError(f"The {what} export must be a JSON object")
        return data

    def fetch_org_stats_usage(self, *, pasted: str | None = None) -> dict[str, Any]:
        if pasted is None:
            raise SentryReadOnlyError("Supply an offline stats export; live reads are not implemented")
        return self._parse_json(pasted, what="stats")

    def fetch_event_json(self, event_id: str, *, pasted: str | None = None) -> dict[str, Any]:
        if pasted is None:
            raise SentryReadOnlyError("Supply an offline event export; live reads are not implemented")
        return self._parse_json(pasted, what="event")

    def fetch_project_settings(self, project: str, *, pasted: str | None = None) -> dict[str, Any]:
        if pasted is None:
            raise SentryReadOnlyError("Supply an offline settings export; live reads are not implemented")
        return self._parse_json(pasted, what="settings")

    def refuse_write(self, action: str) -> None:
        raise SentryReadOnlyError(f"read-only client refuses write action: {action}")


def client_from_env() -> SentryReadOnlyClient:
    """Historical function name; intentionally does not read the environment."""
    return SentryReadOnlyClient()


if __name__ == "__main__":
    emit_json({"advisory": True, "live_reads": False, "credential_reads": False})
