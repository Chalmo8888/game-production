#!/usr/bin/env python3
"""Game Creation & Polish Skill tool (preview). Python 3.9+, standard library only.

Keeps the per-game records of games built on a delivered Creator Base: games/<id>/
design and state, stage progress, design/QA/release gates bound to the Base version,
asset status, authorised scope, handoff and recovery. The Base itself is owned by
game-reverse-engineering; this tool only reads its exported creator handoff.
Never runs a game or build, installs packages, launches agents, commits, pushes or
deploys. Validation checks records, evidence bytes, readiness claims and isolation;
it does not judge gameplay quality, art quality or legal clearance.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

KIT_ROOT = Path(__file__).resolve().parent.parent
KIT_VERSION = "0.1.0-preview"
SCHEMA_VERSION = "3.0"
SKILL_PATH = ".agents/skills/game-creation-polish"
WORKSPACE_FILE = ".production/WORKSPACE.json"
AGENTS_MARKERS = ("<!-- GAME_CREATION_POLISH_BEGIN -->", "<!-- GAME_CREATION_POLISH_END -->")
IGNORE_MARKERS = ("# GAME_CREATION_POLISH_LOCAL", "# GAME_REVERSE_ENGINEERING_LOCAL")
IGNORE_BLOCK = "# GAME_CREATION_POLISH_LOCAL\n.production/local/\n"
HANDOFF_SCHEMA = "creator-handoff-1"
HANDOFF_LEVELS = ["NONE", "LOGIC_READY", "PRESENTATION_READY", "CREATOR_CANDIDATE", "CREATOR_READY"]
UNFILLED_MARKER = "TEMPLATE_UNFILLED"

RESEARCH_STAGES = ["R0", "R1", "R2"]
GAME_STAGES = ["G%d" % i for i in range(8)]
ALL_STAGES = RESEARCH_STAGES + GAME_STAGES
LEGACY_STAGES = ["S%d" % i for i in range(7)]
TARGETS = ("research", "base", "game", "full_pipeline", "batch")
DEFAULT_QUOTA: Dict[str, Optional[int]] = {"research": 0, "base": 0, "game": 1, "full_pipeline": 1, "batch": None}
RUN_MODES = ("auto", "stage", "review")
RUN_STATUSES = ("NEW", "RUNNING", "TARGET_REACHED", "HANDOFF_READY", "EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED")
STOP_STATUSES = ("EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED")
STAGE_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "DONE", "BLOCKED", "NEEDS_REWORK", "NOT_APPLICABLE")
GATE_STATUSES = ("PASS", "FAIL", "UNVERIFIED", "BLOCKED", "NOT_APPLICABLE")
PUB_STATUSES = ("NOT_AUTHORIZED", "REVIEW_PENDING", "AUTHORIZED_NOT_PUBLISHED", "PUBLISHED")
REVIEW_MODES = ("self_review", "separate_context_same_environment", "independent_reviewer", "external_approval")
ASSET_STATUSES = ("planned", "source_generated", "processed", "integrated", "verified", "rejected")
INTAKE_ROUTES = ("", "new_research", "adopt_existing", "new_game_on_base")

GAME_LEVELS = ["IN_PROGRESS", "FEATURE_COMPLETE", "GAME_READY", "RELEASE_CANDIDATE", "PUBLICATION_APPROVED"]
GAME_REQUIREMENTS = [
    ("FEATURE_COMPLETE", {"D01", "Q01", "Q02"}, set()),
    ("GAME_READY", {"D02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08"}, set()),
    ("RELEASE_CANDIDATE", {"R01", "R02"}, set()),
    ("PUBLICATION_APPROVED", {"R03", "R04"}, {"Q08", "R03", "R04"}),
]
GAME_GATE_IDS = {"D01", "D02"} | {"Q%02d" % i for i in range(1, 9)} | {"R01", "R02", "R03", "R04"}
VERSION_BOUND_GAME_GATES = {"Q%02d" % i for i in range(1, 9)} | {"R01", "R02", "R03"}
APPROVAL_GATES = {"R04"}
DESIGN_DOCS = {
    "D01": ["design/GAME_DESIGN.md"],
    "D02": ["design/ART_DIRECTION.md", "design/ART_ASSET_PLAN.md", "design/ANIMATION_SPEC.md"],
}
GAME_DESIGN_SECTIONS = set(range(1, 18))
GAME_RECORD_TEMPLATES = {
    ".production/GAME.json": "game/GAME.json",
    ".production/GATES.json": "game/GATES.json",
    ".production/ASSETS.json": "game/ASSETS.json",
    ".production/BACKLOG.md": "game/BACKLOG.md",
    ".production/HANDOFF.md": "game/HANDOFF.md",
    ".production/RIGHTS_LEDGER.md": "workspace/RIGHTS_LEDGER.md",
    "design/GAME_DESIGN.md": "game/GAME_DESIGN.md",
    "design/ART_DIRECTION.md": "game/ART_DIRECTION.md",
    "design/ART_ASSET_PLAN.md": "game/ART_ASSET_PLAN.md",
    "design/ANIMATION_SPEC.md": "game/ANIMATION_SPEC.md",
    "design/RELEASE_CHECKLIST.md": "game/RELEASE_CHECKLIST.md",
}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".cache", ".venv"}
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.$-]+\\|(?<![\w.])/(?:Users|home)/[^\s\"'`)]+")


# ---------------------------------------------------------------- helpers

def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    """Reject absolute/traversal paths and symlink escapes on any host OS."""
    if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
        raise ValueError("expected a nonempty project-relative path")
    normalized = relative.replace("\\", "/")
    win_path = PureWindowsPath(relative)
    path = PurePosixPath(normalized)
    if path.is_absolute() or win_path.drive or win_path.root or ".." in path.parts:
        raise ValueError("absolute paths and '..' are not allowed: " + relative)
    resolved = (root / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path escapes its root (possibly symlink): " + relative) from exc
    return resolved


def load_json(path: Path) -> Dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read JSON " + str(path) + ": " + str(exc)) from exc
    if not isinstance(obj, dict):
        raise ValueError("Expected JSON object: " + str(path))
    return obj


def json_bytes(obj: Dict[str, Any]) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(json_bytes(obj))
    os.replace(str(temporary), str(path))


def create_new(path: Path, data: bytes) -> bool:
    """Exclusive create; never overwrite a pre-existing project file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as out:
            out.write(data)
        return True
    except FileExistsError:
        return False


def template(relative: str) -> Path:
    return KIT_ROOT / "templates" / relative


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def level_index(levels: List[str], value: Any) -> int:
    return levels.index(value) if isinstance(value, str) and value in levels else 0


def check_slug(value: str, kind: str) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        raise ValueError(kind + " ID must be lowercase letters, digits and '-' (max 48): " + repr(value))
    return value


def snapshot(obj: Dict[str, Any], **extra: Any) -> Dict[str, Any]:
    copy = json.loads(json.dumps(obj))
    copy.update(extra)
    return copy


def append_text(path: Path, addition: str) -> None:
    existing = path.read_bytes() if path.exists() else b""
    path.write_bytes(existing + addition.encode("utf-8"))


def git_text(root: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root)] + args, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=8)
        return result.stdout.strip() if result.returncode == 0 else "not available (not a repository or command failed)"
    except (OSError, subprocess.SubprocessError):
        return "not available (Git missing or timed out)"


# ---------------------------------------------------------------- Skill package

def kit_manifest(kit_root: Path = KIT_ROOT) -> List[Tuple[str, str]]:
    sums = kit_root / "SHA256SUMS.txt"
    entries = []
    for line in sums.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line.strip())
        if not match:
            raise ValueError("Malformed SHA256SUMS line: " + line)
        entries.append((match.group(2), match.group(1).lower()))
    return entries


def manifest_bytes(path: Path, sha: str) -> Optional[bytes]:
    """File bytes matching the manifest; tolerates CRLF checkouts (core.autocrlf) by normalizing to LF."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == sha:
        return data
    normalized = data.replace(b"\r\n", b"\n")
    return normalized if hashlib.sha256(normalized).hexdigest() == sha else None


def install_plan(root: Path) -> List[Tuple[Path, bytes]]:
    """Install exactly the released files listed in SHA256SUMS.txt (never .git, caches or strays)."""
    plan = []
    for relative, sha in kit_manifest():
        data = manifest_bytes(safe_path(KIT_ROOT, relative), sha)
        if data is None:
            raise ValueError("Skill package integrity check failed (SHA256SUMS mismatch): " + relative)
        plan.append((safe_path(root, SKILL_PATH + "/" + relative), data))
    sums = (KIT_ROOT / "SHA256SUMS.txt").read_bytes().replace(b"\r\n", b"\n")
    plan.append((safe_path(root, SKILL_PATH + "/SHA256SUMS.txt"), sums))
    return plan


def same_text_bytes(a: bytes, b: bytes) -> bool:
    return a == b or a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def ensure_agents_and_ignore(root: Path) -> List[str]:
    messages = []
    agents = safe_path(root, "AGENTS.md")
    existing = agents.read_text(encoding="utf-8-sig") if agents.exists() else ""
    if AGENTS_MARKERS[0] not in existing:
        block = template("AGENTS.block.md").read_text(encoding="utf-8").rstrip("\n")
        append_text(agents, ("\n\n" if existing else "") + block + "\n")
        messages.append("Appended game-creation-polish guide to AGENTS.md; existing instructions retained.")
    ignores = safe_path(root, ".gitignore")
    current = ignores.read_text(encoding="utf-8-sig") if ignores.exists() else ""
    if not any(marker in current for marker in IGNORE_MARKERS):
        append_text(ignores, ("\n" if current and not current.endswith("\n") else "") + IGNORE_BLOCK)
        messages.append("Added .production/local/ to .gitignore (device facts, not shared).")
    return messages


def probe_environment(root: Path, label: Optional[str] = None) -> Dict[str, Any]:
    """Refresh device-local facts only. Never touches shared workspace/base/game records."""
    path = safe_path(root, ".production/local/ENVIRONMENT.json")
    env = load_json(path) if path.is_file() else load_json(template("workspace/ENVIRONMENT.local.json"))
    env["schema_version"] = SCHEMA_VERSION
    env["os"] = "%s %s (%s)" % (platform.system(), platform.release(), platform.machine())
    env["probed_utc"] = now_utc()
    env["project_root"] = str(root)
    if label:
        env["device_label"] = label
    tools = env.setdefault("tools", {})
    tools["python"] = platform.python_version()
    git_version = git_text(root, ["--version"])
    tools["git"] = git_version if git_version.startswith("git version") else "missing_or_unavailable"
    tools["shell"] = os.environ.get("SHELL") or os.environ.get("COMSPEC") or "unknown"
    save_json(path, env)
    return env


# ---------------------------------------------------------------- gates

def check_evidence(evidence: Any, root: Path, label: str) -> List[str]:
    errors = []
    if not isinstance(evidence, list) or not evidence:
        return [label + ": PASS requires evidence files, not only a claim"]
    for index, item in enumerate(evidence):
        item_label = label + ": evidence[%d] " % index
        if not isinstance(item, dict):
            errors.append(item_label + "must be an object")
            continue
        if not item.get("kind") or not item.get("observed"):
            errors.append(item_label + "requires kind and observed result")
        sha = item.get("sha256", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            errors.append(item_label + "requires SHA-256")
            continue
        try:
            path = safe_path(root, item.get("path", ""))
            if not path.is_file():
                errors.append(item_label + "file missing: " + str(item.get("path")))
            elif digest(path) != sha.lower():
                errors.append(item_label + "SHA-256 mismatch: " + str(item.get("path")))
        except (ValueError, OSError) as exc:
            errors.append(item_label + str(exc))
    return errors


def check_gate_entry(gate: Dict[str, Any], label: str, evidence_root: Path,
                     version_bound: bool, approval: bool) -> List[str]:
    errors = []
    status = gate.get("status")
    if not isinstance(status, str) or status not in GATE_STATUSES:
        return [label + ": invalid status"]
    if status == "NOT_APPLICABLE" and not text(gate.get("scope_basis")):
        errors.append(label + ": NOT_APPLICABLE requires a scope basis, not missing tools")
    if status != "PASS":
        return errors
    if not text(gate.get("criteria")):
        errors.append(label + ": PASS requires concrete criteria")
    if not text(gate.get("subject_revision")):
        errors.append(label + ": PASS requires tested code/assets/build identity (subject_revision)")
    reviewer = gate.get("reviewer")
    independence = reviewer.get("independence") if isinstance(reviewer, dict) else None
    if not isinstance(reviewer, dict) or not text(reviewer.get("identity")) or independence not in REVIEW_MODES:
        errors.append(label + ": PASS requires reviewer identity and actual independence")
    elif approval and independence != "external_approval":
        errors.append(label + ": publication approval must come from the user/rights holder (external_approval); an Agent cannot self-approve")
    elif not approval and independence == "external_approval":
        errors.append(label + ": external_approval is reserved for publication approval gates")
    if version_bound and not text(gate.get("base_version")):
        errors.append(label + ": PASS requires base_version (the Base version it was verified against)")
    return errors + check_evidence(gate.get("evidence"), evidence_root, label)


def check_gate_file(obj: Dict[str, Any], expected: set, evidence_root: Path, label: str,
                    version_bound: set, approval: set) -> List[str]:
    errors = []
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append(label + ": unsupported schema_version")
    gates = obj.get("gates")
    if not isinstance(gates, list):
        return errors + [label + ": gates must be a list"]
    seen = set()
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append(label + ": gate entry must be an object")
            continue
        gid = gate.get("id")
        if not isinstance(gid, str) or not re.fullmatch(r"[A-Z]\d{2,}", gid):
            errors.append(label + ": invalid gate ID " + repr(gid))
            continue
        if gid in seen:
            errors.append(label + ": duplicate gate ID " + gid)
        seen.add(gid)
        errors += check_gate_entry(gate, label + " " + gid, evidence_root, gid in version_bound, gid in approval)
    missing = expected - seen
    if missing:
        errors.append(label + ": missing gates (scope them NOT_APPLICABLE with a basis, do not delete): " + ", ".join(sorted(missing)))
    return errors


def gates_by_id(obj: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    gates = obj.get("gates")
    return {g["id"]: g for g in gates if isinstance(g, dict) and isinstance(g.get("id"), str)} if isinstance(gates, list) else {}


def gate_problem(gate: Optional[Dict[str, Any]], evidence_root: Path, version: Optional[str],
                 strict: bool, extra_check=None) -> Optional[str]:
    if not isinstance(gate, dict):
        return "missing"
    status = gate.get("status")
    gid = gate.get("id")
    if status == "PASS":
        errors = check_gate_entry(gate, str(gid), evidence_root, version is not None, gid in APPROVAL_GATES)
        if errors:
            return "PASS record invalid (" + errors[0].split(": ", 1)[-1] + ")"
        if version is not None and text(gate.get("base_version")) != version:
            return "PASS was verified against base %s, not %s; re-verify" % (text(gate.get("base_version")) or "(none)", version)
        return extra_check(gid) if extra_check else None
    if status == "NOT_APPLICABLE":
        if strict:
            return "must be PASS; NOT_APPLICABLE is not accepted at this level"
        return None if text(gate.get("scope_basis")) else "NOT_APPLICABLE without scope_basis"
    return "is " + str(status)


# ---------------------------------------------------------------- workspace model

class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.path = safe_path(self.root, WORKSPACE_FILE)
        if not self.path.is_file():
            raise ValueError("No Creator Base workspace here (.production/WORKSPACE.json). game-creation-polish starts from a Base delivered by game-reverse-engineering.")
        self.data = load_json(self.path)

    def save(self) -> None:
        save_json(self.path, self.data)

    def entries(self, kind: str) -> List[Dict[str, Any]]:
        value = self.data.get(kind)
        return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []

    def entry(self, kind: str, item_id: str) -> Dict[str, Any]:
        for item in self.entries(kind):
            if item.get("id") == item_id:
                return item
        raise ValueError("Unknown %s: %s" % ({"bases": "Base", "games": "game"}.get(kind, kind), item_id))

    # bases
    def base_dir(self, bid: str) -> Path:
        return safe_path(self.root, self.entry("bases", bid).get("records", ""))

    def load_base(self, bid: str) -> Dict[str, Any]:
        return load_json(self.base_dir(bid) / "BASE.json")

    # games
    def is_legacy(self, gid: str) -> bool:
        return self.entry("games", gid).get("layout") == "v3_legacy"

    def game_root(self, gid: str) -> Path:
        path = self.entry("games", gid).get("path", "")
        return self.root if path == "." else safe_path(self.root, path)

    def game_records(self, gid: str) -> Path:
        return safe_path(self.root, self.entry("games", gid).get("records", ""))

    def load_game(self, gid: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if self.is_legacy(gid):
            raise ValueError(gid + " is a migrated v3 game; game-creation-polish does not manage v3 records.")
        folder = self.game_records(gid)
        return load_json(folder / "GAME.json"), load_json(folder / "GATES.json")

    def save_game(self, gid: str, game: Dict[str, Any]) -> None:
        save_json(self.game_records(gid) / "GAME.json", game)

    @property
    def run(self) -> Dict[str, Any]:
        run = self.data.get("run")
        if not isinstance(run, dict):
            raise ValueError("WORKSPACE.run must be an object")
        return run

    @property
    def scope(self) -> Dict[str, Any]:
        scope = self.run.get("scope")
        if not isinstance(scope, dict):
            raise ValueError("WORKSPACE.run.scope must be an object")
        return scope


def version_entry(base: Dict[str, Any], version: str) -> Optional[Dict[str, Any]]:
    for item in base.get("versions", []) if isinstance(base.get("versions"), list) else []:
        if isinstance(item, dict) and item.get("version") == version:
            return item
    return None


def iter_files(folder: Path):
    if folder.is_file():
        yield folder
        return
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not (set(path.relative_to(folder).parts[:-1]) & EXCLUDED_DIRS):
            yield path


def core_fingerprint(root: Path, core_paths: List[str]) -> str:
    """Same algorithm as game-reverse-engineering: hash of every file (path + content) under the core paths."""
    result = hashlib.sha256()
    entries = []
    for relative in core_paths:
        folder = safe_path(root, relative)
        if not folder.exists():
            continue
        for path in iter_files(folder):
            entries.append((path.resolve().relative_to(root.resolve()).as_posix(), digest(path)))
    for name, sha in sorted(set(entries)):
        result.update((name + "\0" + sha + "\n").encode("utf-8"))
    return result.hexdigest() if entries else ""


def latest_handoff(ws: Workspace, bid: str, version: str) -> Tuple[Optional[Dict[str, Any]], Optional[Path]]:
    folder = ws.base_dir(bid) / "handoff" / version
    files = sorted(folder.glob("*-CREATOR_HANDOFF.json")) if folder.is_dir() else []
    if not files:
        return None, None
    return load_json(files[-1]), files[-1]


def handoff_problems(ws: Workspace, bid: str, version: str, need_level: str = "CREATOR_CANDIDATE") -> List[str]:
    """The Base is usable for production only through its exported, unchanged creator handoff."""
    try:
        contract, path = latest_handoff(ws, bid, version)
    except ValueError as exc:
        return [str(exc)]
    if contract is None:
        return ["Base %s@%s has no creator handoff export (ask for game-reverse-engineering `gre.py export`)" % (bid, version)]
    problems = []
    if contract.get("schema_version") != HANDOFF_SCHEMA:
        problems.append("handoff %s has unsupported schema %s" % (path.name, contract.get("schema_version")))
    if contract.get("base_id") != bid or contract.get("base_version") != version:
        problems.append("handoff %s is for %s@%s, not %s@%s" % (path.name, contract.get("base_id"), contract.get("base_version"), bid, version))
    changed = []
    for entry in contract.get("files", []):
        try:
            target = safe_path(ws.root, entry.get("path", ""))
            if not target.is_file() or digest(target) != entry.get("sha256"):
                changed.append(entry.get("path"))
        except (ValueError, AttributeError):
            changed.append(str(entry))
    core = contract.get("core_paths") if isinstance(contract.get("core_paths"), list) else []
    try:
        if not core or core_fingerprint(ws.root, core) != contract.get("core_fingerprint"):
            problems.append("Base core %s differs from the exported fingerprint; the Base core changed after export (games must not edit it)" % (core or "(missing core_paths)"))
    except ValueError as exc:
        problems.append("handoff core_paths invalid: %s" % exc)
    if changed:
        problems.append("Base files listed in the handoff changed or are missing (%s); the Base changed after export ; re-export or rebind" % ", ".join(changed[:3]))
    level = contract.get("level")
    if level_index(HANDOFF_LEVELS, level) < HANDOFF_LEVELS.index(need_level):
        problems.append("Base %s@%s is %s; game production needs %s or better" % (bid, version, level, need_level))
    return problems


def refresh_dependents(ws: Workspace, bid: str) -> None:
    base_path = ws.base_dir(bid) / "BASE.json"
    base = load_json(base_path)
    dependents = []
    for item in ws.entries("games"):
        if item.get("layout") == "v3_legacy":
            continue
        game, _ = ws.load_game(item["id"])
        binding = game.get("base_binding", {})
        if binding.get("base_id") == bid:
            dependents.append({"game": item["id"], "version": binding.get("version", "")})
    base["dependent_games"] = dependents
    save_json(base_path, base)


# ---------------------------------------------------------------- game model

def design_doc_problems(game_root: Path, gid: str) -> List[str]:
    problems = []
    for relative in DESIGN_DOCS.get(gid, []):
        path = game_root / relative
        if not path.is_file():
            problems.append(relative + " is missing")
            continue
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        if UNFILLED_MARKER in content:
            problems.append(relative + " still carries the TEMPLATE_UNFILLED marker")
        if relative.endswith("GAME_DESIGN.md"):
            found = {int(n) for n in re.findall(r"^##\s+(\d+)\.", content, re.M)}
            missing = sorted(GAME_DESIGN_SECTIONS - found)
            if missing:
                problems.append("GAME_DESIGN.md lacks sections " + ", ".join(map(str, missing)))
    if gid == "D02":
        try:
            assets = load_json(game_root / ".production/ASSETS.json").get("assets", [])
        except ValueError:
            assets = []
        if not any(isinstance(a, dict) and a.get("status") == "verified" for a in assets):
            problems.append("D02 needs at least one representative asset verified at runtime in ASSETS.json")
    return problems


def check_assets(obj: Dict[str, Any], game_root: Path, base_code_root: Optional[Path], label: str) -> List[str]:
    errors = []
    if obj.get("schema_version") != SCHEMA_VERSION:
        errors.append(label + ": unsupported schema_version")
    assets = obj.get("assets")
    if not isinstance(assets, list):
        return errors + [label + ": assets must be a list"]
    seen = set()
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            errors.append(label + "[%d]: must be an object" % index)
            continue
        aid = asset.get("id")
        item = "%s %s" % (label, aid)
        if not text(aid):
            errors.append(label + "[%d]: id required" % index)
        elif aid in seen:
            errors.append(item + ": duplicate asset ID")
        seen.add(aid)
        status = asset.get("status")
        if status not in ASSET_STATUSES:
            errors.append(item + ": invalid status")
            continue
        scope = asset.get("scope", "game")
        if scope not in ("game", "base"):
            errors.append(item + ": scope must be game or base")
            continue
        file_root = game_root if scope == "game" else base_code_root
        if status not in ("planned", "rejected") and not text(asset.get("provenance")):
            errors.append(item + ": %s requires provenance (tool/author/source)" % status)
        if status == "rejected" and not text(asset.get("rejected_reason")):
            errors.append(item + ": rejected requires rejected_reason")
        if status in ("integrated", "verified"):
            if not text(asset.get("license")):
                errors.append(item + ": %s requires license/usage basis" % status)
            files = asset.get("runtime_files")
            if not isinstance(files, list) or not files:
                errors.append(item + ": %s requires runtime_files actually loaded by the game" % status)
            elif file_root is None:
                errors.append(item + ": base-scoped asset but bound Base code_path is unavailable")
            else:
                for f_index, entry in enumerate(files):
                    f_label = item + ": runtime_files[%d] " % f_index
                    if not isinstance(entry, dict) or not re.fullmatch(r"[a-fA-F0-9]{64}", str(entry.get("sha256", ""))):
                        errors.append(f_label + "requires path and SHA-256")
                        continue
                    try:
                        path = safe_path(file_root, entry.get("path", ""))
                        if not path.is_file() or digest(path) != entry["sha256"].lower():
                            errors.append(f_label + "missing or SHA-256 mismatch: " + str(entry.get("path")))
                    except (ValueError, OSError) as exc:
                        errors.append(f_label + str(exc))
        if status == "verified":
            errors += [e.replace("PASS requires", "verified requires") for e in check_evidence(asset.get("evidence"), game_root, item)]
    return errors


def base_code_root(ws: Workspace, bid: str) -> Optional[Path]:
    try:
        base = ws.load_base(bid)
        code = base.get("code_path", "")
        return ws.root if code == "." else safe_path(ws.root, code)
    except ValueError:
        return None


def game_level_problems(ws: Workspace, gid: str, level: str, loaded=None) -> List[str]:
    target = level_index(GAME_LEVELS, level)
    if target == 0:
        return []
    game, gates = loaded or ws.load_game(gid)
    root = ws.game_root(gid)
    binding = game.get("base_binding", {}) if isinstance(game.get("base_binding"), dict) else {}
    version = text(binding.get("version"))
    by_id = gates_by_id(gates)
    problems = []

    def docs(gate_id):
        found = design_doc_problems(root, gate_id)
        return found[0] if found else None

    strict_all = set().union(*(strict for _, _, strict in GAME_REQUIREMENTS[:target]))
    for name, required, _ in GAME_REQUIREMENTS[:target]:
        for gate_id in sorted(required):
            bound = version if gate_id in VERSION_BOUND_GAME_GATES else None
            problem = gate_problem(by_id.get(gate_id), root, bound, gate_id in strict_all,
                                   docs if gate_id in DESIGN_DOCS else None)
            if problem:
                problems.append("%s %s (needed for %s)" % (gate_id, problem, name))
    if target >= GAME_LEVELS.index("GAME_READY"):
        bid = text(binding.get("base_id"))
        problems += ["Base handoff: " + p for p in handoff_problems(ws, bid, version)]
        if target >= GAME_LEVELS.index("PUBLICATION_APPROVED"):
            contract, _ = latest_handoff(ws, bid, version)
            rights = (contract or {}).get("rights", {})
            if rights.get("RE01") != "PASS" or rights.get("RE03") not in ("PASS", "NOT_APPLICABLE"):
                problems.append("Base rights are incomplete in the handoff (RE01=%s, RE03=%s); a game cannot be approved for publication on uncleared Base code or original assets"
                                % (rights.get("RE01", "missing"), rights.get("RE03", "missing")))
    if target >= GAME_LEVELS.index("RELEASE_CANDIDATE"):
        release = game.get("release", {}) if isinstance(game.get("release"), dict) else {}
        path, sha = text(release.get("artifact_path")), text(release.get("artifact_sha256"))
        if not path or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            problems.append("release candidate artifact path and SHA-256 are not recorded")
        else:
            try:
                artifact = safe_path(root, path)
                if not artifact.is_file() or digest(artifact) != sha.lower():
                    problems.append("release artifact missing or SHA-256 mismatch")
            except (ValueError, OSError) as exc:
                problems.append(str(exc))
    return problems


def derive_game_level(ws: Workspace, gid: str, loaded=None) -> str:
    result = GAME_LEVELS[0]
    for level in GAME_LEVELS[1:]:
        if game_level_problems(ws, gid, level, loaded):
            break
        result = level
    return result


def stage_done_problems(ws: Workspace, gid: str, stage: str, loaded) -> List[str]:
    game, gates = loaded
    root = ws.game_root(gid)
    by_id = gates_by_id(gates)

    def docs(gate_id):
        found = design_doc_problems(root, gate_id)
        return found[0] if found else None

    if stage in ("G1", "G2"):
        gate_id = "D01" if stage == "G1" else "D02"
        problem = gate_problem(by_id.get(gate_id), root, None, False, docs)
        return ["%s %s" % (gate_id, problem)] if problem else []
    if stage == "G5":
        return game_level_problems(ws, gid, "GAME_READY", loaded)
    if stage == "G6":
        return game_level_problems(ws, gid, "RELEASE_CANDIDATE", loaded)
    if stage == "G7":
        problems = []
        if game.get("stages", {}).get("G6") not in ("DONE", "NOT_APPLICABLE"):
            problems.append("G6 is not finished")
        retro = game.get("retrospective", {})
        if not isinstance(retro, dict) or not text(retro.get("summary")):
            problems.append("retrospective.summary (Base version used, reusable capabilities, lessons, core feedback) is empty")
        return problems
    return []


# ---------------------------------------------------------------- workspace commands

def new_scope(target: str, basis: str, quota: Optional[int] = None, games: Optional[List[str]] = None,
              required: str = "RELEASE_CANDIDATE") -> Dict[str, Any]:
    if target not in TARGETS:
        raise ValueError("Unknown target: " + str(target))
    if required not in GAME_LEVELS[1:]:
        raise ValueError("required_readiness must be one of " + ", ".join(GAME_LEVELS[1:]))
    games = list(games or [])
    if quota is None:
        quota = DEFAULT_QUOTA[target] if target != "batch" else (len(games) or None)
    if target == "batch" and quota is None:
        raise ValueError("batch target needs --game-quota N or --games a,b,c from the user's explicit request")
    if quota is not None and quota < len(games):
        raise ValueError("game_quota is smaller than the listed games")
    return {"target": target, "required_readiness": required, "game_quota": quota, "games": games, "basis": basis}


def dependents_needing_regression(ws: Workspace, bid: str) -> List[Tuple[str, str]]:
    base = ws.load_base(bid)
    current = base.get("current_version")
    result = []
    for item in ws.entries("games"):
        if item.get("layout") == "v3_legacy":
            continue
        binding = ws.load_game(item["id"])[0].get("base_binding", {})
        if binding.get("base_id") == bid and binding.get("version") != current:
            result.append((item["id"], str(binding.get("version"))))
    return result


def parse_base_ref(ref: str) -> Tuple[str, Optional[str]]:
    bid, _, version = ref.partition("@")
    return bid, version or None


def check_game_path_free(ws: Workspace, relative: str) -> None:
    new = PurePosixPath(relative.replace("\\", "/"))
    for item in ws.entries("games"):
        if item.get("path") == ".":
            continue
        other = PurePosixPath(str(item.get("path", "")))
        if new == other or other in new.parents or new in other.parents:
            raise ValueError("Game directory overlaps registered game %s (%s)" % (item.get("id"), other))


def game_create(ws: Workspace, gid: str, base_ref: str, title: str = "", brief: str = "",
                path: Optional[str] = None, user_request: str = "", adopt_existing: bool = False) -> List[str]:
    check_slug(gid, "Game")
    if any(g.get("id") == gid for g in ws.entries("games")):
        raise ValueError("Game already registered: " + gid)
    bid, version = parse_base_ref(base_ref)
    base = ws.load_base(bid)
    version = version or base.get("current_version")
    if version_entry(base, version) is None:
        raise ValueError("Base %s has no version %s" % (bid, version))
    scope = ws.scope
    messages = []
    if text(user_request):
        ws.run.setdefault("scope_history", []).append(snapshot(scope, replaced_utc=now_utc()))
        if scope.get("target") in ("research", "base", "game"):
            scope = new_scope("game", user_request, 1, [], scope.get("required_readiness", "RELEASE_CANDIDATE"))
        else:
            scope = snapshot(scope, game_quota=(scope.get("game_quota") or len(scope.get("games", []))) + 1,
                             basis=text(scope.get("basis")) + " | " + user_request)
        ws.run["scope"] = scope
        messages.append("Scope updated from explicit user request: " + user_request)
    quota = scope.get("game_quota")
    if quota is not None and len(scope.get("games", [])) >= quota:
        raise ValueError("Authorized scope '%s' allows %s new game(s) and has %s. Creating more needs the user's explicit request (--user-request)."
                         % (scope.get("target"), quota, len(scope.get("games", []))))
    relative = path or (ws.data["layout"].get("games_dir", "games") + "/" + gid)
    game_root = safe_path(ws.root, relative)
    if game_root == ws.root:
        raise ValueError("A new game cannot use the workspace root; each game gets its own games/<id>/ folder.")
    check_game_path_free(ws, relative)
    if (game_root / ".production/GAME.json").exists():
        raise ValueError("Game records already exist at " + relative)
    if game_root.exists() and any(game_root.iterdir()) and not adopt_existing:
        raise ValueError("Directory %s already has files. Use --adopt-existing to register it without touching them." % relative)
    for record, source in GAME_RECORD_TEMPLATES.items():
        data = template(source).read_bytes()
        if record == ".production/GAME.json":
            game = load_json(template(source))
            game.update(game_id=gid, title=title or gid, last_checkpoint_utc=now_utc())
            game["brief"].update(user_request=user_request or brief, goal=brief)
            game["base_binding"] = {"base_id": bid, "version": version, "history": []}
            data = json_bytes(game)
        create_new(game_root / record, data)
    ws.data.setdefault("games", []).append({"id": gid, "path": relative, "records": relative + "/.production", "layout": "standard"})
    scope.setdefault("games", []).append(gid)
    ws.data["focus"].update(game=gid, base=bid, stage="G1")
    ws.save()
    refresh_dependents(ws, bid)
    messages.append("Created game %s at %s bound to %s@%s; next stage G1 (game design)." % (gid, relative, bid, version))
    blockers = handoff_problems(ws, bid, version)
    if blockers:
        messages.append("NOTE: %s. Design (G1/G2) may start, but this game cannot become GAME_READY until the Base handoff is CREATOR_CANDIDATE or better." % blockers[0])
    return messages


def game_stage(ws: Workspace, gid: str, stage: str, status: str, note: str = "") -> List[str]:
    if stage not in GAME_STAGES or status not in STAGE_STATUSES:
        raise ValueError("stage must be G0..G7 and status one of " + ", ".join(STAGE_STATUSES))
    mode = ws.run.get("mode")
    if mode == "review":
        raise ValueError("review mode is read-only: record findings, do not advance stages")
    if mode == "stage" and stage not in ws.run.get("allowed_stages", []):
        raise ValueError("Stage %s is outside this session's allowed stages %s" % (stage, ws.run.get("allowed_stages")))
    game, gates = ws.load_game(gid)
    if status == "NOT_APPLICABLE" and not text(note):
        raise ValueError("NOT_APPLICABLE needs --note with the scope basis (not missing tools)")
    if status == "DONE":
        problems = stage_done_problems(ws, gid, stage, (game, gates))
        if problems:
            raise ValueError("%s cannot be DONE:\n- %s" % (stage, "\n- ".join(problems)))
    game.setdefault("stages", {})[stage] = status
    if text(note):
        game.setdefault("stage_notes", {})[stage] = note
    game["last_checkpoint_utc"] = now_utc()
    ws.save_game(gid, game)
    messages = ["%s %s = %s" % (gid, stage, status)]
    if ws.run.get("status") == "NEW":
        ws.run["status"] = "RUNNING"
    if status in ("DONE", "NOT_APPLICABLE") and ws.data["focus"].get("game") == gid:
        allowed = ws.run.get("allowed_stages", GAME_STAGES)
        remaining = [s for s in GAME_STAGES if s in allowed and game["stages"].get(s) not in ("DONE", "NOT_APPLICABLE")]
        if remaining:
            ws.data["focus"]["stage"] = remaining[0]
            if mode == "auto":
                messages.append("A finished stage is not a stop. Continue with %s %s." % (gid, remaining[0]))
            else:
                messages.append("Next allowed stage: " + remaining[0])
        elif mode == "stage":
            messages.append("All allowed stages are finished: write the handoff and set run status HANDOFF_READY.")
        else:
            messages.append("All game stages finished; check the authorized target with `run --status TARGET_REACHED`.")
    ws.save()
    return messages


def game_update(ws: Workspace, gid: str, readiness: Optional[str] = None, publication: Optional[str] = None,
                next_action: Optional[str] = None, task: Optional[str] = None, agent: Optional[str] = None,
                agent_stages: Optional[List[str]] = None, clear_assignment: bool = False,
                artifact: Optional[str] = None, retrospective: Optional[str] = None) -> List[str]:
    game, gates = ws.load_game(gid)
    messages = []
    if artifact is not None:
        path = safe_path(ws.game_root(gid), artifact)
        if not path.is_file():
            raise ValueError("Artifact not found inside the game directory: " + artifact)
        game.setdefault("release", {}).update(artifact_path=artifact, artifact_sha256=digest(path))
        messages.append("Recorded artifact %s sha256=%s" % (artifact, game["release"]["artifact_sha256"]))
    if retrospective is not None:
        game.setdefault("retrospective", {})["summary"] = retrospective
    if next_action is not None:
        game["next_action"] = next_action
    if task is not None:
        game["current_task_id"] = task
    if clear_assignment:
        game["assignment"] = {"agent_label": "", "allowed_stages": [], "since_utc": "", "note": ""}
    if agent is not None:
        stages = agent_stages or []
        if not stages or any(s not in GAME_STAGES for s in stages):
            raise ValueError("--assign-stages must list G0..G7 stages for the assigned Agent")
        game["assignment"] = {"agent_label": agent, "allowed_stages": stages, "since_utc": now_utc(), "note": ""}
        messages.append("%s assigned to %s for %s" % (gid, agent, ",".join(stages)))
    if readiness is not None:
        if readiness not in GAME_LEVELS:
            raise ValueError("readiness must be one of " + ", ".join(GAME_LEVELS))
        if level_index(GAME_LEVELS, readiness) > level_index(GAME_LEVELS, game.get("readiness")):
            problems = game_level_problems(ws, gid, readiness, (game, gates))
            if problems:
                raise ValueError("Cannot claim %s for %s:\n- %s" % (readiness, gid, "\n- ".join(problems)))
        game["readiness"] = readiness
        messages.append("%s readiness = %s" % (gid, readiness))
    if publication is not None:
        if publication not in PUB_STATUSES:
            raise ValueError("publication status must be one of " + ", ".join(PUB_STATUSES))
        if publication in ("AUTHORIZED_NOT_PUBLISHED", "PUBLISHED"):
            if game.get("readiness") != "PUBLICATION_APPROVED" or game_level_problems(ws, gid, "PUBLICATION_APPROVED", (game, gates)):
                raise ValueError("%s requires PUBLICATION_APPROVED backed by R04 external approval evidence" % publication)
        game["publication_status"] = publication
    game["last_checkpoint_utc"] = now_utc()
    ws.save_game(gid, game)
    return messages or ["Updated " + gid]


def game_rebind(ws: Workspace, gid: str, base_ref: str) -> List[str]:
    game, gates = ws.load_game(gid)
    old = dict(game.get("base_binding", {}))
    bid, version = parse_base_ref(base_ref)
    bid = bid or old.get("base_id")
    base = ws.load_base(bid)
    version = version or base.get("current_version")
    if version_entry(base, version) is None:
        raise ValueError("Base %s has no version %s" % (bid, version))
    history = list(old.get("history", []))
    history.append({"base_id": old.get("base_id"), "version": old.get("version"), "replaced_utc": now_utc()})
    game["base_binding"] = {"base_id": bid, "version": version, "history": history}
    messages = ["%s now bound to %s@%s (was %s@%s)." % (gid, bid, version, old.get("base_id"), old.get("version"))]
    derived = derive_game_level(ws, gid, (game, gates))
    if level_index(GAME_LEVELS, game.get("readiness")) > level_index(GAME_LEVELS, derived):
        messages.append("Readiness lowered %s -> %s until regression evidence exists for the new Base." % (game.get("readiness"), derived))
        game["readiness"] = derived
    for stage in ("G5", "G6"):
        if game.get("stages", {}).get(stage) == "DONE" and stage_done_problems(ws, gid, stage, (game, gates)):
            game["stages"][stage] = "NEEDS_REWORK"
            messages.append(stage + " -> NEEDS_REWORK (QA evidence was for the previous Base)")
    messages.append("Regression required: re-verify Q01-Q08 and R01-R03 with base_version=%s." % version)
    ws.save_game(gid, game)
    for affected in {bid, old.get("base_id")}:
        if affected and any(b.get("id") == affected for b in ws.entries("bases")):
            refresh_dependents(ws, affected)
    return messages


def set_focus(ws: Workspace, research=None, base=None, game=None, stage=None, task=None) -> List[str]:
    focus = ws.data["focus"]
    for kind, value in (("research", research), ("bases", base), ("games", game)):
        if value:
            ws.entry(kind, value)
    if stage is not None and stage not in ALL_STAGES + LEGACY_STAGES + [""]:
        raise ValueError("Unknown stage: " + stage)
    for key, value in (("research", research), ("base", base), ("game", game), ("stage", stage), ("task", task)):
        if value is not None:
            focus[key] = value
    ws.save()
    return ["Focus: " + ", ".join("%s=%s" % (k, focus.get(k) or "-") for k in ("research", "base", "game", "stage", "task"))]


def set_scope(ws: Workspace, target: str, basis: str, quota: Optional[int] = None, games: Optional[List[str]] = None,
              required: Optional[str] = None, mode: Optional[str] = None, allowed_stages: Optional[List[str]] = None) -> List[str]:
    if not text(basis):
        raise ValueError("--basis must quote the user's instruction that defines this scope")
    for gid in games or []:
        ws.entry("games", gid)
    old = ws.scope
    if target == old.get("target"):
        quota = old.get("game_quota") if quota is None else quota
        games = games or list(old.get("games", []))
    scope = new_scope(target, basis, quota, games, required or old.get("required_readiness", "RELEASE_CANDIDATE"))
    ws.run.setdefault("scope_history", []).append(snapshot(old, replaced_utc=now_utc()))
    ws.run["scope"] = scope
    if mode:
        if mode not in RUN_MODES:
            raise ValueError("mode must be one of " + ", ".join(RUN_MODES))
        ws.run["mode"] = mode
    if allowed_stages:
        if any(s not in ALL_STAGES + LEGACY_STAGES for s in allowed_stages):
            raise ValueError("allowed stages must be R0..R2 / G0..G7")
        ws.run["allowed_stages"] = allowed_stages
    ws.save()
    return ["Scope: target=%s quota=%s games=%s mode=%s" % (target, scope["game_quota"], scope["games"], ws.run.get("mode"))]


def target_problems(ws: Workspace) -> List[str]:
    scope = ws.scope
    target = scope.get("target")
    problems = []

    def base_at_least(level):
        bid = ws.data["focus"].get("base")
        if not bid:
            return ["no focus Base"]
        base = ws.load_base(bid)
        return handoff_problems(ws, bid, base.get("current_version"), level)

    def games_ready():
        games = scope.get("games", [])
        if not games:
            return ["no games in the authorized scope yet"]
        found = []
        required = scope.get("required_readiness", "RELEASE_CANDIDATE")
        for gid in games:
            if ws.is_legacy(gid):
                found.append("%s uses retired v3 records; it is outside game-creation-polish" % gid)
                continue
            derived = derive_game_level(ws, gid)
            if level_index(GAME_LEVELS, derived) < GAME_LEVELS.index(required):
                found.append("%s is %s, needs %s: %s" % (gid, derived, required, "; ".join(game_level_problems(ws, gid, required)[:3])))
        return found

    if target in ("research", "base"):
        problems.append("target %s is research/Base work owned by game-reverse-engineering; record a game target with `scope` or `game create --user-request`" % target)
    elif target == "full_pipeline":
        problems += base_at_least("CREATOR_CANDIDATE") + games_ready()
    elif target in ("game", "batch"):
        if target == "batch" and scope.get("game_quota") is not None and len(scope.get("games", [])) < scope["game_quota"]:
            problems.append("batch has %d of %d games" % (len(scope.get("games", [])), scope["game_quota"]))
        problems += games_ready()
    else:
        problems.append("unknown target")
    return problems


def set_run_status(ws: Workspace, status: str, reason: str = "") -> List[str]:
    if status not in RUN_STATUSES:
        raise ValueError("status must be one of " + ", ".join(RUN_STATUSES))
    if status in STOP_STATUSES and not text(reason):
        raise ValueError(status + " requires a truthful --reason")
    if status == "TARGET_REACHED":
        problems = target_problems(ws)
        if problems:
            raise ValueError("Authorized target not reached; keep working:\n- " + "\n- ".join(problems))
    ws.run.update(status=status, stop_reason=reason)
    ws.data["last_checkpoint_utc"] = now_utc()
    ws.save()
    return ["Run status = " + status]


# ---------------------------------------------------------------- validation


def scan_record_paths(ws: Workspace) -> Tuple[List[str], List[str]]:
    """Shared records must not contain device paths, nor reference another game's directory."""
    errors, warnings = [], []
    skip = {"local", "evidence", "archive"}
    games_dir = ws.data.get("layout", {}).get("games_dir", "games")
    game_ids = {g.get("id") for g in ws.entries("games")}

    def files_under(folder: Path):
        if not folder.is_dir():
            return
        for path in folder.rglob("*"):
            relative = path.relative_to(folder).parts
            if path.is_file() and not (set(relative[:-1]) & skip) and path.suffix in (".json", ".md", ".txt"):
                yield path

    owners: List[Tuple[Path, Optional[str]]] = [(ws.root / ".production", None)]
    for item in ws.entries("games"):
        if item.get("layout") == "v3_legacy":
            continue
        root = ws.game_root(item["id"])
        owners += [(root / ".production", item["id"]), (root / "design", item["id"])]
    cross = re.compile(re.escape(games_dir) + r"/([a-z0-9][a-z0-9-]*)/")
    for folder, owner in owners:
        for path in files_under(folder):
            label = path.relative_to(ws.root).as_posix()
            content = path.read_text(encoding="utf-8-sig", errors="replace")
            match = ABS_PATH_RE.search(content)
            if match:
                errors.append("%s contains a device-specific absolute path (%s); use project-relative paths or .production/local/" % (label, match.group(0)[:40]))
            if owner:
                for other in set(cross.findall(content)):
                    if other != owner and other in game_ids:
                        message = "%s references another game's directory %s/%s/" % (label, games_dir, other)
                        (errors if path.suffix == ".json" else warnings).append(message)
    return errors, warnings


def validate_game(ws: Workspace, gid: str, strict: bool = False) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    label = "Game " + gid
    if ws.is_legacy(gid):
        return [], [label + ": retired v3 records are not managed by game-creation-polish"]
    try:
        game, gates = ws.load_game(gid)
    except ValueError as exc:
        return [label + ": " + str(exc)], warnings
    root = ws.game_root(gid)
    if game.get("schema_version") != SCHEMA_VERSION:
        errors.append(label + ": GAME.json unsupported schema_version")
    if game.get("game_id") != gid:
        errors.append(label + ": GAME.json game_id does not match the registry")
    binding = game.get("base_binding") if isinstance(game.get("base_binding"), dict) else {}
    try:
        base = ws.load_base(text(binding.get("base_id")))
        if version_entry(base, text(binding.get("version"))) is None:
            errors.append(label + ": bound Base version %s does not exist" % binding.get("version"))
        elif binding.get("version") != base.get("current_version"):
            warnings.append(label + ": bound to %s@%s while current is %s (upgrade needs regression)" % (binding.get("base_id"), binding.get("version"), base.get("current_version")))
    except ValueError as exc:
        errors.append(label + ": base_binding " + str(exc))
    errors += check_gate_file(gates, GAME_GATE_IDS, root, label + " GATES", VERSION_BOUND_GAME_GATES, APPROVAL_GATES)
    try:
        bid = text(binding.get("base_id"))
        errors += check_assets(load_json(root / ".production/ASSETS.json"), root,
                               base_code_root(ws, bid) if bid else None, label + " ASSETS")
    except ValueError as exc:
        errors.append(label + ": " + str(exc))
    stages = game.get("stages")
    if not isinstance(stages, dict) or set(stages) != set(GAME_STAGES):
        errors.append(label + ": stages must contain exactly G0..G7")
        stages = {}
    for stage, status in stages.items():
        if status not in STAGE_STATUSES:
            errors.append("%s %s: invalid stage status" % (label, stage))
        elif status == "NOT_APPLICABLE" and not text(game.get("stage_notes", {}).get(stage)):
            errors.append("%s %s: NOT_APPLICABLE needs a stage note with the scope basis" % (label, stage))
        elif status == "DONE" and not errors:
            for problem in stage_done_problems(ws, gid, stage, (game, gates)):
                errors.append("%s %s is DONE but %s" % (label, stage, problem))
    if game.get("readiness") not in GAME_LEVELS:
        errors.append(label + ": invalid readiness")
    elif not errors:
        derived = derive_game_level(ws, gid, (game, gates))
        if level_index(GAME_LEVELS, game["readiness"]) > level_index(GAME_LEVELS, derived):
            problems = game_level_problems(ws, gid, game["readiness"], (game, gates))
            errors.append("%s claims %s but evidence supports %s: %s" % (label, game["readiness"], derived, problems[0] if problems else ""))
    publication = game.get("publication_status")
    if publication not in PUB_STATUSES:
        errors.append(label + ": invalid publication_status")
    elif publication in ("AUTHORIZED_NOT_PUBLISHED", "PUBLISHED") and game.get("readiness") != "PUBLICATION_APPROVED":
        errors.append(label + ": %s requires PUBLICATION_APPROVED" % publication)
    assignment = game.get("assignment", {})
    if isinstance(assignment, dict) and text(assignment.get("agent_label")):
        stages_assigned = assignment.get("allowed_stages")
        if not isinstance(stages_assigned, list) or not stages_assigned or any(s not in GAME_STAGES for s in stages_assigned):
            errors.append(label + ": assignment needs allowed_stages within G0..G7")
    for name in ("BACKLOG.md", "HANDOFF.md", "RIGHTS_LEDGER.md"):
        if not (root / ".production" / name).is_file():
            errors.append(label + ": missing record " + name)
    if strict and not (isinstance(game.get("acceptance_contract"), dict) and game["acceptance_contract"].get("defined") is True):
        errors.append(label + ": acceptance contract is not yet defined from the actual project")
    return errors, warnings


def validate_workspace(root: Path, strict: bool = False, only_game: Optional[str] = None) -> Tuple[List[str], List[str]]:
    root = root.resolve()
    if not (root / WORKSPACE_FILE).is_file():
        return ["No Creator Base workspace here (.production/WORKSPACE.json)."], []
    try:
        ws = Workspace(root)
    except ValueError as exc:
        return [str(exc)], []
    errors, warnings = [], []
    data = ws.data
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("WORKSPACE: unsupported schema_version")
    layout = data.get("layout", {})
    try:
        safe_path(root, layout.get("games_dir", ""))
    except (ValueError, AttributeError) as exc:
        errors.append("WORKSPACE.layout.games_dir: " + str(exc))
    if data.get("intake", {}).get("route", "") not in INTAKE_ROUTES:
        errors.append("WORKSPACE.intake.route is invalid")
    for kind in ("research", "bases", "games"):
        ids = [e.get("id") for e in ws.entries(kind)]
        if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not SLUG_RE.fullmatch(i) for i in ids):
            errors.append("WORKSPACE.%s has invalid or duplicate IDs" % kind)
        for item in ws.entries(kind):
            try:
                safe_path(root, item.get("records", ""))
            except ValueError as exc:
                errors.append("WORKSPACE.%s %s records: %s" % (kind, item.get("id"), exc))
    paths = []
    for item in ws.entries("games"):
        if item.get("path") == ".":
            if item.get("layout") != "v3_legacy":
                errors.append("Game %s: only migrated v3 games may live at the workspace root" % item.get("id"))
            continue
        try:
            safe_path(root, item.get("path", ""))
            paths.append((item.get("id"), PurePosixPath(item["path"])))
        except (ValueError, KeyError) as exc:
            errors.append("Game %s path: %s" % (item.get("id"), exc))
    for index, (gid, path) in enumerate(paths):
        for other_id, other in paths[index + 1:]:
            if path == other or path in other.parents or other in path.parents:
                errors.append("Games %s and %s share or nest directories; each game needs its own folder" % (gid, other_id))
    focus = data.get("focus", {})
    for key, kind in (("research", "research"), ("base", "bases"), ("game", "games")):
        if focus.get(key) and focus[key] not in {e.get("id") for e in ws.entries(kind)}:
            errors.append("WORKSPACE.focus.%s refers to an unregistered ID" % key)
    if focus.get("stage", "") not in ALL_STAGES + LEGACY_STAGES + [""]:
        errors.append("WORKSPACE.focus.stage is invalid")
    try:
        run, scope = ws.run, ws.scope
        if run.get("mode") not in RUN_MODES:
            errors.append("WORKSPACE.run.mode is invalid")
        if run.get("status") not in RUN_STATUSES:
            errors.append("WORKSPACE.run.status is invalid")
        allowed = run.get("allowed_stages")
        if not isinstance(allowed, list) or not allowed or any(s not in ALL_STAGES + LEGACY_STAGES for s in allowed):
            errors.append("WORKSPACE.run.allowed_stages must be a nonempty list of R0..R2/G0..G7")
        if run.get("status") in STOP_STATUSES and not text(run.get("stop_reason")):
            errors.append("Stopping state requires a truthful stop_reason")
        if scope.get("target") not in TARGETS:
            errors.append("WORKSPACE.run.scope.target is invalid")
        if scope.get("required_readiness") not in GAME_LEVELS[1:]:
            errors.append("WORKSPACE.run.scope.required_readiness is invalid")
        quota = scope.get("game_quota")
        scoped = scope.get("games", [])
        if quota is not None and (type(quota) is not int or quota < 0):
            errors.append("WORKSPACE.run.scope.game_quota must be null or a non-negative integer")
        elif not isinstance(scoped, list) or any(g not in {e.get("id") for e in ws.entries("games")} for g in scoped):
            errors.append("WORKSPACE.run.scope.games must list registered games")
        elif quota is not None and len(scoped) > quota:
            errors.append("WORKSPACE.run.scope has more games than its authorized quota")
    except ValueError as exc:
        errors.append(str(exc))
    for name in ("BACKLOG.md", "HANDOFF.md", "RIGHTS_LEDGER.md"):
        if not (root / ".production" / name).is_file():
            errors.append("Missing workspace record: " + name)
    if errors:
        return errors, warnings
    for item in ws.entries("bases"):
        try:
            base = ws.load_base(item["id"])
            warnings += ["Base %s: %s" % (item["id"], p) for p in handoff_problems(ws, item["id"], base.get("current_version", ""))]
        except ValueError as exc:
            errors.append("Base %s: %s" % (item["id"], exc))
    for item in ws.entries("games"):
        if only_game and item["id"] != only_game:
            continue
        game_errors, game_warnings = validate_game(ws, item["id"], strict)
        errors += game_errors
        warnings += game_warnings
    path_errors, path_warnings = scan_record_paths(ws)
    errors += path_errors
    warnings += path_warnings
    if not errors and (ws.run.get("status") == "TARGET_REACHED" or strict):
        problems = target_problems(ws)
        if problems:
            prefix = "TARGET_REACHED recorded but " if ws.run.get("status") == "TARGET_REACHED" else "Strict target: "
            errors += [prefix + p for p in problems]
    if not strict:
        warnings.append("Structure check permits UNVERIFIED/FAIL/BLOCKED states; it is not target acceptance.")
    warnings.append("This tool verifies records, bytes and paths only; it cannot judge gameplay, art quality or legal clearance.")
    return errors, warnings


# ---------------------------------------------------------------- status and handoff

def status_report(ws: Workspace, only_game: Optional[str] = None) -> str:
    data, run, scope = ws.data, ws.run, ws.scope
    focus = data.get("focus", {})
    lines = ["# Workspace %s (kit %s)" % (data.get("name"), data.get("kit_version")),
             "Run: mode=%s status=%s%s" % (run.get("mode"), run.get("status"), (" reason=" + run["stop_reason"]) if run.get("stop_reason") else ""),
             "Authorized scope: target=%s required=%s quota=%s games=%s" % (scope.get("target"), scope.get("required_readiness"), scope.get("game_quota"), scope.get("games")),
             "  basis: " + str(scope.get("basis")),
             "Focus: " + ", ".join("%s=%s" % (k, focus.get(k) or "-") for k in ("research", "base", "game", "stage", "task")),
             "Next workspace action: " + str(data.get("next_action", ""))]
    for item in ws.entries("bases"):
        base = ws.load_base(item["id"])
        current = base.get("current_version")
        contract, path = latest_handoff(ws, item["id"], current)
        blockers = handoff_problems(ws, item["id"], current)
        lines.append("Base %s@%s handoff level=%s (%s)%s" % (item["id"], current, (contract or {}).get("level", "NONE"),
                     path.name if path else "no export", (" — " + blockers[0]) if blockers else ""))
        if contract:
            lines.append("  fidelity: mechanism %s | visual %s" % (contract.get("fidelity", {}).get("mechanism"), contract.get("fidelity", {}).get("visual")))
            lines.append("  independent reuse: %s; open gaps: %d" % (contract.get("independent_reuse", {}).get("status"), len(contract.get("open_gaps", []))))
        for gid, old in dependents_needing_regression(ws, item["id"]):
            lines.append("  REGRESSION NEEDED: %s bound to %s, current is %s" % (gid, old, current))
    for item in ws.entries("games"):
        gid = item["id"]
        if only_game and gid != only_game:
            continue
        if item.get("layout") == "v3_legacy":
            state = load_json(ws.game_records(gid) / "STATE.json")
            lines.append("Game %s (v3 records at %s): stage=%s status=%s next=%s" % (gid, item.get("records"),
                         state.get("run", {}).get("current_stage"), state.get("run", {}).get("status"), state.get("next_action")))
            continue
        game, gates = ws.load_game(gid)
        derived = derive_game_level(ws, gid, (game, gates))
        binding = game.get("base_binding", {})
        stages = " ".join("%s:%s" % (s, game.get("stages", {}).get(s)) for s in GAME_STAGES)
        lines.append("Game %s '%s' path=%s base=%s@%s readiness claimed=%s evidence-supports=%s publication=%s"
                     % (gid, game.get("title"), item.get("path"), binding.get("base_id"), binding.get("version"),
                        game.get("readiness"), derived, game.get("publication_status")))
        lines.append("  stages: " + stages)
        assignment = game.get("assignment", {})
        if text(assignment.get("agent_label")):
            lines.append("  assignment: %s -> %s" % (assignment["agent_label"], ",".join(assignment.get("allowed_stages", []))))
        lines.append("  next: %s (task %s)" % (game.get("next_action"), game.get("current_task_id") or "-"))
        if derived != GAME_LEVELS[-1]:
            nxt = GAME_LEVELS[GAME_LEVELS.index(derived) + 1]
            blockers = game_level_problems(ws, gid, nxt, (game, gates))[:4]
            lines.append("  to reach %s: %s" % (nxt, "; ".join(blockers)))
    problems = target_problems(ws)
    lines.append("Authorized target: " + ("MET (verify, then record TARGET_REACHED)" if not problems else "not met — " + "; ".join(problems[:4])))
    return "\n".join(lines)


def handoff_report(ws: Workspace, only_game: Optional[str] = None, check: bool = False) -> Tuple[str, List[str]]:
    problems = []
    workspace_handoff = ws.root / ".production/HANDOFF.md"
    if not workspace_handoff.is_file():
        problems.append("workspace HANDOFF.md is missing")
    elif ws.run.get("status") in STOP_STATUSES + ("HANDOFF_READY",) and workspace_handoff.read_bytes() == template("workspace/HANDOFF.md").read_bytes():
        problems.append("workspace HANDOFF.md is still the blank template")
    if ws.run.get("status") in STOP_STATUSES + ("HANDOFF_READY",) and not text(ws.data.get("next_action")):
        problems.append("workspace next_action is empty")
    targets = [only_game] if only_game else ([ws.data["focus"]["game"]] if ws.data.get("focus", {}).get("game") else [])
    for gid in targets:
        ws.entry("games", gid)
        if ws.is_legacy(gid):
            if not (ws.game_records(gid) / "HANDOFF.md").is_file():
                problems.append(gid + ": v3 HANDOFF.md missing")
            continue
        game, _ = ws.load_game(gid)
        if not text(game.get("next_action")):
            problems.append(gid + ": next_action is empty; the next Agent would not know where to start")
        game_handoff = ws.game_records(gid) / "HANDOFF.md"
        if not game_handoff.is_file() or game_handoff.read_bytes() == template("game/HANDOFF.md").read_bytes():
            problems.append(gid + ": game HANDOFF.md is missing or still the blank template")
        errors, _ = validate_game(ws, gid)
        problems += errors
    lines = ["# Generated handoff summary — verify against files before continuing",
             status_report(ws, only_game),
             "Actual HEAD: " + git_text(ws.root, ["rev-parse", "HEAD"]),
             "Actual working tree:\n" + (git_text(ws.root, ["status", "--short"]) or "clean"),
             "Next Agent: read .production/WORKSPACE.json, .production/HANDOFF.md, then the focus game's .production/ and design/.",
             "Re-probe this device (`gcp.py env`), verify asset sync and run a smoke test. No commands from records were executed."]
    if check:
        lines.append("Handoff check: " + ("COMPLETE" if not problems else "INCOMPLETE\n- " + "\n- ".join(problems)))
    return "\n".join(lines), problems


# ---------------------------------------------------------------- CLI

def split_list(value: Optional[str]) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def init_creation(root: Path) -> List[str]:
    """Install this Skill into a delivered Creator Base workspace; never creates Base records."""
    root = root.resolve()
    if root == KIT_ROOT or KIT_ROOT in root.parents:
        raise ValueError("Select the Base workspace root, not the Skill folder or its child.")
    ws = Workspace(root)
    if not ws.entries("bases"):
        raise ValueError("The workspace has no Base. Deliver one with game-reverse-engineering first.")
    planned = install_plan(root)
    for destination, data in planned:
        if destination.exists() and (not destination.is_file() or not same_text_bytes(destination.read_bytes(), data)):
            raise ValueError("Installed Skill differs; review and merge manually: " + str(destination))
    added = sum(1 for destination, data in planned if create_new(destination, data))
    messages = ["Skill files added: %d (identical existing files kept)" % added]
    for item in ws.entries("bases"):
        base = ws.load_base(item["id"])
        version = base.get("current_version", "")
        blockers = handoff_problems(ws, item["id"], version)
        messages.append("Base %s@%s: %s" % (item["id"], version, "creator handoff OK" if not blockers else blockers[0]))
    if not (root / ".production/local/ENVIRONMENT.json").exists():
        probe_environment(root)
    messages += ensure_agents_and_ignore(root)
    messages.append("Next: read the Base START_HERE and BASE_HANDOFF, then `gcp.py game create --base <id> --user-request \"<the user's words>\"`.")
    return messages


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, help_text):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--project", required=True, type=Path, help="Creator Base workspace root")
        return command

    add("init", "Install this Skill into a delivered Creator Base workspace (no Base records are created)")
    p = add("game", "Create / stage / update / rebind a game")
    p.add_argument("action", choices=("create", "stage", "update", "rebind"))
    p.add_argument("--id", required=True)
    p.add_argument("--base", default="", help="base-id or base-id@version")
    p.add_argument("--title", default="")
    p.add_argument("--brief", default="")
    p.add_argument("--path")
    p.add_argument("--user-request", default="", help="quote the user's explicit request for this game")
    p.add_argument("--adopt-existing", action="store_true")
    p.add_argument("--stage", choices=GAME_STAGES)
    p.add_argument("--status", choices=STAGE_STATUSES)
    p.add_argument("--note", default="")
    p.add_argument("--readiness", choices=GAME_LEVELS)
    p.add_argument("--publication-status", choices=PUB_STATUSES)
    p.add_argument("--next-action")
    p.add_argument("--task")
    p.add_argument("--assign-agent")
    p.add_argument("--assign-stages", default="")
    p.add_argument("--clear-assignment", action="store_true")
    p.add_argument("--artifact")
    p.add_argument("--retrospective")
    p = add("focus", "Switch the current Base / game / stage / task")
    for option in ("--base", "--game", "--stage", "--task"):
        p.add_argument(option)
    p = add("scope", "Record the user-authorized game target (prevents silent scope growth)")
    p.add_argument("--target", choices=("game", "batch", "full_pipeline"), required=True)
    p.add_argument("--basis", required=True)
    p.add_argument("--game-quota", type=int)
    p.add_argument("--games", default="")
    p.add_argument("--required-readiness", choices=GAME_LEVELS[1:])
    p.add_argument("--mode", choices=RUN_MODES)
    p.add_argument("--allowed-stages", default="")
    p = add("run", "Record run status; TARGET_REACHED is refused until evidence supports it")
    p.add_argument("--status", choices=RUN_STATUSES, required=True)
    p.add_argument("--reason", default="")
    p = add("env", "Re-probe this device into ignored .production/local/ENVIRONMENT.json")
    p.add_argument("--device-label")
    p = add("status", "Print Base handoff and game status (read-only)")
    p.add_argument("--game")
    p = add("validate", "Validate game records, evidence, readiness claims and isolation (NOT game/legal quality)")
    p.add_argument("--game")
    p.add_argument("--strict-target", action="store_true")
    p = add("handoff", "Print a read-only handoff summary; --check verifies completeness")
    p.add_argument("--game")
    p.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.project
        if args.command == "init":
            output = init_creation(root)
        elif args.command == "validate":
            errors, warnings = validate_workspace(root, args.strict_target, args.game)
            for line in warnings:
                print("NOTE: " + line)
            for line in errors:
                print("ERROR: " + line)
            print("RECORD_CHECK_FAILED" if errors else "RECORD_CHECK_PASSED - not a gameplay/art/legal verdict")
            return 1 if errors else 0
        elif args.command == "env":
            Workspace(root)
            env = probe_environment(root.resolve(), args.device_label)
            output = ["Device facts refreshed (local only): %s, python %s, git %s" % (env["os"], env["tools"]["python"], env["tools"]["git"]),
                      "Shared records unchanged. Re-verify dependencies, asset sync and a smoke test before continuing."]
        else:
            ws = Workspace(root)
            if args.command == "game":
                if args.action == "create":
                    if not args.base:
                        raise ValueError("game create needs --base base-id[@version]")
                    output = game_create(ws, args.id, args.base, args.title, args.brief, args.path, args.user_request, args.adopt_existing)
                elif args.action == "stage":
                    if not args.stage or not args.status:
                        raise ValueError("game stage needs --stage and --status")
                    output = game_stage(ws, args.id, args.stage, args.status, args.note)
                elif args.action == "rebind":
                    output = game_rebind(ws, args.id, args.base)
                else:
                    output = game_update(ws, args.id, args.readiness, args.publication_status, args.next_action, args.task,
                                         args.assign_agent, split_list(args.assign_stages), args.clear_assignment,
                                         args.artifact, args.retrospective)
            elif args.command == "focus":
                output = set_focus(ws, None, args.base, args.game, args.stage, args.task)
            elif args.command == "scope":
                output = set_scope(ws, args.target, args.basis, args.game_quota, split_list(args.games),
                                   args.required_readiness, args.mode, split_list(args.allowed_stages))
            elif args.command == "run":
                output = set_run_status(ws, args.status, args.reason)
            elif args.command == "status":
                output = [status_report(ws, args.game)]
            else:
                report, problems = handoff_report(ws, args.game, args.check)
                print(report)
                return 1 if args.check and problems else 0
        for line in output:
            print(line)
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
