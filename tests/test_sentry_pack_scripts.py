"""Regression contract for the sentry-pack v2 helper scripts.

The pack's skills are advisory: scripts read pasted input, print to stdout,
make no network calls and refuse write actions. These tests pin that contract.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "plugins" / "saas-packs" / "sentry-pack"
LIB = PACK / "scripts" / "lib"
SCRIPTS = sorted((PACK / "skills").glob("*/scripts/*.py"))

# (script relative to the pack, extra args) for every script with an --apply path.
REFUSAL_CASES = (
    ("skills/sentry-event-forensics/scripts/parse-resolved-with.py", []),
    ("skills/sentry-issue-triage/scripts/fingerprint-from-event.py", []),
    ("skills/sentry-issue-triage/scripts/issue-context.py", []),
    ("skills/sentry-quota-leak-hunter/scripts/parse-usage-stats.py", []),
    ("skills/sentry-pii-scrub-enforcer/scripts/settings-diff.py", []),
)


def run(script: Path, *args: str, stdin: str = "{}") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, script.name, *args],
        cwd=script.parent,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


class SentryPackScriptsContract(unittest.TestCase):
    def test_every_script_answers_help(self):
        self.assertGreaterEqual(len(SCRIPTS), 11)
        for script in SCRIPTS:
            with self.subTest(script=script.name):
                result = run(script, "--help")
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_apply_is_refused_cleanly_without_a_traceback(self):
        for rel, extra in REFUSAL_CASES:
            script = PACK / rel
            with self.subTest(script=script.name):
                result = run(script, "--apply", *extra)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("refuses write action", result.stdout + result.stderr)

    def test_no_script_imports_a_network_client(self):
        for script in [*SCRIPTS, LIB / "sentry_readonly.py"]:
            source = script.read_text(encoding="utf-8")
            with self.subTest(script=script.name):
                for banned in ("import requests", "urllib.request", "import httpx", "http.client", "subprocess"):
                    self.assertNotIn(banned, source)

    def test_redaction_removes_all_three_token_shapes(self):
        script = PACK / "skills/sentry-event-forensics/scripts/redact-support-bundle.py"
        bundle = (
            "dsn ok\n"
            "token sntrys_abcDEF123.xyz-789\n"
            "SENTRY_AUTH_TOKEN=supersecretvalue\n"
            "Authorization: Bearer anothersecret\n"
        )
        result = run(script, "--json", "-", stdin=bundle)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for secret in ("sntrys_abcDEF123", "supersecretvalue", "anothersecret"):
            self.assertNotIn(secret, result.stdout)

    def test_client_is_advisory_and_honest_about_live_fetch(self):
        sys.path.insert(0, str(LIB))
        try:
            from sentry_readonly import SentryReadOnlyClient, SentryReadOnlyError
        finally:
            sys.path.remove(str(LIB))
        client = SentryReadOnlyClient(token=None)
        self.assertEqual(client.fetch_event_json("abc", pasted=json.dumps({"id": "abc"})), {"id": "abc"})
        with self.assertRaises(SentryReadOnlyError):
            client.fetch_event_json("abc", pasted="not json")
        with self.assertRaises(SentryReadOnlyError):
            client.refuse_write("anything")
        source = (LIB / "sentry_readonly.py").read_text(encoding="utf-8")
        self.assertNotIn("TODO", source)


class SentryOperatorEvidenceTests(unittest.TestCase):
    def cli(self, skill, script, *args, payload=None):
        result = run(PACK / "skills" / skill / "scripts" / script, *args, stdin=payload or "{}")
        self.assertNotIn("Traceback", result.stderr)
        return result, json.loads(result.stdout)

    def test_every_individually_installed_skill_has_its_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            for skill in sorted({script.parent.parent for script in SCRIPTS}):
                target = isolated / skill.name
                shutil.copytree(skill, target)
                self.assertEqual(
                    (target / "scripts/lib/sentry_readonly.py").read_bytes(), (LIB / "sentry_readonly.py").read_bytes()
                )
                for script in sorted((target / "scripts").glob("*.py")):
                    with self.subTest(skill=skill.name, script=script.name):
                        result = subprocess.run(
                            [sys.executable, "-I", "-B", str(script), "--help"],
                            cwd=isolated,
                            env={"PATH": os.environ["PATH"]},
                            capture_output=True,
                            text=True,
                            timeout=20,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_bundled_runtime_cannot_fall_back_to_an_ambient_module(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            copied = root / "installed"
            shutil.copytree(PACK / "skills/sentry-quota-leak-hunter", copied)
            (copied / "scripts/lib/sentry_readonly.py").unlink()
            marker = root / "ambient-executed"
            (root / "sentry_readonly.py").write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
            result = subprocess.run(
                [sys.executable, "-B", str(copied / "scripts/parse-usage-stats.py"), "--help"],
                cwd=root,
                env={"PATH": os.environ["PATH"], "PYTHONPATH": str(root)},
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_missing_issue_evidence_is_not_low_severity(self):
        result, report = self.cli("sentry-issue-triage", "issue-context.py", "--pasted", "-", payload="{}")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["severity"], "INCONCLUSIVE")
        self.assertIsNone(report["count"])
        self.assertIsNone(report["userCount"])

    def test_observed_issue_counts_keep_the_local_rubric(self):
        payload = {"level": "error", "count": "4000", "userCount": 120, "environment": "production", "release": "r1"}
        result, report = self.cli(
            "sentry-issue-triage", "issue-context.py", "--pasted", "-", payload=json.dumps(payload)
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["severity"], "SEV-1")
        self.assertEqual(report["suspect_release"], "r1")

    def test_usage_rejects_non_counts_instead_of_truncating_them(self):
        for value in (-1, -1.5, 1.5, True, "12", None):
            with self.subTest(value=value):
                result, _ = self.cli(
                    "sentry-quota-leak-hunter",
                    "parse-usage-stats.py",
                    "--json",
                    "-",
                    payload=json.dumps({"categories": {"error": {"accepted": value}}}),
                )
                self.assertNotEqual(result.returncode, 0)
        result, report = self.cli(
            "sentry-quota-leak-hunter",
            "parse-usage-stats.py",
            "--json",
            "-",
            payload='{"categories":{"error":{"accepted":12,"filtered":3}}}',
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["categories"]["error"], {"accepted": 12, "filtered": 3})

    def test_missing_previous_meter_is_not_assumed_zero(self):
        payload = {
            "categories": {"error": {"accepted": 12}},
            "previous_window": {"categories": {"span": {"accepted": 2}}},
        }
        result, report = self.cli(
            "sentry-quota-leak-hunter", "parse-usage-stats.py", "--json", "-", payload=json.dumps(payload)
        )
        self.assertEqual(result.returncode, 0)
        self.assertIsNone(report["meter_that_moved"])

    def test_query_metadata_never_establishes_release_health(self):
        payload = {
            "api_read": True,
            "groups_returned": 1,
            "query": {
                "project": "web",
                "environment": "prod",
                "release": "r1",
                "fields": ["crash_free_rate(session)"],
                "statsPeriod": "24h",
                "interval": "1h",
            },
        }
        for flag in ([], ["--mark-fine"]):
            with self.subTest(flag=flag):
                result, report = self.cli(
                    "sentry-release-medic", "assess-session-stats.py", "--json", "-", *flag, payload=json.dumps(payload)
                )
                self.assertIsNone(report["health_fine"])
                self.assertFalse(report["api_read_verified"])
                self.assertEqual(result.returncode, 2 if flag else 0)
        for change in (
            {"project": ["one", "two"]},
            {"environment": ["prod", "dev"]},
            {"fields": []},
            {"interval": "unknown"},
        ):
            with self.subTest(change=change):
                candidate = {**payload, "query": {**payload["query"], **change}}
                result, report = self.cli(
                    "sentry-release-medic", "assess-session-stats.py", "--json", "-", payload=json.dumps(candidate)
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(report["query_checks_pass"])

    def test_missing_or_mistyped_settings_do_not_become_clean_projects(self):
        for settings in ({}, {"sendDefaultPii": 0}, {"sendDefaultPii": "false"}):
            with self.subTest(settings=settings):
                result, report = self.cli(
                    "sentry-pii-scrub-enforcer",
                    "settings-diff.py",
                    "--projects",
                    json.dumps({"slug": "web", "settings": settings}),
                    "--standard",
                    '{"sendDefaultPii":false}',
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(report["incomplete_projects"], ["web"])
                self.assertEqual(report["clean_projects"], [])
        result, report = self.cli(
            "sentry-pii-scrub-enforcer",
            "settings-diff.py",
            "--projects",
            '{"slug":"web","settings":{"sendDefaultPii":false}}',
            "--standard",
            '{"sendDefaultPii":false}',
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["clean_projects"], ["web"])

    def test_empty_or_unknown_standards_cannot_bless_a_project(self):
        for standard in ("{}", '{"madeUpPolicy":false}'):
            with self.subTest(standard=standard):
                result, _ = self.cli(
                    "sentry-pii-scrub-enforcer",
                    "settings-diff.py",
                    "--projects",
                    '{"slug":"web","settings":{}}',
                    "--standard",
                    standard,
                )
                self.assertNotEqual(result.returncode, 0)

    def test_shipped_policy_example_is_usable_without_loosening_unknown_keys(self):
        standard = PACK / "skills/sentry-pii-scrub-enforcer/references/project-standard.example.json"
        values = json.loads(standard.read_text())["settings"]
        result, report = self.cli(
            "sentry-pii-scrub-enforcer",
            "settings-diff.py",
            "--projects",
            "-",
            "--standard",
            str(standard),
            payload=json.dumps({"slug": "example-review", "settings": values}),
        )
        self.assertEqual(result.returncode, 0, report)
        self.assertEqual(report["clean_projects"], ["example-review"])
        self.assertEqual(report["incomplete_projects"], [])
        self.assertEqual(report["compared_standard_keys"], sorted(values))

    def test_redaction_handles_quoted_whitespace_and_multiline_values(self):
        for payload in (
            '{"SENTRY_AUTH_TOKEN": "DO_NOT_ECHO with spaces"}',
            "SENTRY_AUTH_TOKEN='DO_NOT_ECHO\nsecond line'",
            '{"Authorization":"Bearer DO_NOT_ECHO with spaces"}',
        ):
            with self.subTest(payload=payload):
                result, report = self.cli(
                    "sentry-event-forensics", "redact-support-bundle.py", "--json", "-", payload=payload
                )
                self.assertEqual(result.returncode, 0)
                self.assertNotIn("DO_NOT_ECHO", report["text"])

    def test_debug_id_word_and_map_alone_do_not_prove_runtime_injection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            js = root / "app.js"
            js.write_text('const debugId = "not an injected UUID";\n')
            result, report = self.cli("sentry-release-medic", "grep_debug_id.py", str(js))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(report["verdict"], "ABSENT")
            identifier = "11111111-2222-4333-8444-555555555555"
            js.write_text(f"console.log(1);\n//# debugId={identifier}\n")
            source_map = root / "app.js.map"
            source_map.write_text(json.dumps({"version": 3, "debug_id": identifier}))
            result, report = self.cli("sentry-release-medic", "grep_debug_id.py", str(root))
            self.assertEqual(result.returncode, 0)
            self.assertEqual(report["locally_matching_debug_ids"], [identifier])
            self.assertIsNone(report["running_bytes_injected"])

    def test_log_comment_is_not_a_logging_write_or_a_guessed_field(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "example.py"
            path.write_text("# Do not log event_id; DO_NOT_ECHO_SOURCE_SECRET\n")
            result, report = self.cli(
                "sentry-issue-triage", "find-event-id-log.py", "--root", temporary, "--event-id", "a" * 32
            )
            self.assertEqual(result.returncode, 0)
            self.assertFalse(report["logging_write_proven"])
            self.assertIsNone(report["query"])
            self.assertIsNone(report["query_template"])
            self.assertNotIn("DO_NOT_ECHO_SOURCE_SECRET", result.stdout)

    def test_hook_substrings_and_source_tokens_are_not_runtime_coverage(self):
        result, report = self.cli(
            "sentry-pii-scrub-enforcer",
            "scrub-hook-coverage.py",
            "--pasted",
            "Sentry.init({beforeSendTransaction: e => e});",
        )
        self.assertEqual(result.returncode, 0)
        row = report["files"][0]
        self.assertFalse(row["hooks"]["beforeSend"])
        self.assertTrue(row["hooks"]["beforeSendTransaction"])
        self.assertEqual(row["effective_hook_coverage"], "not_verified")
        self.assertIsNone(report["replay_on"])

    def test_strict_json_and_missing_files_fail_without_tracebacks(self):
        for payload in (
            '{"categories":{},"categories":{}}',
            '{"categories":{"error":{"accepted":NaN}}}',
            '{"categories":{"error":{"accepted":1e999}}}',
        ):
            with self.subTest(payload=payload):
                result, _ = self.cli("sentry-quota-leak-hunter", "parse-usage-stats.py", "--json", "-", payload=payload)
                self.assertNotEqual(result.returncode, 0)
        result, _ = self.cli(
            "sentry-quota-leak-hunter", "parse-usage-stats.py", "--json", "/does-not-exist/sentry.json"
        )
        self.assertNotEqual(result.returncode, 0)

    def test_erasure_plan_never_asserts_subject_wide_completion(self):
        result, report = self.cli(
            "sentry-pii-scrub-enforcer",
            "print-gdpr-delete-request.py",
            "--org",
            "example",
            "--user-id",
            "subject",
            "--issue-id",
            "123",
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(report["erasure_completed"])
        self.assertFalse(report["issue_deletes_not_sent"][0]["sent"])
        self.assertEqual(set(report["coverage"].values()), {"not_verified"})


if __name__ == "__main__":
    unittest.main()
