"""Tests of the game-reverse-engineering record tool; not tests of any game, decompiler or art."""
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gre_tool", SKILL_ROOT / "scripts" / "gre.py")
gre = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gre)

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
        common = dict(inputs="logic position in tiles", outputs="screen pixels", data_structures="Transform{x,y,sx,sy,rot,pivot,anchor,parent}",
                      constraints="integer pixel snapping", unknowns="none known", reuse="REIMPLEMENT on the Base renderer")
        for tid in gre.PR_TOPICS:
            ref = self.write("research/%s.txt" % tid, "render code listing %s\n" % tid)
            if tid == gre.PRODUCTION_TOPIC:
                gre.present_study(self.ctx(), tid, level="INFERRED", evidence=ref, kind="data", observed="atlas json layout",
                                  gap="no author documentation of the production tools", decision="D", relation="different_method",
                                  base_method="own atlas packer script", items=[], **common)
                continue
            gre.present_study(self.ctx(), tid, level=level, evidence=ref, kind="source", observed="render path traced in source",
                              gap="not compared frame by frame with the running original", decision="B", relation="same_method",
                              original_method="draw call per sprite sorted by sort key %s" % tid,
                              base_method="same composition rebuilt on the Base renderer", **common)

    def reference_and_frames(self):
        inventory = self.write("research/reference-inventory.md", "original build cannot start; no legal original pixels\n")
        gre.present_reference(self.ctx(), "UNAVAILABLE", "PLACEHOLDER_ONLY", ["battle"], [(inventory, "inventory")])
        walk = self.write("research/frame-battle-walkthrough.md", "source walkthrough of one battle frame\n")
        gre.present_frame(self.ctx(), "battle", "source", walkthrough=walk)

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
                "PX08": dict(kinds=["measurement", "measurement"], resolutions=["1280x720", "1920x1080"]),
                "PX09": dict(kinds=["measurement"], bind=[self.write("scenes/geometry.json", '{"window": [0, 0, 960, 540], "board": "data"}')])}
        self.reference_and_frames()
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

    # ---- creator gates (needs Git: the first-use gate tests a clean checkout of HEAD)
    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                               "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"] + list(args),
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message="fixture"):
        if not (self.root / ".git").exists():
            self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    TOOLS = {
        "tools/new_pack.py": "import json, pathlib, sys\nd = pathlib.Path('content/packs') / sys.argv[1]\nd.mkdir(parents=True, exist_ok=True)\n"
                             "(d / 'pack.json').write_text(json.dumps({'id': sys.argv[1], 'background': 'bg.png', 'hero': 'hero.png'}))\n",
        "tools/import_assets.py": "import pathlib, shutil, sys\nfor n in ('bg.png', 'hero.png'):\n"
                                  "    shutil.copy('content/starter/' + n, 'content/packs/%s/%s' % (sys.argv[1], n))\n",
        "tools/validate_assets.py": "import json, pathlib, sys\nbad = []\nfor pack in pathlib.Path('content').rglob('pack.json'):\n"
                                    "    data = json.loads(pack.read_text())\n"
                                    "    bad += [str(pack.parent / data[k]) for k in ('background', 'hero') if not (pack.parent / data[k]).is_file()]\n"
                                    "print('missing: %s' % bad if bad else 'assets ok')\nsys.exit(1 if bad else 0)\n",
        "tools/build.py": "import pathlib\npathlib.Path('dist').mkdir(exist_ok=True)\npathlib.Path('dist/index.html').write_text('<canvas></canvas>')\n",
        "tools/launch.py": "import pathlib, sys\nsys.exit(0 if pathlib.Path('dist/index.html').is_file() else 2)\n",
        "tools/playtest.py": "print('start play end result restart')\n",
        "tools/regression.py": "print('rules regression ok')\n",
    }
    STEPS = [("create-pack", "create_content_pack", ["tools/new_pack.py", "my-pack"]),
             ("import-assets", "import_assets", ["tools/import_assets.py", "my-pack"]),
             ("validate", "validate_assets", ["tools/validate_assets.py"]),
             ("build", "build", ["tools/build.py"]),
             ("launch", "launch_runtime", ["tools/launch.py"]),
             ("playtest", "playtest", ["tools/playtest.py"]),
             ("missing-resource-blocks", "negative_missing_resource", ["tools/validate_assets.py"]),
             ("regression", "regression", ["tools/regression.py"])]

    def creator_gates(self, run=True):
        """Starter content outside the core, a full creator kit and a passing clean first-use run on a commit."""
        self.write("content/starter/pack.json", json.dumps({"id": "frost-meadow", "name": "Frost Meadow Pack",
                                                             "background": "bg.png", "hero": "hero.png"}))
        self.write("content/starter/bg.png", b"starter background")
        self.write("content/starter/hero.png", b"starter hero")
        for relative, code in self.TOOLS.items():
            self.write(relative, code)
        quick = "\n".join("- `python %s`" % " ".join(argv) for _, _, argv in self.STEPS)
        self.write("docs/START_HERE.md", "# 创作者快速开始\n\n" + quick + "\n")
        docs = {}
        for key in gre.KIT_ITEMS:
            if key not in ("start_here", "new_pack_tool", "asset_validator", "runnable_example", "concept_to_runtime"):
                docs[key] = self.write("docs/creator/%s.md" % key, "# %s\nrules with examples\n" % key)
        gre.set_paths(self.ctx(), None, ["content/starter"], None)
        for key, path in dict(docs, start_here="docs/START_HERE.md", new_pack_tool="tools/new_pack.py",
                              asset_validator="tools/validate_assets.py", runnable_example="content/starter").items():
            gre.kit_set(self.ctx(), key, [path])
        gre.kit_set(self.ctx(), "concept_to_runtime", [], na_reason="pixel-art game without a concept-art stage")
        spec = self.ctx().load("FIRST_USE.json")
        spec["start_here"] = "docs/START_HERE.md"
        spec["steps"] = [dict({"id": sid, "kind": kind, "argv": ["{python}"] + argv, "timeout_min": 2},
                              **({"remove": ["content/starter/hero.png"], "expect": "failure"} if kind == "negative_missing_resource" else {}))
                         for sid, kind, argv in self.STEPS]
        self.ctx().save("FIRST_USE.json", spec)
        self.commit("base with creator kit")
        if run:
            return gre.first_use_run(self.ctx())

    def independent_trial(self, agent="agent-independent", independence="independent_reviewer", result="PASS", core_edit=False):
        gre.trial_start(self.ctx(), agent, independence, ["docs/START_HERE.md"])
        if core_edit:
            self.write("engine/core/sim.ts", "export const step = 1; // trial needed a core hack\n")
        clip = self.write("qa/trial/slice-%s.mp4" % agent, ("slice by " + agent).encode())
        return gre.trial_finish(self.ctx(), result, {k: True for k in gre.TRIAL_CHECKS}, [(clip, "recording")], assets=6, steps=9,
                                manual=[], minutes=35.0, unverified=["audio mix on mobile"])

    def make_creator_candidate(self):
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.present_ready()
        self.probe("probe-a", "冰原像素风")
        self.probe("probe-b", "沙漠水彩风")
        self.creator_gates()

    def make_creator_ready(self):
        self.make_creator_candidate()
        self.independent_trial()


class StartAndTakeoverTest(Fixture):
    def test_empty_folder_start_creates_workspace_and_creator_records(self):
        ctx = self.start()
        workspace = json.loads((self.root / gre.WORKSPACE_FILE).read_text(encoding="utf-8"))
        self.assertEqual(workspace["run"]["scope"]["target"], "base")
        self.assertEqual(workspace["run"]["scope"]["game_quota"], 0)
        self.assertEqual(workspace["research"][0]["sources"], ["https://example.com/original-2d-game"])
        self.assertEqual(ctx.current_version(), "0.1.0")
        for name in ("RE_STATE.json", "PARITY.json", "REUSE.json", "PROBES.json", "GATES.json", "TECH_SURVEY.md",
                     "DYNAMIC_STUDY.md", "BASE_HANDOFF.md", "HISTORY.jsonl", "PRESENTATION.json", "CREATOR_KIT.json",
                     "FIRST_USE.json", "REUSE_TRIAL.json"):
            self.assertTrue(ctx.path(name).is_file(), name)
        installed = self.root / gre.SKILL_PATH
        expected = {p for p, _ in gre.kit_manifest()} | {"SHA256SUMS.txt"}
        self.assertEqual({p.relative_to(installed).as_posix() for p in installed.rglob("*") if p.is_file()}, expected)
        self.assertIn("research-private/", (self.root / ".gitignore").read_text(encoding="utf-8"))
        self.assertEqual(self.errors(), [])
        self.assertEqual(gre.derive_level(ctx), "NONE")
        self.assertFalse((ctx.base_dir / "GATES.json").exists(), "no retired Base gate file is created")

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

    def test_v3_workspace_is_refused_with_conversion_hint(self):
        self.write(".production/PROJECT.json", "{}\n")
        with self.assertRaisesRegex(ValueError, "v3 single-game records.*9fc83fe"):
            gre.init(self.root, "core", "0.1.0", "engine", ["engine"], [])

    def test_existing_workspace_with_games_is_adopted_without_changes(self):
        self.start()
        workspace_path = self.root / gre.WORKSPACE_FILE
        workspace = json.loads(workspace_path.read_text(encoding="utf-8"))
        workspace["games"].append({"id": "game-01", "path": "games/game-01", "records": "games/game-01/.production", "layout": "standard"})
        workspace_path.write_bytes(gre.json_bytes(workspace))
        self.write("games/game-01/.production/GAME.json", '{"game_id": "game-01"}\n')
        before = {k: v for k, v in tree(self.root).items() if not k.startswith((".production/local/", ".production/bases/core/re/"))}
        messages = gre.init(self.root, "core", "9.9.9", "", ["engine/core"], [])
        self.assertTrue(any("Adopting existing Base core@0.1.0" in m for m in messages))
        after = tree(self.root)
        for path, value in before.items():
            if path not in (".gitignore", "AGENTS.md"):
                self.assertEqual(after.get(path), value, path)
        self.assertEqual(self.ctx().current_version(), "0.1.0")
        self.assertEqual(self.errors(), [])

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
            gre.set_level(self.ctx(), "CREATOR_CANDIDATE")
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
        self.creator_gates()
        gre.set_level(self.ctx(), "CREATOR_CANDIDATE")
        self.independent_trial()
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
        problems = gre.level_problems(self.ctx(), "CREATOR_CANDIDATE", gre.snapshot(self.ctx()))
        self.assertTrue(any("40% of visual assets are identical" in p for p in problems))

    def test_image_swap_without_gameplay_change_is_not_production_capability(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.probe("probe-a", "冰原像素风", gameplay=False)
        self.probe("probe-b", "沙漠水彩风", gameplay=False)
        problems = gre.level_problems(self.ctx(), "CREATOR_CANDIDATE", gre.snapshot(self.ctx()))
        self.assertTrue(any("swapping images alone" in p for p in problems))
        self.assertIn("visual-only (not production evidence): probe-a, probe-b", gre.status_report(self.ctx()))
        messages = self.probe("probe-a", "冰原像素风", gameplay_items=("P1-01",))
        self.assertTrue(any("must change a gameplay mechanic" in m for m in messages))
        messages = self.probe("probe-b", "沙漠水彩风", loop_input="debug")
        self.assertTrue(any("normal input" in m for m in messages))
        with self.assertRaisesRegex(ValueError, "Cannot claim CREATOR_CANDIDATE"):
            gre.set_level(self.ctx(), "CREATOR_CANDIDATE")

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
        self.assertIn("release rights record complete", gre.status_report(self.ctx()))
        self.assertIn("residual rights risk is never zero", gre.status_report(self.ctx()))
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
        with self.assertRaisesRegex(ValueError, "Presentation Reconstruction Gate: record what reference material exists"):
            gre.set_level(self.ctx(), "PRESENTATION_READY")
        self.reference_and_frames()
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
        with self.assertRaisesRegex(ValueError, "inferred or unknown methods are D"):
            gre.present_study(self.ctx(), "PR03", level="INFERRED", evidence=shot, kind="screenshot", observed="layers visible",
                              gap="draw order inferred from two screenshots", decision="B", relation="same_method")
        gre.present_study(self.ctx(), "PR03", level="INFERRED", evidence=shot, kind="screenshot", observed="layers visible",
                          gap="draw order inferred from two screenshots; not traced in code or at runtime",
                          inputs="?", outputs="frame", data_structures="unknown", constraints="unknown",
                          unknowns="sort key, batching", reuse="REIMPLEMENT with a data-driven layer graph",
                          decision="D", relation="different_method", base_method="data-driven layer graph")
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



class OriginalPipelineFirstTest(Fixture):
    """Generic failure modes: a method written as the original's that is not, corrections, placeholder pixels, self-evidence."""

    def study(self, tid="PR03", **kwargs):
        ref = self.write("research/%s-src.txt" % tid, "draw loop listing %s\n" % tid)
        args = dict(level="STATIC_ONLY", evidence=ref, kind="source", observed="traced in source", gap="not run frame by frame",
                    inputs="world state", outputs="draw list", data_structures="DrawItem{image, rect, sort}", constraints="none known",
                    unknowns="none known", reuse="REIMPLEMENT", original_method="sort by y then layer", base_method="sort by y then layer")
        args.update(kwargs)
        return gre.present_study(self.ctx(), tid, **args)

    def test_b_and_a_require_the_same_method_and_a_reusable_original(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "a different method, downgrade or missing capability must be C"):
            self.study(decision="B", relation="different_method")
        with self.assertRaisesRegex(ValueError, "must disclose difference, reason, impact"):
            self.study(decision="C", relation="different_method")
        self.study(decision="C", relation="different_method",
                   deviation={"difference": "single sorted list instead of per-layer buckets", "reason": "renderer batches by atlas",
                              "impact": "objects on the same row may overlap differently"})
        with self.assertRaisesRegex(ValueError, "A needs the original implementation as a legally reusable KEEP/ADAPT module"):
            self.study("PR04", decision="A", relation="same_method")
        self.write("third_party/anim/LICENSE", "MIT License\n")
        gre.reuse_set(self.ctx(), "orig-anim", source_kind="open_source", license_="MIT", decision="KEEP", base_paths=["engine/core"],
                      evidence="third_party/anim/LICENSE", execution="reviewed", execution_note="read before use; no scripts")
        self.study("PR04", decision="A", relation="same_method", modules=["orig-anim"])

    def test_unknown_or_inferred_methods_are_d_and_tools_are_never_guessed(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "inferred or unknown methods are D"):
            self.study(level="INFERRED", decision="B", relation="same_method")
        with self.assertRaisesRegex(ValueError, "choose A, B or C instead of D"):
            self.study(decision="D", relation="different_method")
        with self.assertRaisesRegex(ValueError, "never infer a tool from a data format"):
            self.study(gre.PRODUCTION_TOPIC, kind="data", decision="B", relation="same_method")
        self.study(gre.PRODUCTION_TOPIC, kind="author-documentation", decision="B", relation="same_method")

    def test_parity_claim_cannot_hide_a_changed_method(self):
        self.start()
        self.own_engine_reuse()
        self.verify("P4-01", visual=True)
        self.study(decision="C", relation="downgrade", items=["P4-01"],
                   deviation={"difference": "no per-row occlusion", "reason": "time box", "impact": "units overlap scenery"})
        problems = gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("P4-01 is claimed PARITY but PR03 records C/downgrade" in p for p in problems))
        self.assertTrue(any("claimed PARITY but PR03" in e for e in self.errors()))

    def test_correction_marks_downstream_checks_and_items_stale(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.present_ready()
        self.assertEqual(gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx())), [])
        with self.assertRaisesRegex(ValueError, "--affects"):
            gre.present_study(self.ctx(), "PR03", correct="draw order is row-major, not y-sorted")
        messages = gre.present_study(self.ctx(), "PR03", correct="draw order is row-major, not y-sorted",
                                     affects=["engine/core/render/sort.ts", "PX03"])
        self.assertTrue(any("revision 1" in m for m in messages))
        snapshot = gre.snapshot(self.ctx())
        problems = gre.presentation_problems(self.ctx(), snapshot)
        self.assertTrue(any(p.startswith("PX03") and "study conclusion of PR03 was corrected" in p for p in problems))
        p401 = next(i for i in snapshot["parity"]["items"] if i["id"] == "P4-01")
        self.assertIn("PR03", gre.item_counts(self.ctx(), p401, "0.1.0", snapshot["core"], snapshot["presentation"]) or "")
        self.px("PX03", kinds=["measurement"])
        self.assertFalse(any(p.startswith("PX03") for p in gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))))
        correction = self.ctx().load("PRESENTATION.json")["study"]["PR03"]["corrections"][0]
        self.assertEqual(correction["affects"], ["engine/core/render/sort.ts", "PX03"])

    def test_placeholder_or_own_pixels_never_establish_visual_fidelity(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.present_ready()
        with self.assertRaisesRegex(ValueError, "asset-source"):
            gre.present_compare(self.ctx(), "DONE", [(self.write("qa/side.png", b"side"), "comparison")])
        gre.present_compare(self.ctx(), "DONE", [(self.write("qa/side.png", b"side"), "comparison")], asset_source="placeholder")
        visual = gre.fidelity(gre.snapshot(self.ctx()))["visual"]
        self.assertTrue(visual.startswith("NOT VERIFIED"))
        inventory = self.write("research/reference-2.md", "licensed original pack received\n")
        gre.present_reference(self.ctx(), "UNAVAILABLE", "LEGAL_ORIGINAL", ["battle"], [(inventory, "inventory")])
        self.assertTrue(gre.fidelity(gre.snapshot(self.ctx()))["visual"].startswith("NOT VERIFIED"), "own/placeholder comparison stays unverified")
        gre.present_compare(self.ctx(), "DONE", [(self.write("qa/side-original.png", b"side original"), "comparison")], asset_source="original")
        fidelity = gre.fidelity(gre.snapshot(self.ctx()))
        self.assertEqual(fidelity["visual"], "compared side by side with legal original assets")
        self.assertIn("source-confirmed only", fidelity["mechanism"])
        self.assertIn("changed: none; unknown: PR13", fidelity["mechanism"])
        self.assertIn("Visual fidelity: compared side by side", gre.status_report(self.ctx()))

    def test_base_output_cited_as_original_evidence_is_rejected(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.present_ready()
        own = "qa/present/PX03-0.png"
        gre.present_study(self.ctx(), "PR05", evidence=own, kind="recording", observed="looks like the original")
        self.assertTrue(any("PR05: cites a Base/test output as evidence of the original" in e for e in self.errors()))

    def test_runtime_frame_needs_full_primitives_formula_and_layers(self):
        self.start()
        inventory = self.write("research/inventory.md", "original runs in the browser\n")
        gre.present_reference(self.ctx(), "AVAILABLE", "NONE", ["battle"], [(inventory, "inventory")])
        walk = self.write("research/walk.md", "source walkthrough\n")
        gre.present_frame(self.ctx(), "battle", "source", walkthrough=walk)
        problems = gre.frame_problems(self.ctx(), self.ctx().load("PRESENTATION.json"))
        self.assertTrue(any("trace a real frame instead of a source walkthrough" in p for p in problems))
        primitive = {"image": "atlas0", "src_rect": [0, 0, 32, 32], "corners": [[0, 0], [32, 0], [32, 32], [0, 32]],
                     "blend": "normal", "render_item": "unit#3", "sort_key": 120}
        trace = self.write("research/frame/trace.json", json.dumps({"primitives": [primitive, {"image": "atlas0", "corners": [[0, 0]]}]}))
        formula = self.write("research/frame/formula.json", json.dumps({"checks": [
            {"name": "tile->screen x", "expected": 412, "actual": 412, "tolerance": 0.5},
            {"name": "tile->screen y", "expected": 233, "actual": 230, "tolerance": 0.5},
            {"name": "shadow offset", "expected": 6, "actual": 6}]}))
        layer = self.write("research/frame/layer-0.png", b"layer0")
        messages = gre.present_frame(self.ctx(), "battle", "runtime", trace=trace, formula=formula, layers=[layer])
        text = "\n".join(messages)
        self.assertIn("1 primitives lack image/src_rect/corners/blend/render_item/sort_key", text)
        self.assertIn("formula check 2/3 (failing: tile->screen y)", text)
        self.assertIn("layer-by-layer rebuild", text)
        self.write(trace, json.dumps({"primitives": [primitive]}))
        self.write(formula, json.dumps({"checks": [{"name": "tile->screen x", "expected": 412, "actual": 412.2, "tolerance": 0.5}]}))
        layer2 = self.write("research/frame/layer-1.png", b"layer1")
        gre.present_frame(self.ctx(), "battle", "runtime", trace=trace, formula=formula, layers=[layer, layer2])
        self.assertEqual(gre.frame_problems(self.ctx(), self.ctx().load("PRESENTATION.json")), [])
        self.write(formula, json.dumps({"checks": [{"name": "edited later", "expected": 1, "actual": 9}]}))
        self.assertTrue(any("formula_check file missing or changed" in p for p in gre.frame_problems(self.ctx(), self.ctx().load("PRESENTATION.json"))))

    def test_reference_inventory_comes_first(self):
        self.start()
        problems = gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("record what reference material exists" in p for p in problems))
        gre.present_reference(self.ctx(), "UNAVAILABLE", "PLACEHOLDER_ONLY", [], [])
        problems = gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("list the scene types" in p for p in problems))
        gre.present_reference(self.ctx(), "UNAVAILABLE", "PLACEHOLDER_ONLY", ["battle", "map"], [])
        problems = gre.presentation_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("no frame study for scene type battle" in p for p in problems))
        self.assertTrue(any("no frame study for scene type map" in p for p in problems))


class CreatorGateTest(Fixture):
    """Decoupling, creator kit, clean first-use, independent reuse, Git baseline, stop and export."""

    def test_core_must_not_name_or_load_example_content(self):
        self.start()
        self.write("content/starter/pack.json", json.dumps({"id": "frost-meadow", "name": "Frost Meadow Pack"}))
        self.write("content/starter/sprites/snow_golem.png", b"img")
        problems = gre.decoupling_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("declare starter_paths" in p for p in problems))
        gre.set_paths(self.ctx(), None, ["content/starter"], None)
        self.assertEqual(gre.decoupling_problems(self.ctx(), gre.snapshot(self.ctx())), [])
        for code, needle in (("if (pack.id === 'frost-meadow') boost();\n", "frost-meadow"),
                             ("const boss = 'snow_golem';\n", "snow_golem"),
                             ("load('content/starter/pack.json');\n", "starter path content/starter")):
            self.write("engine/core/hack.ts", code)
            problems = gre.decoupling_problems(self.ctx(), gre.snapshot(self.ctx()))
            self.assertTrue(any("coupled to example content" in p and needle in p for p in problems), code)
        state = self.ctx().load("RE_STATE.json")
        state["decoupling_allow"] = [{"path": "engine/core/hack.ts", "term": "content/starter", "reason": "dev-only default pack loader"}]
        self.ctx().save("RE_STATE.json", state)
        self.assertEqual(gre.decoupling_problems(self.ctx(), gre.snapshot(self.ctx())), [])
        gre.set_paths(self.ctx(), None, ["engine/core/examples"], None)
        self.assertTrue(any("lives inside the engine core" in p for p in gre.decoupling_problems(self.ctx(), gre.snapshot(self.ctx()))))

    def test_creator_kit_must_be_complete_and_exercised(self):
        self.start()
        problems = gre.kit_problems(self.ctx(), gre.snapshot(self.ctx()))
        self.assertTrue(any("missing scene_geometry_contract" in p for p in problems))
        gre.kit_set(self.ctx(), "asset_validator", [], na_reason="we trust artists")
        self.assertTrue(any("asset_validator cannot be NOT_APPLICABLE" in p for p in gre.kit_problems(self.ctx(), gre.snapshot(self.ctx()))))
        gre.kit_set(self.ctx(), "asset_validator", ["tools/missing.py"])
        self.assertTrue(any("tools/missing.py does not exist" in p for p in gre.kit_problems(self.ctx(), gre.snapshot(self.ctx()))))
        self.creator_gates(run=False)
        self.assertEqual(gre.kit_problems(self.ctx(), gre.snapshot(self.ctx())), [])
        self.write("tools/other_validator.py", "print('ok')\n")
        gre.kit_set(self.ctx(), "asset_validator", ["tools/other_validator.py"])
        self.assertTrue(any("not exercised by the first-use validate_assets step" in p for p in gre.kit_problems(self.ctx(), gre.snapshot(self.ctx()))))

    def test_clean_first_use_passes_and_catches_failures(self):
        self.start()
        lines = self.creator_gates()
        self.assertIn("PASSED", lines[0], "\n".join(lines))
        self.assertEqual(gre.first_use_problems(self.ctx(), gre.snapshot(self.ctx())), [])
        run = self.ctx().load("FIRST_USE.json")["runs"][-1]
        self.assertEqual([r["kind"] for r in run["steps"]], list(gre.FIRST_USE_KINDS))
        self.assertTrue(all((self.root / r["log"]["path"]).is_file() for r in run["steps"]))
        self.assertFalse((self.root / "content/packs").exists(), "first-use ran in a clean checkout, not in the workspace")
        # A command that the Quick Start does not mention is a spec error.
        self.write("docs/START_HERE.md", "# Quick start\nrun the tools\n")
        self.assertTrue(any("does not appear in docs/START_HERE.md" in p for p in gre.first_use_problems(self.ctx(), gre.snapshot(self.ctx()))))
        self.git("checkout", "--", "docs/START_HERE.md")
        # The content-pack generator breaks: the run fails at that step and stays failed.
        self.write("tools/new_pack.py", "import sys\nsys.exit(3)\n")
        self.commit("broken generator")
        lines = gre.first_use_run(self.ctx())
        self.assertIn("FAILED", lines[0])
        self.assertTrue(any("create-pack" in l and "FAIL" in l for l in lines))
        self.assertTrue(any("failed at create-pack" in p for p in gre.first_use_problems(self.ctx(), gre.snapshot(self.ctx()))))
        # A validator that never fails cannot pass the missing-resource step.
        self.write("tools/new_pack.py", self.TOOLS["tools/new_pack.py"])
        self.write("tools/validate_assets.py", "print('always fine')\n")
        self.commit("lenient validator")
        lines = gre.first_use_run(self.ctx())
        self.assertTrue(any("missing-resource-blocks" in l and "FAIL" in l for l in lines), "\n".join(lines))
        # A pass goes stale when HEAD moves.
        self.write("tools/validate_assets.py", self.TOOLS["tools/validate_assets.py"])
        self.commit("fixed validator")
        self.assertIn("PASSED", gre.first_use_run(self.ctx())[0])
        self.write("docs/extra.md", "more docs\n")
        self.commit("docs only")
        self.assertTrue(any("but HEAD is" in p for p in gre.first_use_problems(self.ctx(), gre.snapshot(self.ctx()))))

    def test_candidate_needs_creator_gates_and_ready_needs_independent_reuse(self):
        self.start()
        self.logic_ready()
        self.verify_group("presentation")
        self.verify_group("creator")
        self.present_ready()
        self.probe("probe-a", "冰原像素风")
        self.probe("probe-b", "沙漠水彩风")
        problems = gre.level_problems(self.ctx(), "CREATOR_CANDIDATE", gre.snapshot(self.ctx()))
        for needle in ("Decoupling:", "Creator kit:", "Clean first-use:"):
            self.assertTrue(any(p.startswith(needle) for p in problems), needle)
        self.creator_gates()
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_CANDIDATE")
        self.assertTrue(any("no independent reuse trial yet" in p for p in gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))))
        gre.assign(self.ctx(), "agent-builder", "E0-E7")
        self.independent_trial(agent="agent-builder")
        self.assertTrue(any("not independent of the Base development" in p
                            for p in gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))))
        self.independent_trial(agent="agent-same-context", independence="separate_context_same_environment")
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_CANDIDATE")
        lines = self.independent_trial(agent="agent-core-hacker", core_edit=True)
        self.assertTrue(any("core files changed: 1" in l for l in lines))
        self.write("engine/core/sim.ts", "export const step = 1;\n")
        problems = gre.level_problems(self.ctx(), "CREATOR_READY", gre.snapshot(self.ctx()))
        self.assertEqual([p for p in problems if not p.startswith("Independent reuse:")], [], "only the trial itself is at fault")
        self.assertTrue(any("needed 1 engine-core changes" in p for p in problems), problems)
        self.independent_trial(agent="agent-independent", result="BLOCKED")
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_CANDIDATE", "a blocked trial keeps the Base at CREATOR_CANDIDATE")
        self.independent_trial(agent="agent-independent")
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_READY")
        trial = self.ctx().load("REUSE_TRIAL.json")["trials"][-1]
        self.assertEqual((trial["assets"], trial["steps"], trial["first_success_minutes"], trial["core_files_changed"]), (6, 9, 35.0, []))
        self.assertEqual(trial["unverified"], ["audio mix on mobile"])

    def test_uncommitted_core_changes_block_creator_levels(self):
        self.start()
        self.make_creator_candidate()
        self.assertEqual(gre.derive_level(self.ctx()), "CREATOR_CANDIDATE")
        self.write("content/starter/pack.json", json.dumps({"id": "frost-meadow", "name": "Frost Meadow Pack", "background": "bg.png",
                                                             "hero": "hero.png", "note": "uncommitted"}))
        problems = gre.level_problems(self.ctx(), "CREATOR_CANDIDATE", gre.snapshot(self.ctx()))
        self.assertTrue(any("Git baseline: uncommitted changes under core/starter paths" in p for p in problems))

    def test_stop_export_freeze_and_device_paths(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "Target CREATOR_READY not reached"):
            gre.stop(self.ctx(), "TARGET_REACHED", "done")
        with self.assertRaisesRegex(ValueError, "truthful --reason"):
            gre.stop(self.ctx(), "EXTERNAL_BLOCKED", "")
        gre.stop(self.ctx(), "EXTERNAL_BLOCKED", "original build server offline; tried mirrors A and B; unblock: user uploads the build")
        with self.assertRaisesRegex(ValueError, "only a CREATOR_CANDIDATE or CREATOR_READY version can be frozen"):
            gre.base_freeze(self.ctx())
        first = gre.export_handoff(self.ctx())
        second = gre.export_handoff(self.ctx())
        self.assertIn("below CREATOR_CANDIDATE", first[1])
        exports = sorted((self.ctx().base_dir / "handoff/0.1.0").glob("*-CREATOR_HANDOFF.json"))
        self.assertEqual(len(exports), 2, "exports are never overwritten")
        contract = json.loads(exports[-1].read_text(encoding="utf-8"))
        self.assertEqual((contract["schema_version"], contract["base_id"], contract["base_version"], contract["level"]),
                         ("creator-handoff-1", "core", "0.1.0", "NONE"))
        self.assertEqual(contract["core_fingerprint"], gre.core_fingerprint(self.root, ["engine/core"]))
        self.assertIn("residual rights risk is never zero", contract["rights"]["note"])
        self.assertEqual(contract["independent_reuse"]["status"], "NOT_RUN")
        self.assertTrue(contract["open_gaps"])
        gre.base_bump(self.ctx(), "0.2.0", "new renderer; breaking for content packs")
        self.assertEqual(self.ctx().current_version(), "0.2.0")
        survey = self.ctx().path("TECH_SURVEY.md")
        survey.write_text(survey.read_text(encoding="utf-8") + "\nbuild at C:\\Users\\someone\\proj\n", encoding="utf-8")
        self.assertTrue(any("absolute" in e.lower() or "device" in e.lower() for e in self.errors()))


if __name__ == "__main__":
    unittest.main()
