"""Tests of kit bookkeeping only; not tests of any game or native Agent host."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "project.py"
spec = importlib.util.spec_from_file_location("game_production_project", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class ProjectToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "中文游戏 project"
        mod.init_project(self.root, name="示例塔防")

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, name):
        return json.loads((self.root / ".production" / (name + ".json")).read_text(encoding="utf-8"))

    def write(self, name, obj):
        (self.root / ".production" / (name + ".json")).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    def pass_gate(self, gate):
        evidence = self.root / ".production/evidence/test.txt"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("actual test evidence fixture\n", encoding="utf-8")
        gate.update(status="PASS", criteria="Example contract fixture", subject_revision="fixture-build-1",
                    reviewer={"identity": "test fixture", "independence": "self_review"},
                    evidence=[{"path": ".production/evidence/test.txt", "sha256": mod.digest(evidence),
                               "kind": "test-log", "observed": "fixture expectation met"}])

    def test_initialization_creates_skill_and_records(self):
        self.assertTrue((self.root / mod.SKILL_PATH / "SKILL.md").is_file())
        self.assertEqual(self.read("PROJECT")["name"], "示例塔防")
        self.assertIn(".production/local/", (self.root / ".gitignore").read_text())

    def test_repeated_init_keeps_project_and_state(self):
        data = self.read("STATE"); data["next_action"] = "do not overwrite"; self.write("STATE", data)
        pid = self.read("PROJECT")["project_id"]
        mod.init_project(self.root, name="wrong replacement")
        self.assertEqual(self.read("STATE")["next_action"], "do not overwrite")
        self.assertEqual(self.read("PROJECT")["project_id"], pid)
        self.assertEqual(self.read("PROJECT")["name"], "示例塔防")
        self.assertEqual((self.root / "AGENTS.md").read_text().count("GAME_PRODUCTION_V3_BEGIN"), 1)

    def test_existing_agents_and_game_code_retained(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("User rule: do not edit core\n", encoding="utf-8")
        source = self.root / "game.ts"; source.write_text("const keep = true;\n")
        mod.init_project(self.root)
        self.assertTrue(agents.read_text().startswith("User rule"))
        self.assertEqual(source.read_text(), "const keep = true;\n")

    def test_legacy_skill_detection_blocks_init_without_creating_v3(self):
        other = Path(self.tmp.name) / "legacy_skill"
        (other / mod.LEGACY_SKILL_PATH).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Legacy workflow detected"):
            mod.init_project(other)
        self.assertFalse((other / mod.SKILL_PATH).exists())

    def test_legacy_agents_detection_blocks_init(self):
        other = Path(self.tmp.name) / "legacy_agents"
        other.mkdir()
        (other / "AGENTS.md").write_text("<!-- TOTOP_GAME_PRODUCTION_V2_BEGIN -->\n")
        with self.assertRaisesRegex(ValueError, "Legacy AGENTS workflow block"):
            mod.init_project(other)
        self.assertFalse((other / mod.SKILL_PATH).exists())

    def test_platform_scope_is_not_hardcoded(self):
        project = self.read("PROJECT")
        self.assertEqual(project["scope"]["runtime"], "user_selected")
        self.assertEqual(project["scope"]["platforms"], [])
        self.assertFalse(project["platform_contract"]["verified"])

    def test_different_installed_skill_refused(self):
        target = self.root / mod.SKILL_PATH / "SKILL.md"
        target.write_text("custom local skill\n")
        with self.assertRaisesRegex(ValueError, "differs"):
            mod.init_project(self.root)
        self.assertEqual(target.read_text(), "custom local skill\n")

    def test_structure_valid_not_game_acceptance(self):
        errors, warnings = mod.validate_project(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("not target acceptance" in w for w in warnings))

    def test_strict_requires_contract_and_gates(self):
        errors, _ = mod.validate_project(self.root, strict=True)
        self.assertTrue(any("contract" in e for e in errors))
        self.assertTrue(any("required target gate" in e for e in errors))

    def test_pass_without_evidence_fails(self):
        obj = self.read("GATES"); obj["gates"][0]["status"] = "PASS"; self.write("GATES", obj)
        errors, _ = mod.validate_project(self.root)
        self.assertTrue(any("requires evidence" in e for e in errors))

    def test_verified_file_reference_accepted(self):
        obj = self.read("GATES"); self.pass_gate(obj["gates"][0]); self.write("GATES", obj)
        self.assertEqual(mod.validate_project(self.root)[0], [])

    def test_tampered_evidence_rejected(self):
        obj = self.read("GATES"); self.pass_gate(obj["gates"][0]); self.write("GATES", obj)
        (self.root / ".production/evidence/test.txt").write_text("changed")
        self.assertTrue(any("mismatch" in e for e in mod.validate_project(self.root)[0]))

    def test_missing_evidence_rejected(self):
        obj = self.read("GATES"); self.pass_gate(obj["gates"][0]); self.write("GATES", obj)
        (self.root / ".production/evidence/test.txt").unlink()
        self.assertTrue(any("missing" in e for e in mod.validate_project(self.root)[0]))

    def test_absolute_and_traversal_paths_rejected(self):
        for unsafe in ("../outside.txt", "/etc/passwd", "E:\\secrets.txt", "\\\\server\\share\\x", "x/../../y"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    mod.safe_path(self.root, unsafe)

    def test_symlink_escape_rejected(self):
        outside = Path(self.tmp.name) / "outside"; outside.mkdir()
        link = self.root / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit symlinks")
        with self.assertRaises(ValueError):
            mod.safe_path(self.root, "escape/file.json")

    def test_na_requires_scope_basis(self):
        obj = self.read("GATES"); obj["gates"][1]["status"] = "NOT_APPLICABLE"; self.write("GATES", obj)
        self.assertTrue(any("scope basis" in e for e in mod.validate_project(self.root)[0]))

    def test_deleted_or_duplicate_gates_rejected(self):
        obj = self.read("GATES"); obj["gates"][1]["id"] = "G01"; self.write("GATES", obj)
        errors, _ = mod.validate_project(self.root)
        self.assertTrue(any("Duplicate" in e for e in errors))
        self.assertTrue(any("Missing default gates" in e for e in errors))

    def test_stage_mode_does_not_change_project_target(self):
        obj = self.read("STATE"); obj["run"].update(mode="stage", allowed_stages=["S3", "S4"], current_stage="S3"); self.write("STATE", obj)
        self.assertEqual(mod.validate_project(self.root)[0], [])
        self.assertEqual(self.read("PROJECT")["delivery_target"], "release_candidate")

    def test_bad_json_reports_error(self):
        (self.root / ".production/STATE.json").write_text("{ broken JSON")
        self.assertTrue(any("Cannot read JSON" in e for e in mod.validate_project(self.root)[0]))

    def test_stop_requires_reason(self):
        obj = self.read("STATE"); obj["run"]["status"] = "EXTERNAL_BLOCKED"; self.write("STATE", obj)
        self.assertTrue(any("stop_reason" in e for e in mod.validate_project(self.root)[0]))

    def test_wrong_candidate_hash_rejected(self):
        artifact = self.root / "candidate.zip"; artifact.write_bytes(b"fixture")
        obj = self.read("STATE"); obj["snapshot"].update(artifact_path="candidate.zip", artifact_sha256="0"*64); self.write("STATE", obj)
        self.assertTrue(any("Candidate artifact" in e for e in mod.validate_project(self.root)[0]))

    def test_strict_fixture_still_not_publication_authorization(self):
        obj = self.read("PROJECT"); obj["acceptance_contract"]["defined"] = True; self.write("PROJECT", obj)
        gates = self.read("GATES")
        for gate in gates["gates"]:
            if gate["required_for_target"]:
                self.pass_gate(gate)
        self.write("GATES", gates)
        errors, warnings = mod.validate_project(self.root, strict=True)
        self.assertEqual(errors, [])
        self.assertEqual(self.read("STATE")["publication_status"], "NOT_AUTHORIZED")
        self.assertTrue(any("not release authorization" in w for w in warnings))

    def test_research_target_has_distinct_required_scope(self):
        other = Path(self.tmp.name) / "research"
        mod.init_project(other, target="research_handoff")
        gates = mod.load_json(other / ".production/GATES.json")["gates"]
        self.assertEqual({g["id"] for g in gates if g["required_for_target"]}, {"G01", "G02", "G04"})
        self.assertTrue(all(g["status"] == "UNVERIFIED" for g in gates))

    def test_handoff_is_read_only_and_does_not_execute_project_commands(self):
        obj = self.read("PROJECT"); obj["known_commands"]["test"] = "DO_NOT_EXECUTE_THIS"; self.write("PROJECT", obj)
        before = (self.root / ".production/STATE.json").read_bytes()
        summary = mod.handoff_summary(self.root)
        self.assertIn("not verified by this script", summary)
        self.assertEqual((self.root / ".production/STATE.json").read_bytes(), before)

    def test_invalid_run_mode_rejected(self):
        obj = self.read("STATE"); obj["run"]["mode"] = "codex_only"; self.write("STATE", obj)
        self.assertTrue(any("mode is invalid" in e for e in mod.validate_project(self.root)[0]))

    def test_wrong_enum_types_report_errors_without_traceback(self):
        obj = self.read("STATE"); obj["run"]["mode"] = []; obj["run"]["status"] = {}; obj["publication_status"] = []
        self.write("STATE", obj)
        gates = self.read("GATES"); gates["gates"][0]["status"] = []; self.write("GATES", gates)
        errors, _ = mod.validate_project(self.root, strict=True)
        self.assertTrue(any("invalid" in e for e in errors))

    def test_false_boolean_not_accepted(self):
        obj = self.read("GATES"); obj["gates"][0]["required_for_target"] = "false"; self.write("GATES", obj)
        self.assertTrue(any("must be boolean" in e for e in mod.validate_project(self.root)[0]))


if __name__ == "__main__":
    unittest.main()
