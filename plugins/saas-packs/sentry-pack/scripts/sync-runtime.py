#!/usr/bin/env python3
"""Bundle the canonical offline runtime into each independently installable skill."""

import argparse
from pathlib import Path


PACK = Path(__file__).resolve().parents[1]
SKILLS = (
    "sentry-quota-leak-hunter",
    "sentry-event-forensics",
    "sentry-release-medic",
    "sentry-issue-triage",
    "sentry-pii-scrub-enforcer",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = (PACK / "scripts/lib/sentry_readonly.py").read_bytes()
    drift = []
    for skill in SKILLS:
        target = PACK / "skills" / skill / "scripts/lib/sentry_readonly.py"
        if target.is_symlink():
            raise SystemExit("Refusing a runtime destination symlink")
        if target.exists() and target.read_bytes() == source:
            continue
        if args.check:
            drift.append(skill)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source)
    if drift:
        print("Runtime drift: " + ", ".join(drift))
        return 1
    print("Five skill-local runtimes match the canonical source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
