"""Retired Notes tutorial routes must not become misleading installation paths."""

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class AppleNotesRetirementTests(unittest.TestCase):
    def test_generator_refuses_before_creating_files(self):
        generator = ROOT / "plugins/saas-packs/scripts/generate-skill-db.py"
        for vendor in ("apple-notes", "Apple-Notes", " APPLE-NOTES "):
            with self.subTest(vendor=vendor), tempfile.TemporaryDirectory() as folder:
                result = subprocess.run(
                    ["python3", str(generator), vendor, "Apple Notes", "flagship"],
                    cwd=folder,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("generation is retired", result.stderr)
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_retired_urls_do_not_fall_back_to_another_tool_or_section(self):
        script = """
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {decide,loadLiveUniverse} from './marketplace/scripts/build-retired-path-redirects.mjs';
const overrides=JSON.parse(readFileSync('marketplace/src/data/retired-path-overrides.json')).overrides;
const paths=Object.keys(overrides).filter(p=>p==='/learn/apple-notes'||p==='/plugins/apple-notes-pack'||p.startsWith('/skills/apple-notes-'));
assert.equal(paths.length,33);
const live=loadLiveUniverse();
assert.equal(decide('/plugins/apple-notes-pack',live,{}).status,301);
for(const path of paths){
  assert.equal(live.routes.has(path+'/'),false,path+' remains live');
  const decision=decide(path,live,overrides);
  assert.equal(decision.status,404,path);
  assert.equal(decision.to,undefined,path);
  assert.equal(decision.rule,'reviewed-keep-404',path);
}
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
