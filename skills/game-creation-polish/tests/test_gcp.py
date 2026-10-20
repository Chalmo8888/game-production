"""Tests of game-creation-polish bookkeeping and the creator handoff contract; not tests of any game or art quality."""
import hashlib
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "gcp.py"
spec = importlib.util.spec_from_file_location("game_creation_polish", MODULE)
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
        self.stamp = 0

    def tearDown(self):
        self.tmp.cleanup()

    # ---- workspace delivered by game-reverse-engineering (built here without it)
    def make_workspace(self, target="full_pipeline", quota=1, versions=("1.0.0",)):
        production = self.root / ".production"
        records = production / "bases/core"
        records.mkdir(parents=True)
        workspace = {
            "schema_version": "3.0", "kit_version": "workspace-3", "workspace_id": "ws-fixture", "name": "示例工作区",
            "layout": {"games_dir": "games", "base_records_dir": ".production/bases", "research_records_dir": ".production/research"},
            "intake": {"status": "DONE", "route": "new_research", "notes": ""},
            "research": [], "bases": [{"id": "core", "records": ".production/bases/core"}], "games": [],
            "focus": {"research": "", "base": "core", "game": "", "stage": "G0", "task": ""},
            "run": {"mode": "auto", "allowed_stages": ["R0", "R1", "R2"] + mod.GAME_STAGES, "status": "NEW", "stop_reason": "",
                    "active_session": "",
                    "scope": {"target": target, "required_readiness": "RELEASE_CANDIDATE", "game_quota": quota, "games": [],
                              "basis": "fixture: user asked for this scope"},
                    "scope_history": []},
            "permissions": {"project_local_changes": True, "remote_push": {"allowed": False, "repository": "", "branches": []}},
            "last_checkpoint_utc": "", "next_action": "G0: create the first game on core", "notes": []}
        self.write(production / "WORKSPACE.json", workspace)
        base = {"schema_version": "3.0", "base_id": "core", "name": "Core", "code_path": "engine", "current_version": versions[-1],
                "versions": [{"version": v, "readiness": "NONE", "frozen": False} for v in versions], "dependent_games": []}
        self.write(records / "BASE.json", base)
        (production / "BACKLOG.md").write_text("# Backlog\n", encoding="utf-8")
        (production / "HANDOFF.md").write_bytes(mod.template("workspace/HANDOFF.md").read_bytes())
        (production / "RIGHTS_LEDGER.md").write_bytes(mod.template("workspace/RIGHTS_LEDGER.md").read_bytes())
        for relative, content in (("engine/core/rules.js", "export const rules = 1;\n"),
                                  ("engine/starter/pack.json", '{"id": "starter"}\n'),
                                  ("docs/START_HERE.md", "# Start here\n"),
                                  ("docs/SCENE_GEOMETRY.md", "# Scene geometry contract\n"),
                                  (".production/bases/core/re/BASE_HANDOFF.md", "# Base handoff\n")):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return mod.Workspace(self.root)

    def export(self, version="1.0.0", level="CREATOR_CANDIDATE", re01="PASS", re03="NOT_APPLICABLE", **override):
        """Write a creator handoff exactly as `gre.py export` lays it out."""
        files = []
        for relative, item in (("docs/START_HERE.md", "start_here"), ("docs/SCENE_GEOMETRY.md", "scene_geometry_contract"),
                               (".production/bases/core/re/BASE_HANDOFF.md", "base_handoff")):
            files.append({"path": relative, "sha256": mod.digest(self.root / relative), "kit_item": item})
        contract = {"schema_version": "creator-handoff-1", "producer": "game-reverse-engineering fixture", "created_utc": "2026-01-01T00:00:00Z",
                    "base_id": "core", "base_version": version, "level": level, "git_head": "fixture",
                    "core_paths": ["engine/core"], "core_fingerprint": mod.core_fingerprint(self.root, ["engine/core"]),
                    "starter_paths": ["engine/starter"], "fidelity": {"mechanism": "fixture", "visual": "fixture"},
                    "rights": {"RE01": re01, "RE02": "UNVERIFIED", "RE03": re03, "note": "fixture"},
                    "first_use": {"passed": True, "commit": "fixture"},
                    "independent_reuse": {"status": "PASS" if level == "CREATOR_READY" else "NOT_RUN", "agent": ""},
                    "open_gaps": [], "files": files}
        contract.update(override)
        self.stamp += 1
        path = self.root / ".production/bases/core/handoff" / version / ("20260101T0000%02dZ-CREATOR_HANDOFF.json" % self.stamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write(path, contract)
        return path

    def ws(self):
        return mod.Workspace(self.root)

    def read(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    def write(self, path: Path, obj):
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def ready_game(self, gid="game-01"):
        self.make_workspace()
        self.export()
        mod.game_create(self.ws(), gid, "core")
        self.make_game_ready(gid)


class InstallAndSafetyTest(Fixture):
    def test_init_installs_exact_manifest_and_never_creates_base_records(self):
        self.make_workspace()
        base_records = tree_digest(self.root / ".production/bases")
        mod.init_creation(self.root)
        installed = self.root / mod.SKILL_PATH
        expected = {path for path, _ in mod.kit_manifest()} | {"SHA256SUMS.txt"}
        self.assertEqual({p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}, expected)
        self.assertEqual(tree_digest(self.root / ".production/bases"), base_records)
        self.assertIn(".production/local/", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertTrue((self.root / ".production/local/ENVIRONMENT.json").is_file())
        mod.init_creation(self.root)
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8").count(mod.AGENTS_MARKERS[0]), 1)

    def test_init_requires_a_delivered_base(self):
        self.root.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "game-creation-polish starts from a Base"):
            mod.init_creation(self.root)
        self.assertFalse((self.root / mod.SKILL_PATH).exists())
        self.make_workspace()
        ws = self.ws()
        ws.data["bases"] = []
        ws.save()
        with self.assertRaisesRegex(ValueError, "no Base"):
            mod.init_creation(self.root)

    def test_init_reports_handoff_state_without_writing_it(self):
        self.make_workspace()
        messages = mod.init_creation(self.root)
        self.assertTrue(any("no creator handoff export" in m for m in messages))
        self.assertFalse((self.root / ".production/bases/core/handoff").exists())

    def test_crlf_checkout_of_skill_still_installs_as_lf(self):
        kit = self.base_dir / "crlf-kit"
        for relative, _ in mod.kit_manifest() + [("SHA256SUMS.txt", "")]:
            target = kit / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((mod.KIT_ROOT / relative).read_bytes().replace(b"\n", b"\r\n"))
        self.make_workspace()
        original = mod.KIT_ROOT
        mod.KIT_ROOT = kit
        try:
            mod.init_creation(self.root)
        finally:
            mod.KIT_ROOT = original
        self.assertNotIn(b"\r\n", (self.root / mod.SKILL_PATH / "SKILL.md").read_bytes())

    def test_different_installed_skill_refused(self):
        self.make_workspace()
        mod.init_creation(self.root)
        target = self.root / mod.SKILL_PATH / "SKILL.md"
        target.write_text("custom local skill\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "differs"):
            mod.init_creation(self.root)
        self.assertEqual(target.read_text(encoding="utf-8"), "custom local skill\n")

    def test_existing_agents_rules_retained(self):
        self.make_workspace()
        (self.root / "AGENTS.md").write_text("User rule: do not edit core\n", encoding="utf-8")
        mod.init_creation(self.root)
        self.assertTrue((self.root / "AGENTS.md").read_text(encoding="utf-8").startswith("User rule"))

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
        self.make_workspace()
        (self.root / mod.WORKSPACE_FILE).write_text("{ broken JSON", encoding="utf-8")
        self.assertTrue(any("Cannot read JSON" in e for e in self.errors()))

    def test_cli_smoke_and_exit_codes(self):
        self.make_workspace(target="base", quota=0)
        self.export()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["init", "--project", str(self.root)]), 0)
            self.assertEqual(mod.main(["validate", "--project", str(self.root)]), 0)
            self.assertEqual(mod.main(["status", "--project", str(self.root)]), 0)
            self.assertEqual(mod.main(["run", "--project", str(self.root), "--status", "TARGET_REACHED"]), 2)
            self.assertEqual(mod.main(["game", "create", "--project", str(self.root), "--id", "game-01"]), 2)
            self.assertEqual(mod.main(["game", "create", "--project", str(self.root), "--id", "game-01", "--base", "core"]), 2)
            self.assertEqual(mod.main(["game", "create", "--project", str(self.root), "--id", "game-01", "--base", "core",
                                       "--user-request", "做第一款游戏"]), 0)
            self.assertEqual(mod.main(["handoff", "--project", str(self.root), "--game", "game-01", "--check"]), 1)
        self.assertIn("RECORD_CHECK_PASSED", out.getvalue())
        self.assertIn("handoff level=CREATOR_CANDIDATE", out.getvalue())


class HandoffContractTest(Fixture):
    def assert_not_ready(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            mod.game_update(self.ws(), "game-01", readiness="GAME_READY")

    def test_missing_handoff_allows_design_but_blocks_game_ready(self):
        self.make_workspace()
        messages = mod.game_create(self.ws(), "game-01", "core")
        self.assertTrue(any("no creator handoff export" in m and "G1/G2" in m for m in messages))
        self.make_game_ready("game-01")
        mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        self.assert_not_ready("no creator handoff export")
        self.assertTrue(any("no creator handoff export" in w for w in mod.validate_workspace(self.root)[1]))

    def test_level_below_creator_candidate_blocks_game_ready(self):
        self.make_workspace()
        self.export(level="PRESENTATION_READY")
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.assert_not_ready("PRESENTATION_READY; game production needs CREATOR_CANDIDATE")
        self.export(level="CREATOR_CANDIDATE")
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        self.assertEqual(self.errors(), [])

    def test_latest_export_wins(self):
        self.make_workspace()
        self.export(level="CREATOR_READY")
        self.export(level="LOGIC_READY")
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.assert_not_ready("LOGIC_READY")

    def test_changed_kit_file_invalidates_handoff(self):
        self.ready_game()
        (self.root / "docs/SCENE_GEOMETRY.md").write_text("# edited by a game agent\n", encoding="utf-8")
        self.assert_not_ready("changed or are missing.*SCENE_GEOMETRY")

    def test_changed_base_core_invalidates_handoff(self):
        self.ready_game()
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        (self.root / "engine/core/rules.js").write_text("export const rules = 2; // game hack\n", encoding="utf-8")
        self.assertTrue(any("claims GAME_READY" in e and "core" in e for e in self.errors()))
        (self.root / "engine/core/rules.js").write_text("export const rules = 1;\n", encoding="utf-8")
        (self.root / "engine/core/extra.js").write_text("export const added = 1;\n", encoding="utf-8")
        self.assertTrue(any("differs from the exported fingerprint" in w for w in mod.validate_workspace(self.root)[1]))

    def test_wrong_schema_or_version_rejected(self):
        self.make_workspace()
        self.export(schema_version="creator-handoff-0")
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.assert_not_ready("unsupported schema")
        self.export(base_version="9.9.9")
        self.assert_not_ready("is for core@9.9.9")
        self.export(core_paths=[])
        self.assert_not_ready("missing core_paths")

    def test_handoff_file_paths_cannot_escape(self):
        self.make_workspace()
        self.export(files=[{"path": "../outside.md", "sha256": "0" * 64}])
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.assert_not_ready("changed or are missing")

    def test_status_shows_level_fidelity_and_reuse(self):
        self.ready_game()
        status = mod.status_report(self.ws())
        self.assertIn("handoff level=CREATOR_CANDIDATE", status)
        self.assertIn("fidelity: mechanism fixture | visual fixture", status)
        self.assertIn("independent reuse: NOT_RUN", status)

    def test_core_fingerprint_is_path_and_content_sensitive(self):
        self.make_workspace()
        before = mod.core_fingerprint(self.root, ["engine/core"])
        (self.root / "engine/core/rules.js").rename(self.root / "engine/core/renamed.js")
        self.assertNotEqual(mod.core_fingerprint(self.root, ["engine/core"]), before)
        cache = self.root / "engine/core/node_modules/x.js"
        after = mod.core_fingerprint(self.root, ["engine/core"])
        cache.parent.mkdir(parents=True)
        cache.write_text("cache\n", encoding="utf-8")
        self.assertEqual(mod.core_fingerprint(self.root, ["engine/core"]), after)


class ScenarioTest(Fixture):
    def test_b_game01_gets_independent_design_and_art_planning_state(self):
        self.make_workspace()
        self.export()
        mod.game_create(self.ws(), "game-01", "core", title="第一款", brief="夜色主题")
        root = self.game_root("game-01")
        for relative in ("design/GAME_DESIGN.md", "design/ART_DIRECTION.md", "design/ART_ASSET_PLAN.md",
                         "design/ANIMATION_SPEC.md", ".production/GATES.json", ".production/ASSETS.json"):
            self.assertTrue((root / relative).is_file(), relative)
        game = self.game_json("game-01")
        self.assertEqual(game["base_binding"], {"base_id": "core", "version": "1.0.0", "history": []})
        self.assertEqual(game["stages"]["G0"], "DONE")
        self.assertEqual(self.ws().data["focus"]["stage"], "G1")
        self.assertEqual(self.read(self.root / ".production/bases/core/BASE.json")["dependent_games"],
                         [{"game": "game-01", "version": "1.0.0"}])
        self.assertFalse((root / "engine").exists(), "Base must not be copied into the game")
        self.assertEqual(self.errors(), [])

    def test_c_game02_on_same_base_does_not_touch_game01(self):
        self.make_workspace(target="batch", quota=2)
        self.export()
        mod.game_create(self.ws(), "game-01", "core")
        self.fill_design("game-01")
        self.set_game_gates("game-01", {"D01"})
        mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        before = tree_digest(self.game_root("game-01"))
        mod.game_create(self.ws(), "game-02", "core", title="第二款")
        self.assertEqual(tree_digest(self.game_root("game-01")), before)
        self.assertEqual(self.game_json("game-02")["stages"]["G1"], "NOT_STARTED")
        self.assertEqual(self.errors(), [])
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
        assets_path = self.game_root("game-02") / ".production/ASSETS.json"
        assets = self.read(assets_path)
        assets["notes"] = "copied from games/game-01/assets/hero.png"
        self.write(assets_path, assets)
        self.assertTrue(any("another game's directory" in e for e in self.errors()))
        with self.assertRaisesRegex(ValueError, "overlaps"):
            mod.game_create(self.ws(), "game-03", "core", path="games/game-01/sub", user_request="test overlap")

    def test_d_art_stage_handoff_to_another_agent_restores(self):
        self.make_workspace()
        self.export()
        mod.game_create(self.ws(), "game-01", "core")
        mod.game_stage(self.ws(), "game-01", "G4", "IN_PROGRESS")
        mod.game_update(self.ws(), "game-01", agent="agent-art", agent_stages=["G4"], next_action="")
        _, problems = mod.handoff_report(self.ws(), "game-01", check=True)
        self.assertTrue(any("next_action is empty" in p for p in problems))
        self.assertTrue(any("blank template" in p for p in problems))
        mod.game_update(self.ws(), "game-01", next_action="G4: produce enemy batch 2 per ART_ASSET_PLAN section 5", task="T-014")
        (self.game_root("game-01") / ".production/HANDOFF.md").write_text("# 交接\n- 当前阶段 G4，由 agent-art 负责。\n", encoding="utf-8")
        mod.set_run_status(self.ws(), "HANDOFF_READY")
        (self.root / ".production/HANDOFF.md").write_text("# 工作区交接\n焦点 game-01 / G4\n", encoding="utf-8")
        report, problems = mod.handoff_report(self.ws(), "game-01", check=True)
        self.assertEqual(problems, [])
        status = mod.status_report(mod.Workspace(self.root), "game-01")
        self.assertIn("G4:IN_PROGRESS", status)
        self.assertIn("agent-art -> G4", status)
        self.assertIn("Handoff check: COMPLETE", report)

    def test_e_new_device_reprobes_without_overwriting_project_facts(self):
        self.make_workspace()
        self.export()
        mod.game_create(self.ws(), "game-01", "core")
        device_b = self.base_dir / "device-b checkout"
        shutil.copytree(str(self.root), str(device_b), ignore=shutil.ignore_patterns("local"))
        shared_before = {k: v for k, v in tree_digest(device_b).items() if not k.startswith(".production/local/")}
        env = mod.probe_environment(device_b.resolve(), "device-b")
        shared_after = {k: v for k, v in tree_digest(device_b).items() if not k.startswith(".production/local/")}
        self.assertEqual(shared_before, shared_after)
        self.assertEqual(env["device_label"], "device-b")
        self.assertEqual(mod.validate_workspace(device_b)[0], [])
        self.assertEqual(mod.handoff_problems(mod.Workspace(device_b), "core", "1.0.0"), [], "handoff survives a move to another device")
        game_path = device_b / "games/game-01/.production/GAME.json"
        game = self.read(game_path)
        for leaked in ("C:\\Users\\someone\\tools\\build.bat", "/Users/someone/build.sh", "/home/ci/build.sh"):
            game["known_commands"]["build"] = leaked
            self.write(game_path, game)
            self.assertTrue(any("absolute path" in e for e in mod.validate_workspace(device_b)[0]), leaked)

    def test_f_new_base_version_requires_new_handoff_and_regression(self):
        self.ready_game()
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        base_path = self.root / ".production/bases/core/BASE.json"
        base = self.read(base_path)
        base["versions"].append({"version": "1.1.0", "readiness": "NONE", "frozen": False})
        base["current_version"] = "1.1.0"
        self.write(base_path, base)
        self.assertIn("REGRESSION NEEDED: game-01 bound to 1.0.0", mod.status_report(self.ws()))
        self.assertEqual(self.errors(), [], "old binding stays valid")
        rebind = mod.game_rebind(self.ws(), "game-01", "core@1.1.0")
        self.assertTrue(any("Readiness lowered GAME_READY" in m for m in rebind))
        self.assertEqual(self.game_json("game-01")["base_binding"]["history"][0]["version"], "1.0.0")
        self.set_game_gates("game-01", set(ALL_Q), "1.1.0")
        with self.assertRaisesRegex(ValueError, "core@1.1.0 has no creator handoff"):
            mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        self.export(version="1.1.0")
        mod.game_update(self.ws(), "game-01", readiness="GAME_READY")
        self.assertEqual(self.errors(), [])

    def test_g_failed_visual_qa_cannot_be_release_candidate(self):
        self.ready_game()
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

    def test_h_base_rights_in_handoff_gate_publication(self):
        self.make_workspace()
        self.export(re01="UNVERIFIED", re03="UNVERIFIED")
        mod.game_create(self.ws(), "game-01", "core")
        self.make_game_ready("game-01")
        self.set_game_gates("game-01", {"R01", "R02", "R03"})
        self.set_game_gates("game-01", {"R04"}, independence="external_approval")
        self.record_artifact("game-01")
        mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE")
        with self.assertRaisesRegex(ValueError, "Base rights are incomplete.*RE01=UNVERIFIED"):
            mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        self.export(re01="PASS", re03="FAIL")
        with self.assertRaisesRegex(ValueError, "RE03=FAIL"):
            mod.game_update(self.ws(), "game-01", readiness="PUBLICATION_APPROVED")
        self.export(re01="PASS", re03="NOT_APPLICABLE")
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

    def test_j_single_agent_continues_through_stages_until_target(self):
        self.make_workspace(target="full_pipeline")
        self.export()
        mod.game_create(self.ws(), "game-01", "core")
        with self.assertRaisesRegex(ValueError, "G1 cannot be DONE"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        self.fill_design("game-01")
        self.set_game_gates("game-01", {"D01"})
        messages = mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        self.assertTrue(any("not a stop" in m and "G2" in m for m in messages))
        with self.assertRaisesRegex(ValueError, "Authorized target not reached"):
            mod.set_run_status(self.ws(), "TARGET_REACHED")
        self.make_game_ready("game-01")
        self.set_game_gates("game-01", {"R01", "R02"})
        self.record_artifact("game-01")
        for stage in ("G2", "G3", "G4", "G5", "G6"):
            mod.game_stage(self.ws(), "game-01", stage, "DONE")
        mod.game_update(self.ws(), "game-01", readiness="RELEASE_CANDIDATE",
                        retrospective="Base 1.0.0 used; art pilot first saved two batches")
        mod.game_stage(self.ws(), "game-01", "G7", "DONE")
        mod.set_run_status(self.ws(), "TARGET_REACHED")
        self.assertEqual(self.errors(), [])

    def test_research_or_base_target_is_not_game_work(self):
        self.make_workspace(target="base", quota=0)
        self.export(level="CREATOR_READY")
        with self.assertRaisesRegex(ValueError, "owned by game-reverse-engineering"):
            mod.set_run_status(self.ws(), "TARGET_REACHED")

    def test_scope_blocks_unrequested_games_and_records_user_request(self):
        self.make_workspace(target="base", quota=0)
        self.export()
        with self.assertRaisesRegex(ValueError, "explicit request"):
            mod.game_create(self.ws(), "game-01", "core")
        mod.game_create(self.ws(), "game-01", "core", user_request="基于这个 Base 开始制作第二款游戏，主题为蒸汽朋克")
        scope = self.ws().scope
        self.assertEqual(scope["target"], "game")
        self.assertEqual(scope["games"], ["game-01"])
        self.assertIn("蒸汽朋克", scope["basis"])
        self.assertEqual(self.ws().run["scope_history"][0]["target"], "base")

    def test_batch_of_three_stops_at_quota(self):
        self.make_workspace(target="batch", quota=3)
        self.export()
        for gid in ("game-01", "game-02", "game-03"):
            mod.game_create(self.ws(), gid, "core")
        with self.assertRaisesRegex(ValueError, "allows 3"):
            mod.game_create(self.ws(), "game-04", "core")

    def test_stage_and_review_modes_limit_writes(self):
        self.make_workspace()
        self.export()
        mod.game_create(self.ws(), "game-01", "core")
        mod.set_scope(self.ws(), "full_pipeline", "user: this session only does art", mode="stage", allowed_stages=["G4"])
        with self.assertRaisesRegex(ValueError, "outside this session"):
            mod.game_stage(self.ws(), "game-01", "G3", "IN_PROGRESS")
        mod.game_stage(self.ws(), "game-01", "G4", "IN_PROGRESS")
        mod.set_scope(self.ws(), "full_pipeline", "user: review only", quota=1, games=["game-01"], mode="review")
        with self.assertRaisesRegex(ValueError, "read-only"):
            mod.game_stage(self.ws(), "game-01", "G4", "DONE")

    def test_design_gate_requires_filled_documents(self):
        self.make_workspace()
        mod.game_create(self.ws(), "game-01", "core")
        self.set_game_gates("game-01", {"D01"})
        with self.assertRaisesRegex(ValueError, "TEMPLATE_UNFILLED"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")
        (self.game_root("game-01") / "design/GAME_DESIGN.md").write_text("# 策划\n## 1. 名称\n只有概念名\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lacks sections"):
            mod.game_stage(self.ws(), "game-01", "G1", "DONE")

    def test_generated_image_is_not_integrated_art(self):
        self.make_workspace()
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
        self.make_workspace()
        mod.game_create(self.ws(), "game-01", "core")
        self.set_game_gates("game-01", {"Q01"})
        self.assertEqual(self.errors(), [])
        (self.game_root("game-01") / ".production/evidence/Q01.txt").write_text("changed", encoding="utf-8")
        self.assertTrue(any("mismatch" in e for e in self.errors()))

    def test_pass_without_evidence_or_base_version_fails(self):
        self.make_workspace()
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
        self.make_workspace()
        mod.game_create(self.ws(), "game-01", "core")
        path = self.game_root("game-01") / ".production/GATES.json"
        gates = self.read(path)
        gates["gates"][1]["status"] = "NOT_APPLICABLE"
        del gates["gates"][-1]
        self.write(path, gates)
        errors = self.errors()
        self.assertTrue(any("scope basis" in e for e in errors))
        self.assertTrue(any("missing gates" in e for e in errors))

    def test_retired_v3_game_entry_is_reported_not_managed(self):
        self.make_workspace()
        ws = self.ws()
        ws.data["games"].append({"id": "old-game", "path": ".", "records": ".production", "layout": "v3_legacy"})
        ws.save()
        self.assertTrue(any("retired v3 records" in w for w in mod.validate_workspace(self.root)[1]))
        with self.assertRaisesRegex(ValueError, "does not manage v3"):
            mod.game_update(self.ws(), "old-game", readiness="GAME_READY")

    def test_stop_requires_reason(self):
        self.make_workspace()
        with self.assertRaisesRegex(ValueError, "truthful"):
            mod.set_run_status(self.ws(), "EXTERNAL_BLOCKED")
        ws = self.ws()
        ws.run["status"] = "RUNTIME_LIMIT"
        ws.save()
        self.assertTrue(any("stop_reason" in e for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
