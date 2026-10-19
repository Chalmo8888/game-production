"""Tests of kit bookkeeping only; not tests of any game, art quality or native Agent host."""
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "project.py"
spec = importlib.util.spec_from_file_location("game_production_project", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ALL_Q = ["Q%02d" % i for i in range(1, 9)]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_digest(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.root = self.base_dir / "中文 工作区"

    def tearDown(self):
        self.tmp.cleanup()

    # ---- helpers
    def init(self, target="full_pipeline", quota=None, refs=None, root=None):
        mod.init_workspace(root or self.root, name="示例工作区", target=target, references=refs, quota=quota)
        return mod.Workspace(root or self.root)

    def ws(self):
        return mod.Workspace(self.root)

    def read(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, path: Path, obj):
        path.write_bytes(mod.json_bytes(obj))

    def evidence(self, evidence_root: Path, relative: str, content="actual fixture evidence\n"):
        path = evidence_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": relative, "sha256": mod.digest(path), "kind": "test-log", "observed": "fixture expectation met"}

    def pass_gate(self, gate, evidence_root, relative, base_version=None, independence="self_review", identity="fixture QA"):
        gate.update(status="PASS", criteria="fixture criteria for " + gate["id"], subject_revision="fixture-rev-1",
                    reviewer={"identity": identity, "independence": independence},
                    evidence=[self.evidence(evidence_root, relative)])
        if base_version is not None:
            gate["base_version"] = base_version

    def base_gates_path(self, bid="core"):
        return self.root / ".production/bases" / bid / "GATES.json"

    def set_base_gates(self, version, ids, bid="core", status="PASS"):
        path = self.base_gates_path(bid)
        obj = self.read(path)
        for gate in obj["gates"]:
            if gate["id"] in ids:
                if status == "PASS":
                    self.pass_gate(gate, self.root, ".production/bases/%s/evidence/%s-%s.txt" % (bid, gate["id"], version), version)
                else:
                    gate.update(status=status, scope_basis="fixture scope basis")
        self.write(path, obj)

    def make_base_ready(self, version="1.0.0", commercial=False, bid="core"):
        ids = {"B01", "B03", "B04", "B05", "B06", "B07", "B08"} | ({"B02"} if commercial else set())
        self.set_base_gates(version, ids, bid)
        mod.base_update(self.ws(), bid, version, "COMMERCIAL_BASE_CANDIDATE" if commercial else "BASE_READY")

    def register_base(self, version="1.0.0", bid="core"):
        (self.root / "engine").mkdir(parents=True, exist_ok=True)
        mod.base_register(self.ws(), bid, version, "engine", "Core")

    def game_root(self, gid):
        return self.root / "games" / gid

    def game_json(self, gid):
        return self.read(self.game_root(gid) / ".production/GAME.json")

    def fill_design(self, gid):
        root = self.game_root(gid)
        sections = "\n".join("## %d. 第 %d 节\n具体内容与可执行规格。" % (i, i) for i in range(1, 18))
        (root / "design/GAME_DESIGN.md").write_text("# 游戏策划\n" + sections + "\n", encoding="utf-8")
        for name in ("ART_DIRECTION.md", "ART_ASSET_PLAN.md", "ANIMATION_SPEC.md"):
            (root / "design" / name).write_text("# 已填写\n具体规范。\n", encoding="utf-8")
        art = root / "assets/hero.png"
        art.parent.mkdir(parents=True, exist_ok=True)
        art.write_bytes(b"fixture image bytes " + gid.encode())
        assets = self.read(root / ".production/ASSETS.json")
        assets["assets"] = [{"id": "hero", "kind": "character", "status": "verified", "scope": "game",
                             "provenance": "fixture generator", "license": "project-owned fixture",
                             "runtime_files": [{"path": "assets/hero.png", "sha256": mod.digest(art)}],
                             "evidence": [self.evidence(root, ".production/evidence/hero-runtime.txt")]}]
        self.write(root / ".production/ASSETS.json", assets)

    def set_game_gates(self, gid, ids, version="1.0.0", status="PASS", independence="self_review"):
        root = self.game_root(gid)
        path = root / ".production/GATES.json"
        obj = self.read(path)
        for gate in obj["gates"]:
            if gate["id"] in ids:
                if status == "PASS":
                    bound = version if gate["id"] in mod.VERSION_BOUND_GAME_GATES else None
                    ind = independence if gate["id"] == "R04" else "self_review"
                    self.pass_gate(gate, root, ".production/evidence/%s.txt" % gate["id"], bound, ind)
                else:
                    gate.update(status=status, scope_basis="fixture scope basis")
        self.write(path, obj)

    def make_game_ready(self, gid, version="1.0.0"):
        self.fill_design(gid)
        self.set_game_gates(gid, {"D01", "D02"} | set(ALL_Q), version)

    def record_artifact(self, gid):
        artifact = self.game_root(gid) / "dist/candidate.zip"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"candidate " + gid.encode())
        mod.game_update(self.ws(), gid, artifact="dist/candidate.zip")

    def errors(self, **kwargs):
        return mod.validate_workspace(self.root, **kwargs)[0]


class InstallAndSafetyTest(Fixture):
    def test_init_installs_exact_release_manifest(self):
        self.init()
        installed = self.root / mod.SKILL_PATH
        expected = {path for path, _ in mod.kit_manifest()} | {"SHA256SUMS.txt"}
        actual = {p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected)
        self.assertFalse((installed / ".git").exists())
        self.assertTrue((installed / "SKILL.md").is_file())
        self.assertTrue(mod.installed_skill_intact(installed)[0])

    def test_crlf_checkout_of_skill_still_installs_as_lf(self):
        kit = self.base_dir / "crlf-kit"
        for relative, _ in mod.kit_manifest() + [("SHA256SUMS.txt", "")]:
            target = kit / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((mod.KIT_ROOT / relative).read_bytes().replace(b"\n", b"\r\n"))
        original = mod.KIT_ROOT
        mod.KIT_ROOT = kit
        try:
            self.init()
        finally:
            mod.KIT_ROOT = original
        installed = self.root / mod.SKILL_PATH
        self.assertTrue(mod.installed_skill_intact(installed)[0])
        self.assertNotIn(b"\r\n", (installed / "SKILL.md").read_bytes())

    def test_init_creates_workspace_records_and_local_ignore(self):
        ws = self.init()
        self.assertEqual(ws.data["name"], "示例工作区")
        self.assertEqual(ws.data["schema_version"], mod.SCHEMA_VERSION)
        self.assertIn(".production/local/", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertTrue((self.root / ".production/local/ENVIRONMENT.json").is_file())
        self.assertEqual(self.errors(), [])

    def test_repeated_init_keeps_workspace_and_agents_block_once(self):
        ws = self.init()
        ws.data["next_action"] = "do not overwrite"
        ws.save()
        wid = ws.data["workspace_id"]
        mod.init_workspace(self.root, name="wrong replacement")
        again = self.ws()
        self.assertEqual(again.data["next_action"], "do not overwrite")
        self.assertEqual(again.data["workspace_id"], wid)
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8").count(mod.AGENTS_V4[0]), 1)

    def test_existing_agents_and_game_code_retained(self):
        self.root.mkdir(parents=True)
        (self.root / "AGENTS.md").write_text("User rule: do not edit core\n", encoding="utf-8")
        (self.root / "game.ts").write_text("const keep = true;\n", encoding="utf-8")
        self.init()
        self.assertTrue((self.root / "AGENTS.md").read_text(encoding="utf-8").startswith("User rule"))
        self.assertEqual((self.root / "game.ts").read_text(encoding="utf-8"), "const keep = true;\n")

    def test_legacy_totop_detection_blocks_init(self):
        (self.root / mod.LEGACY_SKILL_PATH).mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "Legacy workflow detected"):
            self.init()
        self.assertFalse((self.root / mod.SKILL_PATH).exists())

    def test_different_installed_skill_refused(self):
        self.init()
        target = self.root / mod.SKILL_PATH / "SKILL.md"
        target.write_text("custom local skill\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            mod.init_workspace(self.root)
        self.assertEqual(target.read_text(encoding="utf-8"), "custom local skill\n")

    def test_batch_target_requires_explicit_quota(self):
        with self.assertRaisesRegex(ValueError, "batch target needs"):
            self.init(target="batch")

    def test_absolute_and_traversal_paths_rejected(self):
        self.root.mkdir(parents=True)
        for unsafe in ("../outside.txt", "/etc/passwd", "E:\\secrets.txt", "\\\\server\\share\\x", "x/../../y"):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    mod.safe_path(self.root, unsafe)

    def test_symlink_escape_rejected(self):
        self.root.mkdir(parents=True)
        outside = self.base_dir / "outside"
        outside.mkdir()
        link = self.root / "escape"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Host does not permit symlinks")
        with self.assertRaises(ValueError):
            mod.safe_path(self.root, "escape/file.json")

    def test_bad_json_reports_error_without_traceback(self):
        self.init()
        (self.root / mod.WORKSPACE_FILE).write_text("{ broken JSON", encoding="utf-8")
        self.assertTrue(any("Cannot read JSON" in e for e in self.errors()))

    def test_cli_smoke_and_exit_codes(self):
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["init", "--project", str(self.root), "--target", "base"]), 0)
            (self.root / "engine").mkdir()
            self.assertEqual(mod.main(["base", "register", "--project", str(self.root), "--id", "core",
                                       "--version", "1.0.0", "--code-path", "engine"]), 0)
            self.assertEqual(mod.main(["validate", "--project", str(self.root)]), 0)
            self.assertEqual(mod.main(["status", "--project", str(self.root)]), 0)
            self.assertEqual(mod.main(["run", "--project", str(self.root), "--status", "TARGET_REACHED"]), 2)
            self.assertEqual(mod.main(["game", "create", "--project", str(self.root), "--id", "game-01", "--base", "core"]), 2)
        self.assertIn("RECORD_CHECK_PASSED", out.getvalue())


class ScenarioTest(Fixture):
    def test_a_empty_folder_with_reference_creates_research_and_base(self):
        ws = self.init(target="base", refs=["https://example.com/original-game"])
        self.assertEqual(ws.data["research"][0]["sources"], ["https://example.com/original-game"])
        self.assertTrue((self.root / ".production/research/research-01/MECHANICS_MATRIX.md").is_file())
        (self.root / "engine").mkdir()
        mod.base_register(self.ws(), "core", "1.0.0", "engine", "Core", ["research-01"])
        ws = self.ws()
        self.assertEqual(ws.data["focus"]["base"], "core")
        base = self.read(self.root / ".production/bases/core/BASE.json")
        self.assertEqual(base["versions"][0]["readiness"], "NONE")
        self.assertEqual(base["research_ids"], ["research-01"])
        self.assertEqual(ws.data["games"], [])
        self.assertEqual(self.errors(), [])
        with self.assertRaisesRegex(ValueError, "Cannot claim BASE_READY"):
            mod.base_update(self.ws(), "core", None, "BASE_READY")
        self.set_base_gates("1.0.0", {"B01"})
        mod.base_update(self.ws(), "core", None, "RESEARCH_READY")
        self.assertEqual(mod.base_effective(self.ws(), "core", "1.0.0"), "RESEARCH_READY")

    def test_b_game01_gets_independent_design_and_art_planning_state(self):
        self.init()
        self.register_base()
        messages = mod.game_create(self.ws(), "game-01", "core", title="第一款", brief="塔防，夜色主题")
        self.assertTrue(any("cannot become GAME_READY" in m for m in messages))
        root = self.game_root("game-01")
        for relative in ("design/GAME_DESIGN.md", "design/ART_DIRECTION.md", "design/ART_ASSET_PLAN.md",
                         "design/ANIMATION_SPEC.md", ".production/GATES.json", ".production/ASSETS.json"):
            self.assertTrue((root / relative).is_file(), relative)
        game = self.game_json("game-01")
        self.assertEqual(game["base_binding"], {"base_id": "core", "version": "1.0.0", "history": []})
        self.assertEqual(game["stages"]["G0"], "DONE")
        self.assertEqual(game["stages"]["G1"], "NOT_STARTED")
        self.assertEqual(self.ws().data["focus"]["stage"], "G1")
        self.assertEqual(self.read(self.root / ".production/bases/core/BASE.json")["dependent_games"],
                         [{"game": "game-01", "version": "1.0.0"}])
        self.assertFalse((self.root / "games/game-01/engine").exists(), "Base must not be copied into the game")
        self.assertEqual(self.errors(), [])

    def test_c_game02_on_same_base_does_not_touch_game01(self):
        self.init(target="batch", quota=2)
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        self.fill_design("game-01")
        self.set_game_gates("game-01", {"D01"})
        mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        before = tree_digest(self.game_root("game-01"))
        mod.game_create(self.ws(), "game-02", "core", title="第二款")
        self.assertEqual(tree_digest(self.game_root("game-01")), before)
        self.assertEqual(self.game_json("game-02")["stages"]["G1"], "NOT_STARTED")
        self.assertEqual(self.game_json("game-01")["stages"]["G1"], "DONE")
        self.assertEqual([g["id"] for g in self.ws().data["games"]], ["game-01", "game-02"])
        self.assertEqual(self.errors(), [])
        # Evidence for game-02 may not reach into game-01.
        gates_path = self.game_root("game-02") / ".production/GATES.json"
        gates = self.read(gates_path)
        gates["gates"][0].update(status="PASS", criteria="x", subject_revision="r",
                                 reviewer={"identity": "qa", "independence": "self_review"},
                                 evidence=[{"path": "../game-01/.production/evidence/D01.txt", "sha256": "0" * 64,
                                            "kind": "log", "observed": "borrowed"}])
        self.write(gates_path, gates)
        self.assertTrue(any("not allowed" in e for e in self.errors()))
        gates["gates"][0].update(status="UNVERIFIED", evidence=[])
        self.write(gates_path, gates)
        # A machine record of game-02 pointing at game-01 files is flagged.
        assets_path = self.game_root("game-02") / ".production/ASSETS.json"
        assets = self.read(assets_path)
        assets["notes"] = "copied from games/game-01/assets/hero.png"
        self.write(assets_path, assets)
        self.assertTrue(any("another game's directory" in e for e in self.errors()))
        with self.assertRaisesRegex(ValueError, "overlaps"):
            mod.game_create(self.ws(), "game-03", "core", path="games/game-01/sub", user_request="test overlap")

    def test_d_art_stage_handoff_to_another_agent_restores(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        mod.game_stage(self.ws(), "game-01", "G4", "IN_PROGRESS")
        mod.game_update(self.ws(), "game-01", agent="agent-art", agent_stages=["G4"], next_action="")
        _, problems = mod.handoff_report(self.ws(), "game-01", check=True)
        self.assertTrue(any("next_action is empty" in p for p in problems))
        self.assertTrue(any("blank template" in p for p in problems))
        mod.game_update(self.ws(), "game-01", next_action="G4: produce enemy batch 2 per ART_ASSET_PLAN section 5", task="T-014")
        handoff = self.game_root("game-01") / ".production/HANDOFF.md"
        handoff.write_text("# 交接\n- 当前阶段 G4，由 agent-art 负责敌人第二批。\n", encoding="utf-8")
        mod.set_run_status(self.ws(), "HANDOFF_READY")
        (self.root / ".production/HANDOFF.md").write_text("# 工作区交接\n焦点 game-01 / G4\n", encoding="utf-8")
        report, problems = mod.handoff_report(self.ws(), "game-01", check=True)
        self.assertEqual(problems, [])
        # A new session reads only files and finds the same position.
        fresh = mod.Workspace(self.root)
        status = mod.status_report(fresh, "game-01")
        self.assertIn("G4:IN_PROGRESS", status)
        self.assertIn("agent-art -> G4", status)
        self.assertIn("enemy batch 2", status)
        self.assertIn("Handoff check: COMPLETE", report)

    def test_e_new_device_reprobes_without_overwriting_project_facts(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        device_b = self.base_dir / "device-b checkout"
        shutil.copytree(str(self.root), str(device_b), ignore=shutil.ignore_patterns("local"))
        shared_before = {k: v for k, v in tree_digest(device_b).items() if not k.startswith(".production/local/")}
        env = mod.probe_environment(device_b.resolve(), "device-b")
        shared_after = {k: v for k, v in tree_digest(device_b).items() if not k.startswith(".production/local/")}
        self.assertEqual(shared_before, shared_after)
        self.assertEqual(env["device_label"], "device-b")
        self.assertEqual(Path(env["project_root"]), device_b.resolve())
        self.assertEqual(mod.validate_workspace(device_b)[0], [])
        # A device path leaking into shared records is caught.
        game_path = device_b / "games/game-01/.production/GAME.json"
        game = self.read(game_path)
        game["known_commands"]["build"] = "C:\\Users\\someone\\tools\\build.bat"
        self.write(game_path, game)
        self.assertTrue(any("absolute path" in e for e in mod.validate_workspace(device_b)[0]))

    def test_f_base_bump_flags_dependents_and_requires_regression(self):
        self.init()
        self.register_base()
        self.make_base_ready("1.0.0")
        mod.base_update(self.ws(), "core", "1.0.0", None, freeze=True)
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01", "1.0.0")
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        messages = mod.base_bump(self.ws(), "core", "1.1.0", "add status effects; non-breaking")
        self.assertTrue(any("REGRESSION NEEDED" in m and "game-01" in m for m in messages))
        self.assertIn("REGRESSION NEEDED: game-01 bound to 1.0.0", mod.status_report(self.ws()))
        # Old binding stays valid on the frozen 1.0.0 baseline.
        self.assertEqual(self.errors(), [])
        with self.assertRaisesRegex(ValueError, "verified against base 1.0.0, not 1.1.0"):
            mod.base_update(self.ws(), "core", None, "BASE_READY")
        self.make_base_ready("1.1.0")
        rebind = mod.game_rebind(self.ws(), "game-01", "core@1.1.0")
        self.assertTrue(any("Readiness lowered GAME_READY" in m for m in rebind))
        game = self.game_json("game-01")
        self.assertEqual(game["base_binding"]["history"][0]["version"], "1.0.0")
        self.assertEqual(game["readiness"], "IN_PROGRESS")
        with self.assertRaisesRegex(ValueError, "re-verify"):
            mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        self.set_game_gates("game-01", set(ALL_Q), "1.1.0")
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        self.assertEqual(self.errors(), [])

    def test_g_failed_visual_qa_cannot_be_release_candidate(self):
        self.init()
        self.register_base()
        self.make_base_ready()
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.set_game_gates("game-01", {"R01", "R02"})
        self.record_artifact("game-01")
        self.set_game_gates("game-01", {"Q04"}, status="FAIL")
        with self.assertRaisesRegex(ValueError, "Q04 is FAIL"):
            mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE")
        with self.assertRaisesRegex(ValueError, "G6 cannot be DONE"):
            mod.game_stage(self.ws(), "game-01", "G6", "DONE")
        path = self.game_root("game-01") / ".production/GAME.json"
        game = self.read(path)
        game["readiness"] = "RELEASE_CANDIDATE"
        self.write(path, game)
        self.assertTrue(any("claims RELEASE_CANDIDATE" in e and "Q04" in e for e in self.errors()))
        game["readiness"] = "IN_PROGRESS"
        self.write(path, game)
        self.set_game_gates("game-01", {"Q04"})
        mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE")
        mod.game_stage(self.ws(), "game-01", "G6", "DONE")
        self.assertEqual(self.game_json("game-01")["publication_status"], "NOT_AUTHORIZED")

    def test_h_missing_rights_blocks_publication_approval(self):
        self.init()
        self.register_base()
        self.make_base_ready(commercial=False)
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.set_game_gates("game-01", {"R01", "R02", "R03"})
        self.set_game_gates("game-01", {"R04"}, independence="external_approval")
        self.record_artifact("game-01")
        mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE")
        with self.assertRaisesRegex(ValueError, "lacks commercial code-source clearance"):
            mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        self.set_base_gates("1.0.0", {"B02"})
        mod.base_update(self.ws(), "core", None, "COMMERCIAL_BASE_CANDIDATE")
        self.set_game_gates("game-01", {"Q08"}, status="NOT_APPLICABLE")
        with self.assertRaisesRegex(ValueError, "Q08 must be PASS"):
            mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        self.set_game_gates("game-01", {"Q08"})
        self.set_game_gates("game-01", {"R04"}, independence="self_review")
        with self.assertRaisesRegex(ValueError, "cannot self-approve"):
            mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        with self.assertRaisesRegex(ValueError, "requires PUBLICATION_APPROVED"):
            mod.game_update(self.ws(), "game-01", publication="PUBLISHED")
        self.set_game_gates("game-01", {"R04"}, independence="external_approval")
        mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        self.assertEqual(self.errors(), [])

    def make_v3_workspace(self, root: Path):
        production = root / ".production"
        production.mkdir(parents=True)
        for name in ("PROJECT.json", "STATE.json", "GATES.json"):
            shutil.copy(str(mod.template("v3/" + name)), str(production / name))
        project = self.read(production / "PROJECT.json")
        project.update(project_id="game-legacy123", name="Old Defense")
        project["permissions"]["remote_push"]["allowed"] = True
        self.write(production / "PROJECT.json", project)
        state = self.read(production / "STATE.json")
        state["run"].update(current_stage="S4", status="RUNNING")
        state["next_action"] = "finish enemy sprites batch 3"
        self.write(production / "STATE.json", state)
        gates = self.read(production / "GATES.json")
        self.pass_gate(gates["gates"][0], root, ".production/evidence/source-audit.txt")
        self.write(production / "GATES.json", gates)
        (production / "BACKLOG.md").write_text("| T-007 | S4 | P0 | enemy sprites batch 3 | | ACTIVE |\n", encoding="utf-8")
        (production / "HANDOFF.md").write_text("old handoff facts\n", encoding="utf-8")
        (production / "RIGHTS_LEDGER.md").write_text("old ledger\n", encoding="utf-8")
        skill = root / mod.SKILL_PATH
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text('---\nmetadata:\n  version: "3.0.0"\n---\nold rules\n', encoding="utf-8")
        (skill / "SHA256SUMS.txt").write_text(sha((skill / "SKILL.md").read_bytes()) + "  SKILL.md\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("Team rule A\n\n<!-- GAME_PRODUCTION_V3_BEGIN -->\nold block\n<!-- GAME_PRODUCTION_V3_END -->\n\nTeam rule B\n", encoding="utf-8")
        (root / "src").mkdir()
        (root / "src/main.ts").write_text("export const game = 1;\n", encoding="utf-8")

    def test_i_v3_workspace_migrates_without_losing_tasks_or_evidence(self):
        self.make_v3_workspace(self.root)
        records_before = tree_digest(self.root / ".production")
        source_before = tree_digest(self.root / "src")
        with self.assertRaisesRegex(ValueError, "migrate"):
            mod.init_workspace(self.root)
        messages = mod.migrate_v3(self.root)
        self.assertTrue(any("Archived previous Skill 3.0.0" in m for m in messages))
        records_after = tree_digest(self.root / ".production")
        for path, digest_value in records_before.items():
            self.assertEqual(records_after.get(path), digest_value, path)
        self.assertEqual(tree_digest(self.root / "src"), source_before)
        ws = self.ws()
        self.assertEqual(ws.data["games"], [{"id": "old-defense", "path": ".", "records": ".production", "layout": "v3_legacy"}])
        self.assertEqual(ws.data["focus"]["stage"], "S4")
        self.assertTrue(ws.data["permissions"]["remote_push"]["allowed"])
        self.assertEqual(ws.data["next_action"], "finish enemy sprites batch 3")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Team rule A", agents)
        self.assertIn("Team rule B", agents)
        self.assertNotIn(mod.AGENTS_V3[0], agents)
        self.assertEqual(agents.count(mod.AGENTS_V4[0]), 1)
        self.assertTrue(mod.installed_skill_intact(self.root / mod.SKILL_PATH)[0])
        archived = list((self.root / ".production/archive").rglob("SKILL.md"))
        self.assertEqual(len(archived), 1)
        self.assertIn("old rules", archived[0].read_text(encoding="utf-8"))
        self.assertEqual(self.errors(), [])
        self.assertIn("finish enemy sprites batch 3", mod.status_report(ws))
        # Evidence of the legacy PASS gate is still verified after migration.
        (self.root / ".production/evidence/source-audit.txt").write_text("tampered", encoding="utf-8")
        self.assertTrue(any("mismatch" in e for e in self.errors()))

    def test_i_customized_v3_skill_requires_explicit_archive(self):
        self.make_v3_workspace(self.root)
        (self.root / mod.SKILL_PATH / "LOCAL_RULES.md").write_text("team customization\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "local changes"):
            mod.migrate_v3(self.root)
        self.assertFalse((self.root / mod.WORKSPACE_FILE).exists())
        mod.migrate_v3(self.root, accept_archive=True)
        self.assertTrue(list((self.root / ".production/archive").rglob("LOCAL_RULES.md")))

    def test_j_single_agent_continues_through_stages_until_target(self):
        self.init(target="full_pipeline")
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        with self.assertRaisesRegex(ValueError, "G1 cannot be DONE"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        self.fill_design("game-01")
        self.set_game_gates("game-01", {"D01"})
        messages = mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        self.assertTrue(any("not a stop" in m and "G2" in m for m in messages))
        ws = self.ws()
        self.assertEqual(ws.data["focus"]["stage"], "G2")
        self.assertEqual(ws.run["status"], "RUNNING")
        with self.assertRaisesRegex(ValueError, "Authorized target not reached"):
            mod.set_run_status(self.ws(), "TARGET_REACHED")
        self.make_base_ready()
        self.make_game_ready("game-01")
        self.set_game_gates("game-01", {"R01", "R02"})
        self.record_artifact("game-01")
        for stage in ("G2", "G3", "G4", "G5", "G6"):
            mod.game_stage(self.ws(), "game-01", stage, "DONE")
        mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE",
                        retrospective="Base 1.0.0 used; reusable wave editor; art pilot first saved two batches")
        mod.game_stage(self.ws(), "game-01", "G7", "DONE")
        mod.set_run_status(self.ws(), "TARGET_REACHED")
        self.assertEqual(self.errors(), [])
        self.assertEqual(self.errors(strict=False), [])

    def test_scope_blocks_unrequested_games_and_records_user_request(self):
        self.init(target="base")
        self.register_base()
        with self.assertRaisesRegex(ValueError, "explicit request"):
            mod.game_create(self.ws(), "game-01", "core")
        mod.game_create(self.ws(), "game-01", "core", user_request="基于这个 Base 开始制作第二款游戏，主题为蒸汽朋克")
        scope = self.ws().scope
        self.assertEqual(scope["target"], "game")
        self.assertEqual(scope["games"], ["game-01"])
        self.assertIn("蒸汽朋克", scope["basis"])
        self.assertEqual(self.ws().run["scope_history"][0]["target"], "base")

    def test_batch_of_three_stops_at_quota(self):
        self.init(target="batch", quota=3)
        self.register_base()
        for gid in ("game-01", "game-02", "game-03"):
            mod.game_create(self.ws(), gid, "core")
        with self.assertRaisesRegex(ValueError, "allows 3"):
            mod.game_create(self.ws(), "game-04", "core")
        self.assertIn("batch", mod.status_report(self.ws()))

    def test_stage_and_review_modes_limit_writes(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        mod.set_scope(self.ws(), "full_pipeline", "user: this session only does art", mode="stage", allowed_stages=["G4"])
        self.assertEqual(self.ws().scope["games"], ["game-01"], "same target keeps already scoped games")
        self.assertEqual(self.ws().scope["game_quota"], 1)
        with self.assertRaisesRegex(ValueError, "outside this session"):
            mod.game_stage(self.ws(), "game-01", "G3", "IN_PROGRESS")
        mod.game_stage(self.ws(), "game-01", "G4", "IN_PROGRESS")
        mod.set_scope(self.ws(), "full_pipeline", "user: review only", quota=1, games=["game-01"], mode="review")
        with self.assertRaisesRegex(ValueError, "read-only"):
            mod.game_stage(self.ws(), "game-01", "G4", "DONE")

    def test_design_gate_requires_filled_documents(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        self.set_game_gates("game-01", {"D01"})
        with self.assertRaisesRegex(ValueError, "TEMPLATE_UNFILLED"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        (self.game_root("game-01") / "design/GAME_DESIGN.md").write_text("# 策划\n## 1. 名称\n只有概念名\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lacks sections"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")

    def test_generated_image_is_not_integrated_art(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        path = self.game_root("game-01") / ".production/ASSETS.json"
        assets = self.read(path)
        assets["assets"] = [{"id": "boss", "status": "source_generated", "scope": "game", "provenance": "image tool"}]
        self.write(path, assets)
        self.assertEqual(self.errors(), [])
        assets["assets"][0]["status"] = "integrated"
        self.write(path, assets)
        errors = self.errors()
        self.assertTrue(any("requires runtime_files" in e for e in errors))
        self.assertTrue(any("requires license" in e for e in errors))

    def test_tampered_game_evidence_is_rejected(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        self.set_game_gates("game-01", {"Q01"})
        self.assertEqual(self.errors(), [])
        (self.game_root("game-01") / ".production/evidence/Q01.txt").write_text("changed", encoding="utf-8")
        self.assertTrue(any("mismatch" in e for e in self.errors()))

    def test_pass_without_evidence_or_base_version_fails(self):
        self.init()
        self.register_base()
        mod.game_create(self.ws(), "game-01", "core")
        path = self.game_root("game-01") / ".production/GATES.json"
        gates = self.read(path)
        gates["gates"][2].update(status="PASS", criteria="c", subject_revision="r",
                                 reviewer={"identity": "qa", "independence": "self_review"})
        self.write(path, gates)
        errors = self.errors()
        self.assertTrue(any("requires evidence" in e for e in errors))
        self.assertTrue(any("requires base_version" in e for e in errors))

    def test_deleted_gate_and_na_without_basis_rejected(self):
        self.init()
        self.register_base()
        path = self.base_gates_path()
        gates = self.read(path)
        gates["gates"][1]["status"] = "NOT_APPLICABLE"
        del gates["gates"][-1]
        self.write(path, gates)
        errors = self.errors()
        self.assertTrue(any("scope basis" in e for e in errors))
        self.assertTrue(any("missing gates" in e for e in errors))

    def test_stop_requires_reason(self):
        self.init()
        with self.assertRaisesRegex(ValueError, "truthful"):
            mod.set_run_status(self.ws(), "EXTERNAL_BLOCKED")
        ws = self.ws()
        ws.run["status"] = "RUNTIME_LIMIT"
        ws.save()
        self.assertTrue(any("stop_reason" in e for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
