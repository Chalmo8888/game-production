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

VISUALS = ("hero.png", "enemy.png", "map.png", "ui.png", "fx.png")


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

    def discover_all(self):
        for source in gre.DISCOVERY_SOURCES:
            path = self.write("research/discovery-%s.md" % source, "reviewed %s for unique mechanics\n" % source)
            gre.discover(self.ctx(), source, "DONE", evidence=path, observed="no further unique mechanics")

    def verify(self, item_id, approach="ADAPT", modules=("engine-own",), visual=False, cls="PARITY"):
        ref = self.write("research/%s-capture.txt" % item_id, "original runtime capture %s\n" % item_id)
        if visual:
            proof, kind, observed = self.write("qa/%s-frames.png" % item_id, b"frames " + item_id.encode()), "measurement", "foot drift <= 1px"
        else:
            proof, kind, observed = self.write("qa/%s-test.log" % item_id, "test passed %s\n" % item_id), "test", "behavior matches"
        gre.parity_set(self.ctx(), item_id, original_level="VERIFIED", original_ref=ref, ref_kind="runtime-capture",
                       approach=approach, modules=list(modules) if approach in ("REUSE", "ADAPT") else [],
                       evidence=proof, kind=kind, observed=observed, reusable=True, capability_class=cls, status="VERIFIED")

    def verify_group(self, group):
        for item in self.ctx().load("PARITY.json")["items"]:
            if gre.DOMAIN_GROUP[item["domain"]] == group and item.get("scope", "core") != "excluded":
                self.verify(item["id"], visual=(group == "presentation"))

    def logic_ready(self):
        self.own_engine_reuse()
        self.discover_all()
        self.verify_group("logic")

    def study_all(self, level="STATIC_ONLY"):
        for tid in gre.PR_TOPICS:
            ref = self.write("research/%s.txt" % tid, "render code listing %s\n" % tid)
            gre.present_study(self.ctx(), tid, level=level, evidence=ref, kind="source", observed="render path traced in source",
                              gap="not compared frame by frame with the running original", inputs="logic position in tiles",
                              outputs="screen pixels", data_structures="Transform{x,y,sx,sy,rot,pivot,anchor,parent}",
                              constraints="integer pixel snapping", unknowns="none known", reuse="REIMPLEMENT on the Base renderer")

    def px(self, cid, kinds=None, bind=None, **kwargs):
        kinds = kinds or [sorted(gre.PX_CHECKS[cid])[0]]
        evidence = [(self.write("qa/present/%s-%d.png" % (cid, i), ("%s-%s-%d" % (cid, k, i)).encode()), k) for i, k in enumerate(kinds)]
        bind = bind if bind is not None else [self.write("scenes/%s.json" % cid, '{"check": "%s"}' % cid)]
        return gre.present_check(self.ctx(), cid, "PASS", evidence, bind, **kwargs)

    def themes(self):
        for theme in ("a", "b"):
            self.write("themes/%s/art/ground.png" % theme, ("ground-" + theme).encode())
            self.write("themes/%s/ui/panel.png" % theme, ("panel-" + theme).encode())
        return {"before": ["themes/a/art"], "after": ["themes/b/art"], "ui_before": ["themes/a/ui"], "ui_after": ["themes/b/ui"]}

    def present_ready(self, skip=()):
        self.study_all()
        scene_a = self.write("scenes/forest.json", '{"layers": ["bg", "ground", "actors", "fx", "ui"]}')
        scene_b = self.write("scenes/cave.json", '{"layers": ["bg", "actors", "fg", "ui"]}')
        anchors = self.write("scenes/anchors.json", '{"hero": {"pivot": [0.5, 1.0], "muzzle": [12, -20]}}')
        plan = {"PX01": dict(kinds=["runtime-capture"], bind=[scene_a, scene_b]), "PX02": dict(kinds=["measurement"], bind=[anchors]),
                "PX03": dict(kinds=["runtime-capture"]), "PX04": dict(kinds=["recording"]), "PX05": dict(kinds=["trace"]),
                "PX06": dict(kinds=["measurement"], bind=[anchors]),
                "PX07": dict(kinds=["measurement"], swap=self.themes()),
                "PX08": dict(kinds=["measurement", "measurement"], resolutions=["1280x720", "1920x1080"])}
        for cid, args in plan.items():
            if cid not in skip:
                self.px(cid, **args)
        gre.present_compare(self.ctx(), "UNAVAILABLE", [], reason="the original's player stops at the loading bar")

    def probe(self, pid, seed, shared_from=None, share_visuals=0, gameplay=True, loop=True,
              gameplay_items=("L4-01", "C1-01"), loop_input="normal"):
        configs = self.write("probes/%s/config.json" % pid, json.dumps({"theme": seed}))
        rules = self.write("probes/%s/rules.json" % pid, json.dumps({"weapon": "bouncing-" + seed, "waves": len(seed)}))
        assets = "probes/%s/assets" % pid
        for index, name in enumerate(VISUALS):
            if shared_from and index < share_visuals:
                shutil.copy(str(self.root / ("probes/%s/assets/%s" % (shared_from, name))), str(self.root / self.write(assets + "/" + name)))
            else:
                self.write(assets + "/" + name, ("%s-%s" % (name, seed)).encode())
        self.write("common/fonts/pixel.ttf", b"shared open font")
        evidence = {}
        for category in gre.PROBE_CATEGORIES:
            path = self.write("qa/probes/%s-%s.png" % (pid, category), ("%s-%s-%s" % (pid, category, seed)).encode())
            evidence[category] = [(path, "runtime-capture")]
        scene = self.write("probes/%s/scene.json" % pid, json.dumps({"layers": ["bg", "actors", "ui"], "theme": seed}))
        messages = gre.probe_record(self.ctx(), pid, "原创测试配置 " + seed, [configs], [assets], evidence,
                                    shared=["common/fonts"], scenes=[scene])
        if gameplay:
            clip = self.write("qa/probes/%s-gameplay.mp4" % pid, ("gameplay-%s" % seed).encode())
            messages += gre.probe_gameplay(self.ctx(), pid, "弹跳武器与波次节奏 " + seed, list(gameplay_items), [rules], [(clip, "recording")])
        if loop:
            run = self.write("qa/probes/%s-loop.mp4" % pid, ("loop-%s" % seed).encode())
            messages += gre.probe_loop(self.ctx(), pid, ["start", "play", "win", "result", "restart"], loop_input, [(run, "recording")])
        return messages

    def make_creator_ready(self):
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.present_ready()
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
        v4.base_register(v4.Workspace(self.root), "core", "1.0.0", "engine", "Core")
        v4.game_create(v4.Workspace(self.root), "game-01", "core")
        before = {k: v for k, v in tree(self.root).items() if not k.startswith(".production/local/")}
        messages = gre.init(self.root, "core", "9.9.9", "", ["engine/core"], [])
        self.assertTrue(any("Adopting existing Base core@1.0.0" in m for m in messages))
        after = tree(self.root)
        for path, value in before.items():
            if path in ("AGENTS.md", ".gitignore"):
                continue
            self.assertEqual(after.get(path), value, path)
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8").count(v4.AGENTS_V4[0]), 1)
        self.assertEqual(self.ctx().current_version(), "1.0.0")
        self.assertEqual(v4.validate_workspace(self.root)[0], [])
        self.assertEqual(self.errors(), [])

    @unittest.skipIf(not (REPO_ROOT / "templates").is_dir(), "repository templates not available")
    def test_bundled_v4_templates_match_game_production(self):
        for relative in ("WORKSPACE.json", "RIGHTS_LEDGER.md", "BACKLOG.md", "HANDOFF.md", "ENVIRONMENT.local.json",
                         "MECHANICS_MATRIX.md", "base/BASE.json", "base/GATES.json", "base/CAPABILITIES.md"):
            self.assertEqual((SKILL_ROOT / "templates/v4" / relative).read_bytes(),
                             (REPO_ROOT / "templates" / relative).read_bytes(), relative)

    def test_records_from_1_0_0_stay_readable_and_upgrade_is_additive(self):
        self.start()
        self.own_engine_reuse()
        ctx = self.ctx()
        # Rebuild what a 1.0.0 workspace looked like: no discovery, no RE03, no new item fields.
        parity = ctx.load("PARITY.json")
        parity.pop("discovery")
        for item in parity["items"]:
            for key in ("scope", "scope_reason", "origin", "capability_class", "code_paths", "value", "design_note"):
                item.pop(key)
            item["importance"] = "core"
        ctx.save("PARITY.json", parity)
        gates = ctx.load("GATES.json")
        gates["gates"] = [g for g in gates["gates"] if g["id"] != "RE03"]
        ctx.save("GATES.json", gates)
        ctx.path("PRESENTATION.json").unlink()
        state = ctx.load("RE_STATE.json")
        state["guards"] = {"research_streak_limit": 6, "polish_streak_limit": 5, "same_failure_limit": 3}
        state.update(claimed_level="LOGIC_READY", claimed_for_version="0.1.0",
                     level_history=[{"utc": gre.now_utc(), "level": "LOGIC_READY", "base_version": "0.1.0"}])
        ctx.save("RE_STATE.json", state)
        errors, warnings = gre.validate(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("gre.py upgrade" in w for w in warnings))
        self.assertTrue(any("claim made under gre 1.0.0 rules" in w for w in warnings))
        self.assertIn("Base core@0.1.0", gre.status_report(self.ctx()))
        before_items = self.ctx().load("PARITY.json")["items"]
        gre.upgrade(self.ctx())
        after = self.ctx()
        self.assertEqual(after.load("PARITY.json")["items"], before_items)
        self.assertIn("RE03", [g["id"] for g in after.load("GATES.json")["gates"]])
        self.assertTrue(after.path("PRESENTATION.json").is_file())
        self.assertIn("discovery", after.load("PARITY.json"))
        self.assertEqual(after.load("RE_STATE.json")["guards"]["research_budget_per_item"], 3)
        self.assertEqual(self.errors(), [])


class DiscoveryAndClassTest(Fixture):
    def test_game_specific_capability_beyond_the_template(self):
        self.start()
        self.logic_ready()
        gre.set_level(self.ctx(), "LOGIC_READY")
        with self.assertRaisesRegex(ValueError, "--source"):
            gre.parity_add(self.ctx(), "L5-04", "L5", "时间回溯关卡机制")
        self.write("research-private/rewind.txt", "rewind buffer in level script\n")
        gre.parity_add(self.ctx(), "L5-04", "L5", "时间回溯关卡机制", source="code", evidence="research-private/rewind.txt",
                       kind="static-analysis", observed="level script keeps a 5s state ring buffer", local=True)
        gre.discover(self.ctx(), "code", "DONE", evidence=self.write("research/code-review-2.md", "found rewind\n"), findings=["L5-04"])
        problems = gre.level_problems(self.ctx(), "LOGIC_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any(p.startswith("L5-04") for p in problems))
        self.assertTrue(any("Claimed LOGIC_READY" in e for e in self.errors()))
        self.assertIn("discovered (game-specific): 1 L5-04", gre.status_report(self.ctx()))
        self.verify("L5-04")
        gre.set_level(self.ctx(), "LOGIC_READY")
        with self.assertRaisesRegex(ValueError, "UNAVAILABLE needs a reason"):
            gre.discover(self.ctx(), "runtime", "UNAVAILABLE")
        gre.discover(self.ctx(), "runtime", "UNAVAILABLE", reason="player stops at the loading bar; see TECH_SURVEY §3")

    def test_scope_changes_and_exclusions_need_reasons(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "scope_reason"):
            gre.parity_set(self.ctx(), "L6-02", scope="excluded")
        gre.parity_set(self.ctx(), "L6-02", scope="excluded", scope_reason="original online leaderboard; out of the user's offline Base scope")
        with self.assertRaisesRegex(ValueError, "downgraded"):
            gre.parity_set(self.ctx(), "L1-03", scope="legacy")
        gre.parity_set(self.ctx(), "L1-03", scope="legacy", scope_reason="old save-compatible RNG kept only for replays")
        self.logic_ready()
        self.assertEqual(gre.derive_level(self.ctx()), "LOGIC_READY")

    def test_unknown_original_allows_extension_but_never_parity(self):
        self.start()
        self.own_engine_reuse()
        with self.assertRaisesRegex(ValueError, "PARITY needs original evidence"):
            gre.parity_set(self.ctx(), "L4-01", original_level="UNKNOWN", capability_class="PARITY")
        with self.assertRaisesRegex(ValueError, "explicitly marked EXTENSION"):
            gre.parity_set(self.ctx(), "L4-01", original_level="UNKNOWN", approach="REIMPLEMENT", status="IMPLEMENTED")
        inferred = self.write("research/L4-02.txt", "community wiki guess\n")
        with self.assertRaisesRegex(ValueError, "PARITY needs original evidence"):
            gre.parity_set(self.ctx(), "L4-02", original_level="INFERRED", original_ref=inferred, gap="never observed in play",
                           capability_class="PARITY")
        with self.assertRaisesRegex(ValueError, "REPLACEMENT needs differences"):
            gre.parity_set(self.ctx(), "L4-02", original_level="INFERRED", original_ref=inferred, gap="never observed in play",
                           capability_class="REPLACEMENT", approach="REIMPLEMENT", status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L4-02", original_level="INFERRED", original_ref=inferred, gap="never observed in play",
                       capability_class="REPLACEMENT", approach="REIMPLEMENT",
                       differences="uses an open-source tween library instead of the original curve", status="IMPLEMENTED")
        test = self.write("qa/L4-01.log", "weapon table tests\n")
        gre.parity_set(self.ctx(), "L4-01", original_level="UNKNOWN", capability_class="EXTENSION", approach="REIMPLEMENT",
                       design_note="original weapon table is unknown; data-driven weapon schema designed for future games",
                       evidence=test, kind="test", observed="schema loads 12 weapons", reusable=True, status="VERIFIED")
        status = gre.status_report(self.ctx())
        self.assertIn("EXTENSION=1", status)
        self.assertIn("REPLACEMENT=1", status)
        report = self.root / gre.write_report(self.ctx())[0].split(": ")[1]
        self.assertIn("EXTENSION（原创扩展，不是逆向成果）1", report.read_text(encoding="utf-8"))
        self.assertEqual(self.errors(), [])


class ReuseAndEvidenceTest(Fixture):
    def test_legally_reusable_code_path(self):
        ctx = self.start()
        with self.assertRaisesRegex(ValueError, "license_evidence"):
            gre.reuse_set(ctx, "tween-lib", source_kind="open_source", license_="MIT", decision="KEEP", base_paths=["engine/core"])
        self.write("third_party/tween/LICENSE", "MIT License ...\n")
        with self.assertRaisesRegex(ValueError, "execution_note"):
            gre.reuse_set(self.ctx(), "tween-lib", source_kind="open_source", license_="MIT", decision="KEEP",
                          base_paths=["engine/core"], evidence="third_party/tween/LICENSE", execution="reviewed")
        gre.reuse_set(self.ctx(), "tween-lib", origin="https://example.com/tween", source_kind="open_source", license_="MIT",
                      decision="KEEP", base_paths=["engine/core"], evidence="third_party/tween/LICENSE",
                      execution="reviewed", execution_note="no install scripts; npm --ignore-scripts; source read before build")
        self.verify("P2-03", approach="REUSE", modules=("tween-lib",), visual=True)
        item = next(i for i in self.ctx().load("PARITY.json")["items"] if i["id"] == "P2-03")
        self.assertEqual((item["status"], item["approach"], item["capability_class"]), ("VERIFIED", "REUSE", "PARITY"))
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
        with self.assertRaisesRegex(ValueError, "never or sandboxed"):
            gre.reuse_set(self.ctx(), "orig-player", source_kind="original_decompiled", decision="QUARANTINE",
                          research_paths=["research-private/decompiled"], execution="reviewed", execution_note="ran it")
        gre.reuse_set(self.ctx(), "orig-player", source_kind="original_decompiled", decision="QUARANTINE",
                      research_paths=["research-private/decompiled"], execution="sandboxed",
                      execution_note="offline VM without credentials")
        ref = self.write("research/L2-01-capture.txt", "jump arc capture\n")
        with self.assertRaisesRegex(ValueError, "cannot reuse module orig-player"):
            gre.parity_set(self.ctx(), "L2-01", approach="ADAPT", modules=["orig-player"], original_level="VERIFIED",
                           original_ref=ref, ref_kind="recording", status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L2-01", approach="REIMPLEMENT", modules=[], research_basis=["orig-player"],
                       original_level="VERIFIED", original_ref=ref, ref_kind="recording", capability_class="PARITY",
                       status="IMPLEMENTED")
        self.assertEqual(self.errors(), [])

    def test_static_only_evidence_when_original_cannot_run(self):
        self.start()
        static = self.write("research/boss-script-static.txt", "static listing\n")
        with self.assertRaisesRegex(ValueError, "dynamic_gap"):
            gre.parity_set(self.ctx(), "L3-02", original_level="STATIC_ONLY", original_ref=static, approach="REIMPLEMENT",
                           status="IMPLEMENTED")
        gre.parity_set(self.ctx(), "L3-02", original_level="STATIC_ONLY", original_ref=static, approach="REIMPLEMENT",
                       gap="player cannot load the SWF; phase timings unconfirmed, tuned by recording later",
                       capability_class="PARITY", status="IMPLEMENTED")
        with self.assertRaisesRegex(ValueError, "dynamic evidence"):
            gre.parity_set(self.ctx(), "L3-01", original_level="VERIFIED", original_ref=static, ref_kind="static-analysis",
                           approach="REIMPLEMENT", status="IMPLEMENTED")
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
        with self.assertRaisesRegex(ValueError, "discovery"):
            gre.set_level(self.ctx(), "LOGIC_READY")
        self.discover_all()
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
        state["level_history"].append({"utc": gre.now_utc(), "level": "PRESENTATION_READY", "skill_version": gre.SKILL_VERSION})
        self.ctx().save("RE_STATE.json", state)
        self.assertTrue(any("Claimed PRESENTATION_READY" in e for e in self.errors()))

    def test_presentation_domain_cannot_be_skipped_entirely(self):
        self.start()
        self.logic_ready()
        for item in self.ctx().load("PARITY.json")["items"]:
            if item["domain"] == "P5":
                gre.parity_set(self.ctx(), item["id"], status="NOT_APPLICABLE", approach="OMIT", na_basis="claimed unnecessary")
            elif gre.DOMAIN_GROUP[item["domain"]] == "presentation":
                self.verify(item["id"], visual=True)
        problems = gre.level_problems(self.ctx(), "PRESENTATION_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("domain P5 needs at least one VERIFIED" in p for p in problems))

    def test_core_change_invalidates_related_qa(self):
        self.start()
        self.write("engine/core/rules/rules.ts", "export const lives = 3;\n")
        self.logic_ready()
        gre.parity_set(self.ctx(), "L1-01", code_paths=["engine/core/rules"])
        self.verify("L1-01")
        gre.set_level(self.ctx(), "LOGIC_READY")
        self.write("engine/core/sim.ts", "export const step = 2; // physics rewrite\n")
        self.assertEqual(gre.derive_level(self.ctx()), "NONE")
        self.assertTrue(any("Claimed LOGIC_READY" in e for e in self.errors()))
        self.assertIn("stale", gre.status_report(self.ctx()))
        snapshot = gre.snapshot(self.ctx())
        l101 = next(i for i in snapshot["parity"]["items"] if i["id"] == "L1-01")
        l201 = next(i for i in snapshot["parity"]["items"] if i["id"] == "L2-01")
        self.assertIsNone(gre.item_counts(self.ctx(), l101, "0.1.0", snapshot["core"]), "unrelated code change keeps scoped QA valid")
        self.assertTrue(gre.item_counts(self.ctx(), l201, "0.1.0", snapshot["core"]).startswith("stale"))
        self.verify_group("logic")
        gre.set_level(self.ctx(), "LOGIC_READY")

    def test_creator_ready_needs_distinct_visuals_gameplay_and_loop_on_one_core(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.present_ready()
        gre.set_level(self.ctx(), "PRESENTATION_READY")
        self.probe("probe-a", "冰原像素风")
        with self.assertRaisesRegex(ValueError, "valid: 1"):
            gre.set_level(self.ctx(), "CREATOR_READY")
        shutil.copytree(str(self.root / "probes/probe-a"), str(self.root / "probes/probe-copy"))
        evidence = {c: [("qa/probes/probe-a-%s.png" % c, "runtime-capture")] for c in gre.PROBE_CATEGORIES}
        gre.probe_record(self.ctx(), "probe-copy", "copy", ["probes/probe-copy/config.json"], ["probes/probe-copy/assets"], evidence,
                         scenes=["probes/probe-copy/scene.json"])
        gre.probe_gameplay(self.ctx(), "probe-copy", "same", ["L4-01"], ["probes/probe-copy/rules.json"], [("qa/probes/probe-a-gameplay.mp4", "recording")])
        gre.probe_loop(self.ctx(), "probe-copy", gre.LOOP_STEPS, "normal", [("qa/probes/probe-a-loop.mp4", "recording")])
        problems = gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("visual assets are identical" in p for p in problems))
        self.assertTrue(any("gameplay configurations are identical" in p for p in problems))
        self.assertTrue(any("scene configurations are identical" in p for p in problems))
        probes = self.ctx().load("PROBES.json")
        probes["probes"] = [p for p in probes["probes"] if p["id"] != "probe-copy"]
        self.ctx().save("PROBES.json", probes)
        self.probe("probe-b", "沙漠水彩风")
        gre.set_level(self.ctx(), "CREATOR_READY")
        self.assertEqual(self.errors(strict=True), [])
        self.write("engine/core/sim.ts", "export const step = 2; // per-theme hack\n")
        self.assertTrue(any("Claimed CREATOR_READY" in e for e in self.errors()))
        snapshot = gre.snapshot(self.ctx())
        probe_problems, valid = gre.probe_errors(self.ctx(), snapshot["probes"], snapshot)
        self.assertEqual(valid, [], "probes recorded on the old core are no longer valid")
        self.assertTrue(any("core fingerprint differs" in p for p in probe_problems))

    def test_visual_configs_may_share_common_resources_but_not_most_visuals(self):
        self.start()
        self.make_creator_ready()
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_READY")
        probe = next(p for p in self.ctx().load("PROBES.json")["probes"] if p["id"] == "probe-b")
        self.assertEqual(len(probe["shared_files"]), 1, "the common font is shared and allowed")
        self.probe("probe-b", "沙漠水彩风", shared_from="probe-a", share_visuals=1)
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_READY", "20% shared visuals is within the limit")
        self.probe("probe-b", "沙漠水彩风", shared_from="probe-a", share_visuals=2)
        problems = gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("40% of visual assets are identical" in p for p in problems))

    def test_image_swap_without_gameplay_change_is_not_production_capability(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.probe("probe-a", "冰原像素风", gameplay=False)
        self.probe("probe-b", "沙漠水彩风", gameplay=False)
        problems = gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))
        self.assertTrue(any("swapping images alone" in p for p in problems))
        self.assertIn("visual-only (not production evidence): probe-a, probe-b", gre.status_report(self.ctx()))
        messages = self.probe("probe-a", "冰原像素风", gameplay_items=("P1-01",))
        self.assertTrue(any("must change a gameplay mechanic" in m for m in messages))
        messages = self.probe("probe-b", "沙漠水彩风", loop_input="debug")
        self.assertTrue(any("normal input" in m for m in messages))
        with self.assertRaisesRegex(ValueError, "Cannot claim CREATOR_READY"):
            gre.set_level(self.ctx(), "CREATOR_READY")

    def test_probe_content_must_not_come_from_quarantined_research(self):
        self.start()
        gre.reuse_set(self.ctx(), "orig-art", source_kind="original_decompiled", decision="QUARANTINE",
                      research_paths=["probes/ripped"], execution="never")
        self.write("probes/ripped/hero.png", b"original sprite")
        self.write("probes/x/config.json", "{}")
        evidence = {c: [(self.write("qa/x-%s.png" % c, c.encode()), "runtime-capture")] for c in gre.PROBE_CATEGORIES}
        messages = gre.probe_record(self.ctx(), "probe-x", "x", ["probes/x/config.json"], ["probes/ripped"], evidence)
        self.assertTrue(any("quarantined research material" in m for m in messages))

    def test_rights_are_separate_and_user_approval_does_not_replace_rights_holder(self):
        self.start()
        self.make_creator_ready()
        gre.set_level(self.ctx(), "CREATOR_READY")
        status = gre.status_report(self.ctx())
        self.assertIn("original assets/expression rights (RE03)=UNVERIFIED", status)
        self.assertIn("release rights record INCOMPLETE", status)
        self.assertIn("residual rights risk is never zero", status)
        self.write("qa/self-approval.md", "agent thinks it is fine\n")
        with self.assertRaisesRegex(ValueError, "external_approval"):
            gre.gate_set(self.ctx(), "RE02", "PASS", criteria="publish", reviewer="agent", subject="0.1.0",
                         evidence="qa/self-approval.md", role="user")
        self.write("qa/user-approval.md", "user approves public release\n")
        with self.assertRaisesRegex(ValueError, "does not replace the original rights holder"):
            gre.gate_set(self.ctx(), "RE03", "PASS", criteria="original sprites", reviewer="the user",
                         independence="external_approval", subject="0.1.0", evidence="qa/user-approval.md", role="user")
        gre.gate_set(self.ctx(), "RE02", "PASS", criteria="publish", reviewer="the user", independence="external_approval",
                     subject="0.1.0", evidence="qa/user-approval.md", role="user")
        self.assertIn("release rights record INCOMPLETE", gre.status_report(self.ctx()))
        self.write("qa/owner-grant.md", "signed grant from the original rights holder\n")
        gre.gate_set(self.ctx(), "RE03", "PASS", criteria="original sprites", reviewer="rights holder",
                     independence="external_approval", subject="0.1.0", evidence="qa/owner-grant.md", role="rights_holder")
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_READY")
        self.assertIn("code source review (v4 B02)=UNVERIFIED", gre.status_report(self.ctx()))
        self.assertIn("release rights record INCOMPLETE", gre.status_report(self.ctx()))
        self.assertEqual(self.errors(), [])

    def test_base_version_bump_requires_reverification(self):
        self.start()
        self.logic_ready()
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


class PresentationTest(Fixture):
    def presentation_items_ready(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")

    def gate(self):
        return gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))

    def test_asset_import_only_cannot_pass_presentation(self):
        self.presentation_items_ready()
        ref = self.write("research/PR01-only.txt", "camera code\n")
        gre.present_study(self.ctx(), "PR01", level="STATIC_ONLY", evidence=ref, kind="source", observed="camera", gap="not run")
        self.assertTrue(any(p.startswith("PR01: record inputs") for p in self.gate()), "evidence alone is not a finished study")
        self.assertTrue(any("record the dynamic comparison" in p for p in self.gate()))
        self.study_all()
        gre.present_compare(self.ctx(), "UNAVAILABLE", [], reason="original cannot run")
        with self.assertRaisesRegex(ValueError, "Presentation Reconstruction Gate: PX01"):
            gre.set_level(self.ctx(), "PRESENTATION_READY")
        self.assertEqual(gre.candidates(self.ctx())[0]["id"], "presentation-reconstruction")
        self.assertIn("Presentation Reconstruction Gate: FAIL", gre.status_report(self.ctx()))
        self.assertEqual(gre.derive_level(self.ctx()), "LOGIC_READY")

    def test_static_scene_without_animation_and_event_binding_is_not_full_presentation(self):
        self.presentation_items_ready()
        self.present_ready(skip=("PX04", "PX05"))
        problems = self.gate()
        self.assertTrue(any(p.startswith("PX04") for p in problems))
        self.assertTrue(any(p.startswith("PX05") for p in problems))
        messages = self.px("PX05", kinds=["runtime-capture"])
        self.assertTrue(any("needs measurement or trace evidence" in m for m in messages), "a screenshot does not prove event timing")
        self.px("PX04", kinds=["recording"])
        self.px("PX05", kinds=["trace"])
        self.assertEqual(self.gate(), [])
        gre.set_level(self.ctx(), "PRESENTATION_READY")

    def test_single_fixed_screen_is_not_a_configurable_scene_system(self):
        self.presentation_items_ready()
        self.present_ready()
        messages = self.px("PX01", kinds=["runtime-capture"], bind=[self.write("scenes/only.json", "{}")])
        self.assertTrue(any("at least two different scene configurations" in m for m in messages))

    def test_scene_coordinate_or_anchor_change_requires_new_evidence(self):
        self.presentation_items_ready()
        self.present_ready()
        self.assertEqual(self.gate(), [])
        gre.set_level(self.ctx(), "PRESENTATION_READY")
        self.write("scenes/anchors.json", '{"hero": {"pivot": [0.5, 0.9], "muzzle": [12, -20]}}')
        problems = self.gate()
        self.assertTrue(any(p.startswith("PX02") and "anchor files changed" in p for p in problems))
        self.assertTrue(any(p.startswith("PX06") for p in problems))
        self.assertTrue(any("Claimed PRESENTATION_READY" in e for e in self.errors()))
        anchors = "scenes/anchors.json"
        self.px("PX02", kinds=["measurement"], bind=[anchors])
        self.px("PX06", kinds=["measurement"], bind=[anchors])
        self.assertEqual(self.gate(), [])
        history = self.ctx().load("PRESENTATION.json")["experiment"]["checks"]["PX02"]["history"]
        self.assertEqual(len(history), 1, "the earlier PX02 measurement is kept in history")

    def test_new_assets_and_ui_theme_run_without_core_changes(self):
        self.presentation_items_ready()
        self.present_ready()
        self.assertEqual(self.gate(), [])
        same_art = {"before": ["themes/a/art"], "after": ["themes/a/art"], "ui_before": ["themes/a/ui"], "ui_after": ["themes/b/ui"]}
        messages = self.px("PX07", kinds=["measurement"], swap=same_art)
        self.assertTrue(any("record scene assets before and after the swap" in m for m in messages))
        same_ui = {"before": ["themes/a/art"], "after": ["themes/b/art"], "ui_before": ["themes/a/ui"], "ui_after": ["themes/a/ui"]}
        messages = self.px("PX07", kinds=["measurement"], swap=same_ui)
        self.assertTrue(any("record UI theme files before and after the swap" in m for m in messages))
        self.write("engine/core/sim.ts", "export const step = 1; // theme-specific hack\n")
        messages = self.px("PX07", kinds=["measurement"], swap=self.themes())
        self.assertTrue(any("swapping art must not need core edits" in m for m in messages))
        self.assertTrue(any(p.startswith("PX02") and "engine core changed" in p for p in self.gate()))

    def test_screenshots_alone_cannot_establish_engine_architecture(self):
        self.start()
        shot = self.write("research/original-title.png", b"screenshot")
        with self.assertRaisesRegex(ValueError, "screenshots alone support at most INFERRED"):
            gre.present_study(self.ctx(), "PR03", level="VERIFIED", evidence=shot, kind="screenshot", observed="layers visible")
        with self.assertRaisesRegex(ValueError, "screenshots alone support at most INFERRED"):
            gre.present_study(self.ctx(), "PR03", level="STATIC_ONLY", evidence=shot, kind="screenshot", observed="layers visible",
                              gap="not traced")
        gre.present_study(self.ctx(), "PR03", level="INFERRED", evidence=shot, kind="screenshot", observed="layers visible",
                          gap="draw order inferred from two screenshots; not traced in code or at runtime",
                          inputs="?", outputs="frame", data_structures="unknown", constraints="unknown",
                          unknowns="sort key, batching", reuse="REIMPLEMENT with a data-driven layer graph")
        self.assertFalse(any(p.startswith("PRESENTATION PR03") for p in gre.study_problems(self.ctx(), gre.snapshot(self.ctx()))))

    def test_missing_dynamic_evidence_is_reported_not_hidden(self):
        self.presentation_items_ready()
        self.present_ready()
        status = gre.status_report(self.ctx())
        self.assertIn("Presentation Reconstruction Gate: PASS", status)
        self.assertIn("NOT dynamically verified", status)
        report = self.root / gre.write_report(self.ctx())[0].split(": ")[1]
        self.assertIn("NOT dynamically verified", report.read_text(encoding="utf-8"))

    def test_claims_made_before_the_gate_stay_readable(self):
        self.presentation_items_ready()
        state = self.ctx().load("RE_STATE.json")
        state.update(claimed_level="PRESENTATION_READY", claimed_for_version="0.1.0")
        state["level_history"].append({"utc": gre.now_utc(), "level": "PRESENTATION_READY", "skill_version": "1.1.0"})
        self.ctx().save("RE_STATE.json", state)
        self.ctx().path("PRESENTATION.json").unlink()
        errors, warnings = gre.validate(self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("claim made under gre 1.1.0 rules" in w for w in warnings))
        self.assertTrue(any("PRESENTATION.json is missing" in w for w in warnings))
        self.assertEqual(gre.derive_level(self.ctx()), "LOGIC_READY")
        gre.upgrade(self.ctx())
        self.assertTrue(self.ctx().path("PRESENTATION.json").is_file())
        if v4:
            self.assertEqual(v4.validate_workspace(self.root)[0], [])


class AutonomyAndHandoffTest(Fixture):
    def old(self, hours=3):
        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")

    def test_interrupted_session_resumes_from_files(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "capability gap"):
            gre.task_start(self.ctx(), "T-01", "research", "read boss scripts")
        gre.task_start(self.ctx(), "T-01", "build", "atlas loader", timeout_min=20)
        gre.checkpoint(self.ctx(), "finish atlas loader then verify P1-01 with a capture", resume_command="npm test")
        state = self.ctx().load("RE_STATE.json")
        state["tasks"][0]["started_utc"] = self.old()
        self.ctx().save("RE_STATE.json", state)
        report = gre.resume_report(gre.Context(self.root))
        self.assertIn("STALLED: task T-01", report)
        self.assertIn("finish atlas loader", report)
        for _ in range(3):
            gre.task_done(self.ctx(), "T-01", "failed", "loader crashed on empty atlas")
            gre.task_start(self.ctx(), "T-01", "build", "atlas loader retry", timeout_min=20)
        self.assertTrue(any("REPEATED_FAILURE" in m for m in gre.task_done(self.ctx(), "T-01", "failed", "same crash")))

    def test_long_task_timeout_is_recovered_safely(self):
        self.start()
        gre.task_start(self.ctx(), "T-07", "build", "batch atlas export", timeout_min=30, pid="4242", command="python tools/export.py")
        with self.assertRaisesRegex(ValueError, "has not passed its timeout"):
            gre.task_recover(self.ctx(), "T-07", "restart", "looked fine")
        state = self.ctx().load("RE_STATE.json")
        state["tasks"][0]["started_utc"] = self.old(2)
        self.ctx().save("RE_STATE.json", state)
        self.assertTrue(any("STALLED: task T-07" in w for w in gre.guard_warnings(self.ctx())))
        messages = gre.task_recover(self.ctx(), "T-07", "restart", "no output for 90 min; stopped pid 4242 only", timeout_min=15)
        self.assertTrue(any("pid 4242" in m for m in messages))
        task = self.ctx().load("RE_STATE.json")["tasks"][0]
        self.assertEqual((task["status"], task["attempts"], task["failures"], task["timeout_min"]), ("ACTIVE", 2, 1, 15))
        self.assertEqual(self.ctx().load("RE_STATE.json")["task_log"][-1]["result"], "timeout")
        self.assertIn("task_recover", [e["event"] for e in self.ctx().history()])
        state = self.ctx().load("RE_STATE.json")
        state["tasks"][0]["started_utc"] = self.old(2)
        self.ctx().save("RE_STATE.json", state)
        gre.task_recover(self.ctx(), "T-07", "abandon", "exporter hangs on 4k sheets; switch to tiled export")
        self.assertFalse(any("T-07" in p for p in gre.handoff_check(self.ctx())))

    def test_high_priority_gap_blocks_endless_polish_and_research(self):
        self.start()
        for n in range(4):
            gre.task_start(self.ctx(), "J-%d" % n, "polish", "flash tweak %d" % n)
            gre.task_done(self.ctx(), "J-%d" % n, "ok", "tweaked")
        with self.assertRaisesRegex(ValueError, "POLISH_BLOCKED"):
            gre.task_start(self.ctx(), "J-4", "polish", "one more flash tweak")
        top = gre.candidates(self.ctx())[0]
        self.assertTrue(top["id"].startswith("L"))
        self.assertGreaterEqual(top["score"], 10)
        self.assertNotIn("polish", top["action"])
        self.assertIn(top["id"], gre.next_report(self.ctx()))
        gre.task_start(self.ctx(), "J-4", "polish", "release blocker typo", override_reason="user asked for this fix now")
        gre.task_done(self.ctx(), "J-4", "ok", "fixed")
        for n in range(3):
            gre.task_start(self.ctx(), "R-%d" % n, "research", "jump curve attempt %d" % n, item="L2-01")
            gre.task_done(self.ctx(), "R-%d" % n, "ok", "still unclear")
        with self.assertRaisesRegex(ValueError, "RESEARCH_BUDGET"):
            gre.task_start(self.ctx(), "R-3", "research", "jump curve attempt 3", item="L2-01")
        action = next(c for c in gre.candidates(self.ctx()) if c["id"] == "L2-01")["action"]
        self.assertIn("mature licensed component", action)

    def test_research_and_polish_spin_warnings(self):
        self.start()
        for n, item in enumerate(("L3-01", "L3-02", "L4-01", "L4-02", "L1-01", "L1-02")):
            gre.task_start(self.ctx(), "R-%d" % n, "research", "study %s" % item, item=item)
            gre.task_done(self.ctx(), "R-%d" % n, "ok", "notes")
        self.assertTrue(any("RESEARCH_SPIN" in w for w in gre.guard_warnings(self.ctx())))
        state = self.ctx().load("RE_STATE.json")
        state["guards"]["high_priority_score"] = 99
        self.ctx().save("RE_STATE.json", state)
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
        self.ctx().path("BASE_HANDOFF.md").write_text("# Base 交接\n- 当前等级 NONE；下一步 P3-01。\n", encoding="utf-8")
        problems = gre.handoff_check(self.ctx())
        self.assertEqual(len([p for p in problems if "creator guide must answer" in p]), len(gre.CREATOR_GUIDE))
        guide = "\n".join("- %s见 docs/creator/%d.md 与 scenes/*.json 示例" % (prompt, n) for n, prompt in enumerate(gre.CREATOR_GUIDE))
        self.ctx().path("BASE_HANDOFF.md").write_text("# Base 交接\n- 当前等级 NONE；下一步 P3-01。\n\n## 后续游戏创作交接\n" + guide + "\n", encoding="utf-8")
        self.assertEqual(gre.handoff_check(self.ctx()), [])
        gre.assign(gre.Context(self.root), "agent-b", "E5")
        status = gre.status_report(self.ctx())
        self.assertIn("Assignment: agent-b", status)
        self.assertIn("implement P3-01", status)
        self.assertEqual([e["event"] for e in self.ctx().history()].count("assign"), 2)

    def test_cli_smoke(self):
        self.write("engine/core/a.ts", "1\n")
        self.write("research/code.md", "review\n")
        out = io.StringIO()
        project = ["--project", str(self.root)]
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(gre.main(["init"] + project + ["--code-path", "engine", "--core-path", "engine/core",
                                                            "--reference", "https://example.com/g"]), 0)
            self.assertEqual(gre.main(["validate"] + project), 0)
            self.assertEqual(gre.main(["status"] + project), 0)
            self.assertEqual(gre.main(["next"] + project), 0)
            self.assertEqual(gre.main(["upgrade"] + project), 0)
            self.assertEqual(gre.main(["discover"] + project + ["--source", "code", "--status", "DONE", "--evidence", "research/code.md"]), 0)
            self.assertEqual(gre.main(["parity", "add"] + project + ["--item", "P2-04", "--domain", "P2", "--name", "palette swap",
                                                                     "--source", "assets", "--evidence", "research/code.md"]), 0)
            self.assertEqual(gre.main(["level"] + project + ["--set", "LOGIC_READY"]), 2)
            self.assertEqual(gre.main(["handoff"] + project), 1)
            self.assertEqual(gre.main(["parity", "set"] + project + ["--item", "L1-01", "--status", "RESEARCHING"]), 0)
        self.assertIn("RECORD_CHECK_PASSED", out.getvalue())
        self.assertIn("Next tasks by value", out.getvalue())


if __name__ == "__main__":
    unittest.main()
