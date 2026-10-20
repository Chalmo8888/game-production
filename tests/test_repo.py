"""Repository layout checks and the creator handoff contract between the two skills."""
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


repo_check = load("repo_check", ROOT / "tools" / "repo_check.py")
gre = load("gre_contract", ROOT / "skills" / "game-reverse-engineering" / "scripts" / "gre.py")
gcp = load("gcp_contract", ROOT / "skills" / "game-creation-polish" / "scripts" / "gcp.py")


class RepositoryCheckTest(unittest.TestCase):
    def test_repository_passes(self):
        self.assertEqual(repo_check.check(ROOT), [])

    def copy_repo(self, folder: Path) -> Path:
        target = folder / "repo"
        shutil.copytree(str(ROOT / "skills"), str(target / "skills"), ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(str(ROOT / "tools"), str(target / "tools"), ignore=shutil.ignore_patterns("__pycache__"))
        for name in ("README.md", "CHANGELOG.md", "QA_REPORT.md"):
            shutil.copy(str(ROOT / name), str(target / name))
        repo_check.write_manifests(target)
        return target

    def test_checker_flags_each_violation_and_passes_the_control(self):
        mutations = {
            "third skill entry": (lambda r: (r / "SKILL.md").write_text("---\nname: game-production\n---\n", encoding="utf-8"),
                                  "Skill entries must be exactly"),
            "retired root prompts": (lambda r: (r / "prompts").mkdir() or (r / "prompts/START_RESEARCH.md").write_text("old\n", encoding="utf-8"),
                                     "retired single-skill file or folder"),
            "retired entry point mention": (lambda r: (r / "skills/game-creation-polish/references/X.md").write_text("run scripts/project.py migrate\n", encoding="utf-8"),
                                            "references a retired entry point"),
            "broken link": (lambda r: (r / "README.md").write_text("[gone](skills/missing.md)\n", encoding="utf-8"), "broken link"),
            "machine path": (lambda r: (r / "README.md").write_text("see C:\\Users\\someone\\proj\n", encoding="utf-8"), "machine-specific path"),
            "secret": (lambda r: (r / "README.md").write_text("token ghp_" + "a1B2" * 9 + "\n", encoding="utf-8"), "secret"),
            "stale manifest": (lambda r: (r / "skills/game-creation-polish/SKILL.md").write_text("edited\n", encoding="utf-8"), "manifest hash mismatch"),
            "diverged shared template": (lambda r: (r / "skills/game-creation-polish/templates/workspace/HANDOFF.md").write_text("fork\n", encoding="utf-8"),
                                         "shared workspace template differs"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            control = self.copy_repo(Path(tmp) / "control")
            self.assertEqual(repo_check.check(control), [], "control copy without mutation must pass")
            for name, (mutate, expected) in mutations.items():
                with self.subTest(name):
                    target = self.copy_repo(Path(tmp) / name.replace(" ", "-"))
                    mutate(target)
                    problems = repo_check.check(target)
                    self.assertTrue(any(expected in p for p in problems), problems)


class CreatorHandoffContractTest(unittest.TestCase):
    """A real gre export, read by gcp: both tools agree on the workspace format, fingerprint and levels."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "studio 工作区"
        (self.root / "engine/core").mkdir(parents=True)
        (self.root / "engine/core/rules.ts").write_text("export const rules = 1;\n", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            gre.init(self.root, "core", "0.1.0", "engine", ["engine/core"], ["https://example.com/game"], "studio")

    def tearDown(self):
        self.tmp.cleanup()

    def test_gre_export_is_consumed_by_gcp(self):
        self.assertEqual(gre.core_fingerprint(self.root, ["engine/core"]), gcp.core_fingerprint(self.root, ["engine/core"]))
        gre.export_handoff(gre.Context(self.root))
        ws = gcp.Workspace(self.root)
        self.assertEqual(gcp.handoff_problems(ws, "core", "0.1.0", "NONE"), [], "an untouched export is intact")
        self.assertTrue(any("is NONE; game production needs CREATOR_CANDIDATE" in p for p in gcp.handoff_problems(ws, "core", "0.1.0")))
        messages = gcp.init_creation(self.root)
        self.assertTrue(any("is NONE" in m for m in messages))
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(gre.AGENTS_MARKERS[0], agents)
        self.assertIn(gcp.AGENTS_MARKERS[0], agents)
        self.assertEqual((self.root / ".gitignore").read_text(encoding="utf-8").count(".production/local/"), 1)
        with self.assertRaisesRegex(ValueError, "explicit request"):
            gcp.game_create(gcp.Workspace(self.root), "game-01", "core")
        gcp.game_create(gcp.Workspace(self.root), "game-01", "core", user_request="基于这个 Base 做第一款游戏")
        self.assertEqual(gcp.validate_workspace(self.root)[0], [])
        self.assertEqual(gre.validate(self.root)[0], [], "a game created by gcp keeps the Base records valid")
        (self.root / "engine/core/rules.ts").write_text("export const rules = 2;\n", encoding="utf-8")
        self.assertTrue(any("differs from the exported fingerprint" in p for p in gcp.handoff_problems(gcp.Workspace(self.root), "core", "0.1.0", "NONE")))

    def test_contract_fields_match_what_gcp_reads(self):
        gre.export_handoff(gre.Context(self.root))
        path = sorted((self.root / ".production/bases/core/handoff/0.1.0").glob("*-CREATOR_HANDOFF.json"))[-1]
        contract = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], gcp.HANDOFF_SCHEMA)
        self.assertEqual(gre.LEVELS, gcp.HANDOFF_LEVELS)
        for key in ("base_id", "base_version", "level", "core_paths", "core_fingerprint", "starter_paths", "fidelity", "rights",
                    "first_use", "independent_reuse", "open_gaps", "files"):
            self.assertIn(key, contract)
        self.assertEqual(set(contract["fidelity"]), {"mechanism", "visual"})
        self.assertTrue({"RE01", "RE02", "RE03", "note"} <= set(contract["rights"]))


if __name__ == "__main__":
    unittest.main()
