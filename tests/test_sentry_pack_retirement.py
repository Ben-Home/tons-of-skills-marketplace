"""Keep the curated Sentry operators independent of retired tutorial generators."""

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "plugins/saas-packs/sentry-pack"
OPERATORS = {
    "sentry-quota-leak-hunter",
    "sentry-event-forensics",
    "sentry-release-medic",
    "sentry-issue-triage",
    "sentry-pii-scrub-enforcer",
}


class SentryRetirementContract(unittest.TestCase):
    def test_legacy_database_guard_precedes_all_writes(self):
        script = ROOT / "plugins/saas-packs/scripts/generate-skill-db.py"
        spec = importlib.util.spec_from_file_location("sentry_legacy_database", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for vendor in ("sentry", " SENTRY ", "sentry-pack"):
            with self.subTest(vendor=vendor), unittest.mock.patch.object(module.os, "makedirs") as mkdir:
                with self.assertRaisesRegex(ValueError, "generation is retired"):
                    module.generate_skill_database(vendor, "Sentry", "flagship+")
                mkdir.assert_not_called()

    def test_pack_generation_cannot_overwrite_curated_skills(self):
        script = ROOT / "plugins/saas-packs/_templates/scripts/generate-pack.py"
        # Execute the actual function without requiring the optional template engine.
        function = next(
            node
            for node in ast.parse(script.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "generate_pack"
        )
        code = compile(ast.Module(body=[function], type_ignores=[]), str(script), "exec")
        with tempfile.TemporaryDirectory() as folder:
            load = Mock(side_effect=AssertionError("Protected pack reached template configuration"))
            namespace = {"load_vendor_config": load, "SAAS_PACKS_DIR": Path(folder)}
            exec(code, namespace)
            for vendor in ("sentry", " SENTRY ", "Sentry-Pack"):
                for dry_run in (True, False):
                    self.assertTrue(namespace["generate_pack"](vendor, dry_run))
            load.assert_not_called()
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_only_five_real_skills_and_no_nested_agent_definitions(self):
        self.assertEqual({p.parent.name for p in PACK.glob("skills/*/SKILL.md")}, OPERATORS)
        self.assertEqual(list(PACK.glob("skills/*/agents/*.md")), [])
        self.assertEqual(len(list(PACK.glob("skills/*/references/roles/*.md"))), 21)
        self.assertFalse((ROOT / "plugins/saas-packs/skill-databases/sentry").exists())
        canonical = (PACK / "scripts/lib/sentry_readonly.py").read_bytes()
        for name in OPERATORS:
            self.assertEqual((PACK / "skills" / name / "scripts/lib/sentry_readonly.py").read_bytes(), canonical)

    def test_sixteen_real_aliases_and_fourteen_deliberate_removals(self):
        redirects = json.loads((ROOT / "marketplace/src/data/skill-redirects.json").read_text())["redirects"]
        aliases = {x["from"]: x for x in redirects if x["from"].startswith("sentry-")}
        overrides = json.loads((ROOT / "marketplace/src/data/retired-path-overrides.json").read_text())["overrides"]
        decisions = {p: row for p, row in overrides.items() if p.startswith("/skills/sentry-")}
        self.assertEqual(len(aliases), 16)
        self.assertEqual(len(decisions), 30)
        self.assertNotIn("sentry-hello-world", aliases)
        self.assertNotIn("to", decisions["/skills/sentry-hello-world"])
        self.assertEqual(sum("to" not in row for row in decisions.values()), 14)
        for name, row in aliases.items():
            self.assertIn(row["to"], OPERATORS)
            self.assertEqual(row["status"], 301)
            self.assertEqual(decisions["/skills/" + name]["to"], "/skills/" + row["to"] + "/")
            self.assertFalse((PACK / "skills" / name / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
