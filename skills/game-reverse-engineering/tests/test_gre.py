"""Tests of the game-reverse-engineering record tool; not tests of any game, decompiler or art."""
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gre_tool", SKILL_ROOT / "scripts" / "gre.py")
gre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gre)

REPO_ROOT = SKILL_ROOT.parents[1]
V4_SCRIPT = REPO_ROOT / "scripts" / "project.py"
v4 = None
if V4_SCRIPT.is_file():
    v4_spec = importlib.util.spec_from_file_location("game_production_v4", V4_SCRIPT)
    v4 = importlib.util.module_from_spec(v4_spec)
    v4_spec.loader.exec_module(v4)


def tree(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): gre.digest(p) for p in sorted(folder.rglob("*")) if p.is_file()}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.root = self.base_dir / "逆向 工作区"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative, content="fixture\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return relative

    def start(self, refs=("https://example.com/original-2d-game",), target="CREATOR_READY"):
        self.write("engine/core/sim.ts", "export const step = 1;\n")
        gre.init(self.root, "core", "0.1.0", "engine", ["engine/core"], list(refs), "示例", target)
        return self.ctx()

    def ctx(self):
        return gre.Context(self.root)

    def errors(self, **kwargs):
        return gre.validate(self.root, **kwargs)[0]

    def own_engine_reuse(self):
        self.write("engine/LICENSE", "Project-owned engine code. All rights reserved by the user.\n")
        gre.reuse_set(self.ctx(), "engine-own", name="自有引擎", source_kind="own_code", license_="project-owned",
                      decision="KEEP", base_paths=["engine/core"], evidence="engine/LICENSE")
        self.write("qa/re01.md", "reuse review record\n")
        gre.gate_set(self.ctx(), "RE01", "PASS", criteria="all modules decided", reviewer="fixture", subject="rev-1",
                     evidence="qa/re01.md")

    def verify(self, item_id, approach="ADAPT", modules=("engine-own",), visual=False):
        ref = self.write("research/%s-capture.txt" % item_id, "original runtime capture %s\n" % item_id)
        test = self.write("qa/%s-test.log" % item_id, "test passed %s\n" % item_id)
        gre.parity_set(self.ctx(), item_id, original_level="VERIFIED", original_ref=ref, ref_kind="runtime-capture",
                       approach=approach, modules=list(modules) if approach in ("REUSE", "ADAPT") else [],
                       evidence=test, kind="test", observed="behavior matches", reusable=True)
        if visual:
            capture = self.write("qa/%s-frames.png" % item_id, b"frames " + item_id.encode())
            gre.parity_set(self.ctx(), item_id, evidence=capture, kind="measurement", observed="foot drift <= 1px")
        gre.parity_set(self.ctx(), item_id, status="VERIFIED")

    def verify_group(self, group):
        for item in self.ctx().load("PARITY.json")["items"]:
            if gre.DOMAIN_GROUP[item["domain"]] == group:
                self.verify(item["id"], visual=(group == "presentation"))

    def probe(self, pid, seed):
        configs = self.write("probes/%s/config.json" % pid, json.dumps({"theme": seed}))
        assets = "probes/%s/assets" % pid
        self.write(assets + "/hero.png", b"hero-" + seed.encode())
        self.write(assets + "/map.png", b"map-" + seed.encode())
        evidence = {}
        for category in gre.PROBE_CATEGORIES:
            path = self.write("qa/probes/%s-%s.png" % (pid, category), b"%s-%s-%s" % (pid.encode(), category.encode(), seed.encode()))
            evidence[category] = [(path, "runtime-capture")]
        return gre.probe_record(self.ctx(), pid, "原创测试配置 " + seed, [configs], [assets], evidence)

    def make_creator_ready(self):
        self.own_engine_reuse()
        for group in ("logic", "presentation", "creator"):
            self.verify_group(group)
        self.probe("probe-a", "冰原像素风")
        self.probe("probe-b", "沙漠水彩风")


class StartAndTakeoverTest(Fixture):
    def test_empty_folder_start_creates_v4_compatible_workspace(self):
        ctx = self.start()
        workspace = json.loads((self.root / gre.WORKSPACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(workspace["run"]["scope"]["target"], "base")
        self.assertEqual(workspace["run"]["scope"]["game_quota"], 0)
        self.assertEqual(workspace["research"][0]["sources"], ["https://example.com/original-2d-game"])
        self.assertEqual(ctx.current_version(), "0.1.0")
        for name in ("RE_STATE.json", "PARITY.json", "REUSE.json", "PROBES.json", "GATES.json", "TECH_SURVEY.md",
                     "DYNAMIC_STUDY.md", "BASE_HANDOFF.md", "HISTORY.jsonl"):
            self.assertTrue(ctx.path(name).is_file(), name)
        installed = self.root / gre.SKILL_PATH
        expected = {p for p, _ in gre.kit_manifest()} | {"SHA256SUMS.txt"}
        self.assertEqual({p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}, expected)
        self.assertIn("research-private/", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(self.errors(), [])
        self.assertEqual(gre.derive_level(ctx), "NONE")
        if v4:
            self.assertEqual(v4.validate_workspace(self.root)[0], [])

    def test_existing_project_takeover_keeps_code_and_rules(self):
        self.write("AGENTS.md", "Team rule: keep the renderer\n")
        self.write("src/engine/render.ts", "export const render = () => 1;\n")
        self.write("src/game/levels.json", "{}\n")
        before = tree(self.root / "src")
        gre.init(self.root, "core", "1.0.0", ".", ["src/engine"], [], "旧工程")
        self.assertEqual(tree(self.root / "src"), before)
        workspace = json.loads((self.root / gre.WORKSPACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(workspace["intake"]["route"], "adopt_existing")
        agents = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(agents.startswith("Team rule"))
        self.assertEqual(agents.count(gre.AGENTS_MARKERS[0]), 1)
        gre.init(self.root, "core", "1.0.0", ".", ["src/engine"], [], "旧工程")
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8").count(gre.AGENTS_MARKERS[0]), 1)
        self.assertEqual(self.errors(), [])

    def test_v3_workspace_is_refused_with_migration_hint(self):
        self.write(".production/PROJECT.json", "{}\n")
        with self.assertRaisesRegex(ValueError, "migrate"):
            gre.init(self.root, "core", "0.1.0", "engine", ["engine"], [])

    @unittest.skipIf(v4 is None, "game-production v4 script not available next to this Skill")
    def test_v4_project_migration_keeps_v4_records(self):
        self.write("engine/core/sim.ts", "export const step = 1;\n")
        v4.init_workspace(self.root, name="v4 studio", target="full_pipeline")
        ws = v4.Workspace(self.root)
        v4.base_register(ws, "core", "1.0.0", "engine", "Core")
        v4.game_create(v4.Workspace(self.root), "game-01", "core")
        before = {k: v for k, v in tree(self.root).items() if not k.startswith(".production/local/")}
        messages = gre.init(self.root, "core", "9.9.9", "", ["engine/core"], [])
        self.assertTrue(any("Adopting existing Base core@1.0.0" in m for m in messages))
        after = tree(self.root)
        for path, value in before.items():
            if path in ("AGENTS.md", ".gitignore"):
                continue
            self.assertEqual(after.get(path), value, path)
        self.assertTrue((self.root / "AGENTS.md").read_text(encoding="utf-8").count(v4.AGENTS_V4[0]) == 1)
        self.assertEqual(self.ctx().current_version(), "1.0.0")
        self.assertEqual(v4.validate_workspace(self.root)[0], [])
        self.assertEqual(self.errors(), [])

    @unittest.skipIf(not (REPO_ROOT / "templates").is_dir(), "repository templates not available")
    def test_bundled_v4_templates_match_game_production(self):
        for relative in ("WORKSPACE.json", "RIGHTS_LEDGER.md", "BACKLOG.md", "HANDOFF.md", "ENVIRONMENT.local.json",
                         "MECHANICS_MATRIX.md", "base/BASE.json", "base/GATES.json", "base/CAPABILITIES.md"):
            self.assertEqual((SKILL_ROOT / "templates/v4" / relative).read_bytes(),
                             (REPO_ROOT / "templates" / relative).read_bytes(), relative)


class ReuseAndEvidenceTest(Fixture):
    def test_legally_reusable_code_path(self):
        ctx = self.start()
        with self.assertRaisesRegex(ValueError, "license_evidence"):
            gre.reuse_set(ctx, "tween-lib", source_kind="open_source", license_="MIT", decision="KEEP", base_paths=["engine/core"])
        self.write("third_party/tween/LICENSE", "MIT License ...\n")
        gre.reuse_set(self.ctx(), "tween-lib", origin="https://example.com/tween", source_kind="open_source", license_="MIT",
                      decision="KEEP", base_paths=["engine/core"], evidence="third_party/tween/LICENSE")
        self.verify("P2-03", approach="REUSE", modules=("tween-lib",), visual=True)
        item = next(i for i in self.ctx().load("PARITY.json")["items"] if i["id"] == "P2-03")
        self.assertEqual((item["status"], item["approach"]), ("VERIFIED", "REUSE"))
        self.assertEqual(self.errors(), [])

    def test_code_that_cannot_be_legally_reused(self):
        self.start()
        self.write("research-private/decompiled/Player.as", "decompiled\n")
        self.write("research-private/LICENSE-unknown.txt", "no license found\n")
        with self.assertRaisesRegex(ValueError, "rights_basis"):
            gre.reuse_set(self.ctx(), "orig-player", source_kind="original_decompiled", license_="proprietary-unknown-grant",
                          decision="KEEP", base_paths=["engine/core"], evidence="research-private/LICENSE-unknown.txt")
        with self.assertRaisesRegex(ValueError, "overlaps Base core"):
            gre.reuse_set(self.ctx(), "orig-player", source_kind="original_decompiled", decision="QUARANTINE",
                          research_paths=["engine/core/legacy"])
        gre.reuse_set(self.ctx(), "orig-player", source_kind="original_decompiled", decision="QUARANTINE",
                      research_paths=["research-private/decompiled"])
        ref = self.write("research/L2-01-capture.txt", "jump arc capture\n")
        with self.assertRaisesRegex(ValueError, "cannot reuse module orig-player"):
            gre.parity_set(self.ctx(), "L2-01", approach="ADAPT", modules=["orig-player"], original_level="VERIFIED",
                           original_ref=ref, ref_kind="recording", status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L2-01", approach="REIMPLEMENT", modules=[], research_basis=["orig-player"],
                       original_level="VERIFIED", original_ref=ref, ref_kind="recording", status="IMPLEMENTED")
        self.assertEqual(self.errors(), [])

    def test_static_only_evidence_when_original_cannot_run(self):
        self.start()
        static = self.write("research/boss-script-static.txt", "static listing\n")
        with self.assertRaisesRegex(ValueError, "dynamic_gap"):
            gre.parity_set(self.ctx(), "L3-02", original_level="STATIC_ONLY", original_ref=static, approach="REIMPLEMENT",
                           status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L3-02", original_level="STATIC_ONLY", original_ref=static, approach="REIMPLEMENT",
                       gap="player cannot load the SWF; phase timings unconfirmed, tuned by recording later", status="IMPLEMENTED")
        with self.assertRaisesRegex(ValueError, "dynamic evidence"):
            gre.parity_set(self.ctx(), "L3-01", original_level="VERIFIED", original_ref=static, ref_kind="static-analysis",
                           approach="REIMPLEMENT", status="IMPLEMENTED")
        with self.assertRaisesRegex(ValueError, "UNKNOWN"):
            gre.parity_set(self.ctx(), "L4-01", original_level="UNKNOWN", approach="REIMPLEMENT", status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L4-01", original_level="UNKNOWN", approach="IMPROVE",
                       gap="original weapon table unknown; designed independently", status="IMPLEMENTED")
        self.write("research-private/raw-dump.bin", b"local only")
        gre.parity_set(self.ctx(), "L1-01", original_ref="research-private/raw-dump.bin", ref_local=True, ref_kind="trace")
        (self.root / "research-private/raw-dump.bin").unlink()
        errors, warnings = gre.validate(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("local research" in w for w in warnings))
        self.assertIn("Static-only/inferred/proxy originals: 1 L3-02", gre.status_report(self.ctx()))

    def test_history_is_append_only_and_evidence_is_not_overwritten(self):
        self.start()
        self.write("qa/playthrough.json", '{"campaign": "15/15"}')
        first = gre.evidence_add(self.ctx(), "qa/playthrough.json", kind="playthrough")[0]
        self.write("qa/playthrough.json", '{"campaign": "2/15"}')
        second = gre.evidence_add(self.ctx(), "qa/playthrough.json", kind="playthrough")[0]
        self.assertNotEqual(first, second)
        self.assertEqual(len(list(self.ctx().path("evidence").iterdir())), 2)
        self.assertEqual(self.errors(), [])
        stored = self.root / first.split()[1]
        stored.write_text("rewritten", encoding="utf-8")
        self.assertTrue(any("changed after it was recorded" in e for e in self.errors()))
        stored.unlink()
        self.assertTrue(any("must not be deleted" in e for e in self.errors()))

    def test_removed_parity_history_is_detected(self):
        self.start()
        gre.parity_set(self.ctx(), "L1-01", status="RESEARCHING", note="start")
        parity = self.ctx().load("PARITY.json")
        next(i for i in parity["items"] if i["id"] == "L1-01")["history"] = []
        self.ctx().save("PARITY.json", parity)
        self.assertTrue(any("records were removed" in e for e in self.errors()))


class LevelTest(Fixture):
    def test_logic_ready_does_not_pass_presentation(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "RE01"):
            gre.set_level(self.ctx(), "LOGIC_READY")
        self.own_engine_reuse()
        self.verify_group("logic")
        gre.set_level(self.ctx(), "LOGIC_READY")
        self.assertEqual(gre.derive_level(self.ctx()), "LOGIC_READY")
        with self.assertRaisesRegex(ValueError, "Cannot claim PRESENTATION_READY"):
            gre.set_level(self.ctx(), "PRESENTATION_READY")
        gre.parity_set(self.ctx(), "P6-01", status="INTERFACE_ONLY")
        self.assertTrue(any("interface or document is not a finished capability" in p
                            for p in gre.level_problems(self.ctx(), "PRESENTATION_READY", gre.snapshot(self.ctx()))))
        ref = self.write("research/P2-01.txt", "frame capture\n")
        unit = self.write("qa/P2-01-unit.log", "unit ok\n")
        with self.assertRaisesRegex(ValueError, "real asset"):
            gre.parity_set(self.ctx(), "P2-01", original_level="VERIFIED", original_ref=ref, ref_kind="recording",
                           approach="REIMPLEMENT", evidence=unit, kind="test", observed="ok", status="VERIFIED")
        state = self.ctx().load("RE_STATE.json")
        state["claimed_level"] = "PRESENTATION_READY"
        self.ctx().save("RE_STATE.json", state)
        self.assertTrue(any("Claimed PRESENTATION_READY" in e for e in self.errors()))

    def test_presentation_domain_cannot_be_skipped_entirely(self):
        self.start()
        self.own_engine_reuse()
        self.verify_group("logic")
        for item in self.ctx().load("PARITY.json")["items"]:
            if item["domain"] == "P5":
                gre.parity_set(self.ctx(), item["id"], status="NOT_APPLICABLE", approach="OMIT", na_basis="claimed unnecessary")
            elif gre.DOMAIN_GROUP[item["domain"]] == "presentation":
                self.verify(item["id"], visual=True)
        problems = gre.level_problems(self.ctx(), "PRESENTATION_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("domain P5 needs at least one VERIFIED" in p for p in problems))

    def test_creator_ready_needs_two_distinct_probes_on_unchanged_core(self):
        self.start()
        self.own_engine_reuse()
        for group in ("logic", "presentation", "creator"):
            self.verify_group(group)
        gre.set_level(self.ctx(), "PRESENTATION_READY")
        self.probe("probe-a", "冰原像素风")
        with self.assertRaisesRegex(ValueError, "valid: 1"):
            gre.set_level(self.ctx(), "CREATOR_READY")
        shutil.copytree(str(self.root / "probes/probe-a"), str(self.root / "probes/probe-copy"))
        evidence = {c: [("qa/probes/probe-a-%s.png" % c, "runtime-capture")] for c in gre.PROBE_CATEGORIES}
        gre.probe_record(self.ctx(), "probe-copy", "copy", ["probes/probe-copy/config.json"], ["probes/probe-copy/assets"], evidence)
        problems = gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("identical" in p for p in problems))
        probes = self.ctx().load("PROBES.json")
        probes["probes"] = [p for p in probes["probes"] if p["id"] != "probe-copy"]
        self.ctx().save("PROBES.json", probes)
        self.probe("probe-b", "沙漠水彩风")
        gre.set_level(self.ctx(), "CREATOR_READY")
        self.assertEqual(self.errors(strict=True), [])
        # Rewriting the core after the probes invalidates the Creator claim.
        self.write("engine/core/sim.ts", "export const step = 2; // per-theme hack\n")
        self.assertTrue(any("Claimed CREATOR_READY" in e for e in self.errors()))

    def test_rights_are_separate_from_technical_levels(self):
        self.start()
        self.make_creator_ready()
        gre.set_level(self.ctx(), "CREATOR_READY")
        self.assertIn("source review (v4 B02)=UNVERIFIED, commercial permission (RE02)=UNVERIFIED", gre.status_report(self.ctx()))
        self.write("qa/self-approval.md", "agent thinks it is fine\n")
        with self.assertRaisesRegex(ValueError, "external_approval"):
            gre.gate_set(self.ctx(), "RE02", "PASS", criteria="commercial use", reviewer="agent", subject="1.0.0",
                         evidence="qa/self-approval.md")
        self.write("qa/owner-approval.md", "signed approval from the rights holder\n")
        gre.gate_set(self.ctx(), "RE02", "PASS", criteria="commercial use", reviewer="rights holder",
                     independence="external_approval", subject="1.0.0", evidence="qa/owner-approval.md")
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_READY")
        self.assertEqual(self.errors(), [])

    def test_base_version_bump_requires_reverification(self):
        self.start()
        self.own_engine_reuse()
        self.verify_group("logic")
        gre.set_level(self.ctx(), "LOGIC_READY")
        base_path = self.ctx().base_dir / "BASE.json"
        base = json.loads(base_path.read_text(encoding="utf-8"))
        base["versions"].append({"version": "0.2.0", "readiness": "NONE", "frozen": False, "summary": "new core", "created_utc": gre.now_utc()})
        base["current_version"] = "0.2.0"
        base_path.write_bytes(gre.json_bytes(base))
        self.assertEqual(gre.derive_level(self.ctx()), "NONE")
        errors, warnings = gre.validate(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("needs re-verification" in w for w in warnings))
        self.verify_group("logic")
        gre.set_level(self.ctx(), "LOGIC_READY")

    def test_crlf_checkout_still_installs(self):
        kit = self.base_dir / "crlf-kit"
        for relative, _ in gre.kit_manifest() + [("SHA256SUMS.txt", "")]:
            target = kit / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((gre.KIT_ROOT / relative).read_bytes().replace(b"\n", b"\r\n"))
        original = gre.KIT_ROOT
        gre.KIT_ROOT = kit
        try:
            self.start()
        finally:
            gre.KIT_ROOT = original
        self.assertNotIn(b"\r\n", (self.root / gre.SKILL_PATH / "SKILL.md").read_bytes())
        self.assertEqual(self.errors(), [])

    def test_report_is_timestamped_and_kept(self):
        self.start()
        first = gre.write_report(self.ctx())[0]
        second = gre.write_report(self.ctx())[0]
        self.assertNotEqual(first, second)
        self.assertEqual(len(list(self.ctx().path("reports").iterdir())), 2)
        self.assertIn("能力等价矩阵报告", (self.root / first.split(": ")[1]).read_text(encoding="utf-8"))


class AutonomyAndHandoffTest(Fixture):
    def test_interrupted_session_resumes_from_files(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "capability gap"):
            gre.task_start(self.ctx(), "T-01", "research", "read boss scripts")
        gre.task_start(self.ctx(), "T-01", "build", "atlas loader", timeout_min=20)
        gre.checkpoint(self.ctx(), "finish atlas loader then verify P1-01 with a capture", resume_command="npm test")
        state = self.ctx().load("RE_STATE.json")
        state["tasks"][0]["started_utc"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat().replace("+00:00", "Z")
        self.ctx().save("RE_STATE.json", state)
        fresh = gre.Context(self.root)
        report = gre.resume_report(fresh)
        self.assertIn("STALLED: task T-01", report)
        self.assertIn("finish atlas loader", report)
        for _ in range(3):
            gre.task_done(self.ctx(), "T-01", "failed", "loader crashed on empty atlas")
            gre.task_start(self.ctx(), "T-01", "build", "atlas loader retry", timeout_min=20)
        self.assertTrue(any("REPEATED_FAILURE" in m for m in gre.task_done(self.ctx(), "T-01", "failed", "same crash")))

    def test_research_and_polish_spin_guards(self):
        self.start()
        for n in range(6):
            gre.task_start(self.ctx(), "R-%d" % n, "research", "boss %d frames" % n, item="L3-02")
            gre.task_done(self.ctx(), "R-%d" % n, "ok", "notes")
        self.assertTrue(any("RESEARCH_SPIN" in w for w in gre.guard_warnings(self.ctx())))
        for n in range(5):
            gre.task_start(self.ctx(), "J-%d" % n, "polish", "flash tweak %d" % n)
            gre.task_done(self.ctx(), "J-%d" % n, "ok", "tweaked")
        self.assertTrue(any("POLISH_SPIN" in w for w in gre.guard_warnings(self.ctx())))

    def test_handoff_between_different_agents(self):
        self.start()
        gre.assign(self.ctx(), "agent-a", "E0-E4")
        gre.task_start(self.ctx(), "T-02", "build", "state machine")
        problems = gre.handoff_check(self.ctx())
        self.assertTrue(any("blank template" in p for p in problems))
        self.assertTrue(any("ACTIVE" in p for p in problems))
        gre.task_done(self.ctx(), "T-02", "blocked", "needs animation clip spec; see qa/notes.md")
        gre.checkpoint(self.ctx(), "agent-b: implement P3-01 transitions from DYNAMIC_STUDY section 4")
        handoff = self.ctx().path("BASE_HANDOFF.md")
        handoff.write_text("# Base 交接\n- 当前等级 NONE；下一步 P3-01。\n", encoding="utf-8")
        self.assertEqual(gre.handoff_check(self.ctx()), [])
        gre.assign(gre.Context(self.root), "agent-b", "E5")
        status = gre.status_report(self.ctx())
        self.assertIn("Assignment: agent-b", status)
        self.assertIn("implement P3-01", status)
        events = [e["event"] for e in self.ctx().history()]
        self.assertEqual(events.count("assign"), 2)

    def test_cli_smoke(self):
        self.write("engine/core/a.ts", "1\n")
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(gre.main(["init", "--project", str(self.root), "--code-path", "engine", "--core-path", "engine/core",
                                       "--reference", "https://example.com/g"]), 0)
            self.assertEqual(gre.main(["validate", "--project", str(self.root)]), 0)
            self.assertEqual(gre.main(["status", "--project", str(self.root)]), 0)
            self.assertEqual(gre.main(["level", "--project", str(self.root), "--set", "LOGIC_READY"]), 2)
            self.assertEqual(gre.main(["handoff", "--project", str(self.root)]), 1)
            self.assertEqual(gre.main(["parity", "set", "--project", str(self.root), "--item", "L1-01", "--status", "RESEARCHING"]), 0)
        self.assertIn("RECORD_CHECK_PASSED", out.getvalue())


if __name__ == "__main__":
    unittest.main()
