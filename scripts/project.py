#!/usr/bin/env python3
"""Local workflow records for Game Production v4. Python 3.9+, standard library only.

Keeps workspace / reusable-base / per-game records. Never runs a game or build,
installs packages, launches agents, commits, pushes or deploys. Validation checks
records, evidence bytes, readiness claims and path isolation; it does not judge
gameplay quality, art quality or legal clearance.
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
KIT_VERSION = "4.1.0"
SCHEMA_VERSION = "3.0"
LEGACY_SCHEMA_VERSION = "2.0"
SKILL_PATH = ".agents/skills/game-production"
WORKSPACE_FILE = ".production/WORKSPACE.json"
LEGACY_SKILL_PATH = ".agents/skills/totop-game-production"
LEGACY_AGENTS_MARKERS = ("TOTOP_GAME_PRODUCTION_V2_BEGIN", "TOTOP_GAME_PRODUCTION_V1_BEGIN")
AGENTS_V4 = ("<!-- GAME_PRODUCTION_V4_BEGIN -->", "<!-- GAME_PRODUCTION_V4_END -->")
AGENTS_V3 = ("<!-- GAME_PRODUCTION_V3_BEGIN -->", "<!-- GAME_PRODUCTION_V3_END -->")
IGNORE_MARKERS = ("# GAME_PRODUCTION_V4_LOCAL", "# GAME_PRODUCTION_V3_LOCAL")
IGNORE_BLOCK = "# GAME_PRODUCTION_V4_LOCAL\n.production/local/\n"
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

BASE_LEVELS = ["NONE", "RESEARCH_READY", "BASE_READY", "COMMERCIAL_BASE_CANDIDATE"]
# (level, gates that must be PASS or scoped NOT_APPLICABLE, gates that must be strictly PASS); cumulative.
BASE_REQUIREMENTS = [
    ("RESEARCH_READY", {"B01"}, set()),
    ("BASE_READY", {"B03", "B04", "B05", "B06", "B07", "B08"}, set()),
    ("COMMERCIAL_BASE_CANDIDATE", {"B02"}, {"B02"}),
]
BASE_GATE_IDS = {"B%02d" % i for i in range(1, 9)}

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
    ".production/RIGHTS_LEDGER.md": "RIGHTS_LEDGER.md",
    "design/GAME_DESIGN.md": "game/GAME_DESIGN.md",
    "design/ART_DIRECTION.md": "game/ART_DIRECTION.md",
    "design/ART_ASSET_PLAN.md": "game/ART_ASSET_PLAN.md",
    "design/ANIMATION_SPEC.md": "game/ANIMATION_SPEC.md",
    "design/RELEASE_CHECKLIST.md": "game/RELEASE_CHECKLIST.md",
}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
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


def check_version(value: str) -> str:
    if not isinstance(value, str) or not VERSION_RE.fullmatch(value):
        raise ValueError("Version must look like 1.0.0: " + repr(value))
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


def installed_skill_intact(skill_dir: Path) -> Tuple[bool, str]:
    """True only when an installed copy matches its own SHA256SUMS and has no extra local files."""
    if not (skill_dir / "SHA256SUMS.txt").is_file():
        return False, "installed Skill has no SHA256SUMS.txt; local changes cannot be ruled out"
    listed = {"SHA256SUMS.txt"}
    try:
        for relative, sha in kit_manifest(skill_dir):
            path = safe_path(skill_dir, relative)
            if not path.is_file() or manifest_bytes(path, sha) is None:
                return False, "installed Skill file changed or missing: " + relative
            listed.add(relative)
    except ValueError as exc:
        return False, str(exc)
    for path in skill_dir.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            relative = path.relative_to(skill_dir).as_posix()
            if relative not in listed:
                return False, "installed Skill has an extra local file: " + relative
    return True, ""


def installed_version(skill_dir: Path) -> str:
    skill = skill_dir / "SKILL.md"
    if skill.is_file():
        match = re.search(r'version:\s*"?([0-9][^"\s]*)', skill.read_text(encoding="utf-8-sig", errors="replace"))
        if match:
            return match.group(1)
    return "unknown"


def check_legacy_blockers(root: Path) -> None:
    if (root / LEGACY_SKILL_PATH).exists():
        raise ValueError("Legacy workflow detected at " + str(root / LEGACY_SKILL_PATH) + "; follow references/MIGRATION_V2.md first.")
    agents = root / "AGENTS.md"
    if agents.is_file() and any(m in agents.read_text(encoding="utf-8-sig") for m in LEGACY_AGENTS_MARKERS):
        raise ValueError("Legacy AGENTS workflow block detected; migrate v2 rules first using references/MIGRATION_V2.md.")


def ensure_agents_and_ignore(root: Path, archive_dir: Optional[Path] = None) -> List[str]:
    messages = []
    agents = safe_path(root, "AGENTS.md")
    existing = agents.read_text(encoding="utf-8-sig") if agents.exists() else ""
    block = template("AGENTS.block.md").read_text(encoding="utf-8").rstrip("\n")
    if AGENTS_V4[0] in existing:
        messages.append("Kept existing v4 AGENTS guide.")
    elif AGENTS_V3[0] in existing and AGENTS_V3[1] in existing:
        if archive_dir is not None:
            create_new(archive_dir / "AGENTS.md.before-v4", agents.read_bytes())
        start = existing.index(AGENTS_V3[0])
        end = existing.index(AGENTS_V3[1]) + len(AGENTS_V3[1])
        agents.write_bytes((existing[:start] + block + existing[end:]).encode("utf-8"))
        messages.append("Replaced only the v3 Game Production block in AGENTS.md; other instructions retained.")
    else:
        append_text(agents, ("\n\n" if existing else "") + block + "\n")
        messages.append("Appended v4 AGENTS guide; existing instructions retained. Review any conflicts.")
    ignores = safe_path(root, ".gitignore")
    current = ignores.read_text(encoding="utf-8-sig") if ignores.exists() else ""
    if not any(marker in current for marker in IGNORE_MARKERS):
        append_text(ignores, ("\n" if current and not current.endswith("\n") else "") + IGNORE_BLOCK)
        messages.append("Added .production/local/ to .gitignore (device facts, not shared).")
    return messages


def probe_environment(root: Path, label: Optional[str] = None) -> Dict[str, Any]:
    """Refresh device-local facts only. Never touches shared workspace/base/game records."""
    path = safe_path(root, ".production/local/ENVIRONMENT.json")
    env = load_json(path) if path.is_file() else load_json(template("ENVIRONMENT.local.json"))
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
            if (self.root / ".production/PROJECT.json").is_file():
                raise ValueError("This is a v3 single-game workspace. Run `project.py migrate` first (references/MIGRATION_V3.md).")
            raise ValueError("No v4 workspace here. Run `project.py init --project <root>` first.")
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

    def load_base(self, bid: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        folder = self.base_dir(bid)
        return load_json(folder / "BASE.json"), load_json(folder / "GATES.json")

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
            raise ValueError(gid + " is a migrated v3 game; its records stay in v3 format (.production/STATE.json, GATES.json).")
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


def base_level_problems(ws: Workspace, bid: str, version: str, level: str,
                        loaded: Optional[Tuple[Dict[str, Any], Dict[str, Any]]] = None) -> List[str]:
    target = level_index(BASE_LEVELS, level)
    if target == 0:
        return []
    base, gates = loaded or ws.load_base(bid)
    by_id = gates_by_id(gates)
    problems = []
    strict_all = set().union(*(strict for _, _, strict in BASE_REQUIREMENTS[:target]))
    for name, required, _ in BASE_REQUIREMENTS[:target]:
        for gid in sorted(required):
            problem = gate_problem(by_id.get(gid), ws.root, version, gid in strict_all)
            if problem:
                problems.append("%s %s (needed for %s)" % (gid, problem, name))
        if name == "BASE_READY" and by_id.get("B02", {}).get("status") == "FAIL":
            problems.append("B02 source/rights review is FAIL; a Base with known unusable code is not BASE_READY")
    return problems


def derive_base_level(ws: Workspace, bid: str, version: str, loaded=None) -> str:
    result = "NONE"
    for level in BASE_LEVELS[1:]:
        if base_level_problems(ws, bid, version, level, loaded):
            break
        result = level
    return result


def base_effective(ws: Workspace, bid: str, version: str) -> str:
    """Recorded claim for a version; the current version is also capped by live gate evidence."""
    base, gates = ws.load_base(bid)
    entry = version_entry(base, version)
    if entry is None:
        raise ValueError("Base %s has no version %s" % (bid, version))
    claim = entry.get("readiness") if entry.get("readiness") in BASE_LEVELS else "NONE"
    if version == base.get("current_version"):
        derived = derive_base_level(ws, bid, version, (base, gates))
        return BASE_LEVELS[min(level_index(BASE_LEVELS, claim), level_index(BASE_LEVELS, derived))]
    return claim


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
        base, _ = ws.load_base(bid)
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
        try:
            effective = base_effective(ws, text(binding.get("base_id")), version)
        except ValueError as exc:
            effective = "NONE"
            problems.append(str(exc))
        if level_index(BASE_LEVELS, effective) < BASE_LEVELS.index("BASE_READY"):
            problems.append("bound Base %s@%s is %s; GAME_READY needs a BASE_READY Base" % (binding.get("base_id"), version, effective))
        if target >= GAME_LEVELS.index("PUBLICATION_APPROVED") and effective != "COMMERCIAL_BASE_CANDIDATE":
            problems.append("bound Base %s@%s lacks commercial code-source clearance (COMMERCIAL_BASE_CANDIDATE)" % (binding.get("base_id"), version))
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


def init_workspace(root: Path, name: Optional[str] = None, target: str = "full_pipeline",
                   references: Optional[List[str]] = None, quota: Optional[int] = None,
                   basis: str = "") -> List[str]:
    root = root.resolve()
    if root == KIT_ROOT or KIT_ROOT in root.parents:
        raise ValueError("Select the workspace/game root, not the Skill folder or its child.")
    if root.exists() and not root.is_dir():
        raise ValueError("Project is not a directory: " + str(root))
    check_legacy_blockers(root)
    workspace_path = root / WORKSPACE_FILE
    if not workspace_path.exists() and (root / ".production/PROJECT.json").exists():
        raise ValueError("v3 single-game records found. Run `project.py migrate` (references/MIGRATION_V3.md); init will not create a second state model.")
    agents = root / "AGENTS.md"
    if agents.is_file() and AGENTS_V3[0] in agents.read_text(encoding="utf-8-sig") and not workspace_path.exists():
        raise ValueError("v3 AGENTS block found. Run `project.py migrate` so the old block is replaced, not duplicated.")
    for path in (root / "AGENTS.md", root / ".gitignore"):
        if path.exists() and not path.is_file():
            raise ValueError("Expected text file: " + str(path))
    planned = install_plan(root)
    for destination, data in planned:
        if destination.exists() and (not destination.is_file() or not same_text_bytes(destination.read_bytes(), data)):
            raise ValueError("Installed Skill differs; use `migrate` for v3 copies or merge manually: " + str(destination))
    scope = new_scope(target, basis or "init --target " + target, quota)
    root.mkdir(parents=True, exist_ok=True)
    messages = []
    added = sum(1 for destination, data in planned if create_new(destination, data))
    messages.append("Skill files added: %d (identical existing files kept)" % added)
    workspace = load_json(template("WORKSPACE.json"))
    workspace["workspace_id"] = "ws-" + uuid.uuid4().hex[:12]
    workspace["name"] = name or root.name
    workspace["run"]["scope"] = scope
    if references:
        workspace["research"] = [{"id": "research-01", "sources": list(references),
                                  "records": ".production/research/research-01"}]
        workspace["focus"]["research"] = "research-01"
        workspace["intake"]["route"] = "new_research"
    defaults = {
        WORKSPACE_FILE: json_bytes(workspace),
        ".production/BACKLOG.md": template("BACKLOG.md").read_bytes(),
        ".production/HANDOFF.md": template("HANDOFF.md").read_bytes(),
        ".production/RIGHTS_LEDGER.md": template("RIGHTS_LEDGER.md").read_bytes(),
    }
    if references:
        defaults[".production/research/research-01/MECHANICS_MATRIX.md"] = template("MECHANICS_MATRIX.md").read_bytes()
    for relative, data in defaults.items():
        created = create_new(safe_path(root, relative), data)
        messages.append(("Created " if created else "Kept existing ") + relative)
    if not (root / ".production/local/ENVIRONMENT.json").exists():
        probe_environment(root)
        messages.append("Probed this device into ignored .production/local/ENVIRONMENT.json")
    messages += ensure_agents_and_ignore(root)
    messages.append("Records only. Next: R0 intake, then research/Base work; no test, quality or legal pass granted.")
    return messages


def migrate_v3(root: Path, game_id: Optional[str] = None, accept_archive: bool = False) -> List[str]:
    """Non-destructive v3 -> v4: keep every v3 record byte-for-byte, register it as one legacy game."""
    root = root.resolve()
    check_legacy_blockers(root)
    if (root / WORKSPACE_FILE).exists():
        raise ValueError("WORKSPACE.json already exists; this workspace is already v4.")
    names = ("PROJECT.json", "STATE.json", "GATES.json")
    if not all((root / ".production" / n).is_file() for n in names):
        raise ValueError("No complete v3 record set (.production/PROJECT.json, STATE.json, GATES.json) to migrate.")
    project = load_json(root / ".production/PROJECT.json")
    state = load_json(root / ".production/STATE.json")
    gid = game_id or re.sub(r"[^a-z0-9]+", "-", str(project.get("name", "")).lower()).strip("-")[:48] or "legacy-game"
    check_slug(gid, "Game")
    skill_dir = root / SKILL_PATH
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = root / ".production/archive" / ("v3-to-v4-" + stamp)
    messages = []
    if skill_dir.exists():
        intact, reason = installed_skill_intact(skill_dir)
        if not intact and not accept_archive:
            raise ValueError("Installed Skill has local changes (" + reason + "). Review them; rerun with --accept-archive to archive the old copy and continue.")
    planned = install_plan(root)
    archive.mkdir(parents=True, exist_ok=False)
    if skill_dir.exists():
        old_version = installed_version(skill_dir)
        copy = archive / ("skill-" + old_version)
        shutil.copytree(str(skill_dir), str(copy))
        originals = sorted(p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob("*") if p.is_file())
        copied = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file())
        if originals != copied:
            raise ValueError("Archive copy incomplete; nothing removed: " + str(copy))
        shutil.rmtree(str(skill_dir))
        messages.append("Archived previous Skill %s to %s (not auto-discovered)." % (old_version, copy.relative_to(root).as_posix()))
    for destination, data in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    messages.append("Installed Skill " + KIT_VERSION)
    run = state.get("run", {}) if isinstance(state.get("run"), dict) else {}
    target_map = {"release_candidate": "game", "mechanics_handoff": "game", "creator_base": "base", "research_handoff": "research"}
    workspace = load_json(template("WORKSPACE.json"))
    workspace["workspace_id"] = str(project.get("project_id") or "ws-" + uuid.uuid4().hex[:12])
    workspace["name"] = str(project.get("name") or root.name)
    workspace["intake"] = {"status": "DONE", "route": "adopt_existing", "notes": "Migrated from v3 single-game records."}
    workspace["games"] = [{"id": gid, "path": ".", "records": ".production", "layout": "v3_legacy"}]
    workspace["focus"].update(game=gid, stage=run.get("current_stage") if run.get("current_stage") in LEGACY_STAGES else "")
    workspace["run"].update(mode=run.get("mode") if run.get("mode") in RUN_MODES else "auto",
                            status=run.get("status") if run.get("status") in RUN_STATUSES else "NEW",
                            stop_reason=str(run.get("stop_reason", "")),
                            allowed_stages=ALL_STAGES + LEGACY_STAGES)
    target = target_map.get(project.get("delivery_target"), "game")
    workspace["run"]["scope"] = new_scope(target, "migrated from v3 delivery_target=" + str(project.get("delivery_target")),
                                          quota=1 if target == "game" else 0, games=[gid] if target == "game" else [])
    if isinstance(project.get("permissions"), dict):
        workspace["permissions"] = project["permissions"]
    workspace["next_action"] = str(state.get("next_action") or workspace["next_action"])
    workspace["notes"].append("Legacy game '%s' keeps its v3 records in .production/. Register its engine as a Base only after review." % gid)
    create_new(root / WORKSPACE_FILE, json_bytes(workspace))
    messages.append("Created .production/WORKSPACE.json; v3 PROJECT/STATE/GATES/BACKLOG/HANDOFF/evidence untouched.")
    if not (root / ".production/local/ENVIRONMENT.json").exists():
        probe_environment(root)
    messages += ensure_agents_and_ignore(root, archive)
    messages.append("Next: review whether the existing engine should become a Base (`base register --code-path .`); new games go to games/<id>/.")
    return messages


def research_add(ws: Workspace, rid: str, sources: List[str]) -> List[str]:
    check_slug(rid, "Research")
    if any(r.get("id") == rid for r in ws.entries("research")):
        raise ValueError("Research already registered: " + rid)
    records = ws.data["layout"].get("research_records_dir", ".production/research") + "/" + rid
    create_new(safe_path(ws.root, records + "/MECHANICS_MATRIX.md"), template("MECHANICS_MATRIX.md").read_bytes())
    ws.data.setdefault("research", []).append({"id": rid, "sources": list(sources), "records": records})
    ws.data["focus"]["research"] = ws.data["focus"].get("research") or rid
    ws.save()
    return ["Registered research " + rid + " at " + records]


def base_register(ws: Workspace, bid: str, version: str, code_path: str, name: str = "",
                  research_ids: Optional[List[str]] = None) -> List[str]:
    check_slug(bid, "Base")
    check_version(version)
    if any(b.get("id") == bid for b in ws.entries("bases")):
        raise ValueError("Base already registered: " + bid)
    code_root = ws.root if code_path == "." else safe_path(ws.root, code_path)
    for rid in research_ids or []:
        ws.entry("research", rid)
    records = ws.data["layout"].get("base_records_dir", ".production/bases") + "/" + bid
    folder = safe_path(ws.root, records)
    if (folder / "BASE.json").exists():
        raise ValueError("Base records already exist: " + records)
    base = load_json(template("base/BASE.json"))
    base.update(base_id=bid, name=name or bid, code_path=code_path, current_version=version,
                research_ids=list(research_ids or []))
    base["versions"] = [{"version": version, "readiness": "NONE", "frozen": False,
                         "summary": "registered", "created_utc": now_utc()}]
    create_new(folder / "BASE.json", json_bytes(base))
    create_new(folder / "GATES.json", template("base/GATES.json").read_bytes())
    create_new(folder / "CAPABILITIES.md", template("base/CAPABILITIES.md").read_bytes())
    create_new(folder / "RIGHTS_LEDGER.md", template("RIGHTS_LEDGER.md").read_bytes())
    ws.data.setdefault("bases", []).append({"id": bid, "records": records})
    ws.data["focus"]["base"] = ws.data["focus"].get("base") or bid
    ws.save()
    messages = ["Registered Base %s@%s (readiness NONE) records at %s" % (bid, version, records)]
    if not code_root.exists():
        messages.append("NOTE: code_path %s does not exist yet (planned Base)." % code_path)
    return messages


def dependents_needing_regression(ws: Workspace, bid: str) -> List[Tuple[str, str]]:
    base, _ = ws.load_base(bid)
    current = base.get("current_version")
    result = []
    for item in ws.entries("games"):
        if item.get("layout") == "v3_legacy":
            continue
        binding = ws.load_game(item["id"])[0].get("base_binding", {})
        if binding.get("base_id") == bid and binding.get("version") != current:
            result.append((item["id"], str(binding.get("version"))))
    return result


def base_bump(ws: Workspace, bid: str, version: str, summary: str) -> List[str]:
    check_version(version)
    if not text(summary):
        raise ValueError("A version summary (what changed, breaking or not) is required")
    path = ws.base_dir(bid) / "BASE.json"
    base = load_json(path)
    if version_entry(base, version):
        raise ValueError("Version already exists: " + version)
    base.setdefault("versions", []).append({"version": version, "readiness": "NONE", "frozen": False,
                                            "summary": summary, "created_utc": now_utc()})
    base["current_version"] = version
    save_json(path, base)
    messages = ["Base %s current version is now %s (readiness NONE until its gates are re-verified for %s)." % (bid, version, version)]
    for gid, old in dependents_needing_regression(ws, bid):
        messages.append("REGRESSION NEEDED before %s moves to %s: bound to %s@%s" % (gid, version, bid, old))
    return messages


def base_update(ws: Workspace, bid: str, version: Optional[str], readiness: Optional[str],
                freeze: bool = False) -> List[str]:
    path = ws.base_dir(bid) / "BASE.json"
    base = load_json(path)
    version = version or base.get("current_version")
    entry = version_entry(base, version)
    if entry is None:
        raise ValueError("Base %s has no version %s" % (bid, version))
    messages = []
    if readiness:
        if readiness not in BASE_LEVELS:
            raise ValueError("readiness must be one of " + ", ".join(BASE_LEVELS))
        if level_index(BASE_LEVELS, readiness) > level_index(BASE_LEVELS, entry.get("readiness")):
            if version != base.get("current_version"):
                raise ValueError("Only the current version can be raised; older versions are history.")
            problems = base_level_problems(ws, bid, version, readiness)
            if problems:
                raise ValueError("Cannot claim %s for %s@%s:\n- %s" % (readiness, bid, version, "\n- ".join(problems)))
        entry["readiness"] = readiness
        messages.append("%s@%s readiness = %s" % (bid, version, readiness))
    if freeze:
        if level_index(BASE_LEVELS, entry.get("readiness")) < BASE_LEVELS.index("BASE_READY"):
            raise ValueError("Only a BASE_READY (or higher) version can be frozen as a baseline")
        entry["frozen"] = True
        messages.append("%s@%s frozen; further changes need a new version." % (bid, version))
    save_json(path, base)
    return messages


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
    base, _ = ws.load_base(bid)
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
        raise ValueError("A new game cannot use the workspace root; only migrated v3 games live there.")
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
    ws.data.setdefault("games", []).append({"id": gid, "path": relative, "records": relative + "/.production", "layout": "v4"})
    scope.setdefault("games", []).append(gid)
    ws.data["focus"].update(game=gid, base=bid, stage="G1")
    ws.save()
    refresh_dependents(ws, bid)
    messages.append("Created game %s at %s bound to %s@%s; next stage G1 (game design)." % (gid, relative, bid, version))
    effective = base_effective(ws, bid, version)
    if level_index(BASE_LEVELS, effective) < BASE_LEVELS.index("BASE_READY"):
        messages.append("NOTE: %s@%s is %s. Design (G1/G2) may start, but this game cannot become GAME_READY until the Base is BASE_READY." % (bid, version, effective))
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
    base, _ = ws.load_base(bid)
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
        base, _ = ws.load_base(bid)
        effective = base_effective(ws, bid, base.get("current_version"))
        if level_index(BASE_LEVELS, effective) < BASE_LEVELS.index(level):
            return ["Base %s@%s is %s, target needs %s: %s" % (bid, base.get("current_version"), effective, level,
                    "; ".join(base_level_problems(ws, bid, base.get("current_version"), level)[:3]))]
        return []

    def games_ready():
        games = scope.get("games", [])
        if not games:
            return ["no games in the authorized scope yet"]
        found = []
        required = scope.get("required_readiness", "RELEASE_CANDIDATE")
        for gid in games:
            if ws.is_legacy(gid):
                errors, _ = validate_legacy_v3(ws.game_root(gid), strict=True)
                if errors:
                    found.append("%s (v3 records) strict target check: %s" % (gid, errors[0]))
                continue
            derived = derive_game_level(ws, gid)
            if level_index(GAME_LEVELS, derived) < GAME_LEVELS.index(required):
                found.append("%s is %s, needs %s: %s" % (gid, derived, required, "; ".join(game_level_problems(ws, gid, required)[:3])))
        return found

    if target == "research":
        problems += base_at_least("RESEARCH_READY")
    elif target == "base":
        problems += base_at_least("BASE_READY")
    elif target == "full_pipeline":
        problems += base_at_least("BASE_READY") + games_ready()
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

def validate_legacy_v3(root: Path, strict: bool = False) -> Tuple[List[str], List[str]]:
    """v3 single-game record rules, kept so migrated projects keep their evidence checks."""
    root = root.resolve()
    errors: List[str] = []
    warnings: List[str] = []
    objects: Dict[str, Dict[str, Any]] = {}
    for name in ("PROJECT", "STATE", "GATES"):
        try:
            obj = load_json(safe_path(root, ".production/" + name + ".json"))
            objects[name] = obj
            if obj.get("schema_version") != LEGACY_SCHEMA_VERSION:
                errors.append(name + ": unsupported schema_version")
        except ValueError as exc:
            errors.append(str(exc))
    if len(objects) != 3:
        return errors, warnings
    project, state, gates_obj = objects["PROJECT"], objects["STATE"], objects["GATES"]
    if project.get("delivery_target") not in ("release_candidate", "mechanics_handoff", "research_handoff", "creator_base"):
        errors.append("PROJECT.delivery_target is invalid")
    contract = project.get("acceptance_contract")
    if not isinstance(contract, dict):
        errors.append("PROJECT.acceptance_contract must be an object")
    elif strict and contract.get("defined") is not True:
        errors.append("Acceptance contract is not yet defined from the actual project.")
    run = state.get("run")
    if not isinstance(run, dict):
        errors.append("STATE.run must be an object")
    else:
        if run.get("mode") not in RUN_MODES:
            errors.append("STATE.run.mode is invalid")
        if run.get("status") not in RUN_STATUSES:
            errors.append("STATE.run.status is invalid")
        if run.get("current_stage") not in LEGACY_STAGES:
            errors.append("STATE.run.current_stage is invalid")
        allowed = run.get("allowed_stages")
        if not isinstance(allowed, list) or not allowed or any(s not in LEGACY_STAGES for s in allowed):
            errors.append("STATE.run.allowed_stages must be a nonempty list of stages S0..S6")
        elif len(allowed) != len(set(allowed)):
            errors.append("STATE.run.allowed_stages has duplicates")
        if run.get("status") in STOP_STATUSES and not text(run.get("stop_reason")):
            errors.append("Stopping state requires a truthful stop_reason")
    if state.get("publication_status") not in PUB_STATUSES:
        errors.append("STATE.publication_status is invalid")
    gates = gates_obj.get("gates")
    if not isinstance(gates, list):
        return errors + ["GATES.gates must be a list"], warnings
    seen = set()
    required_count = 0
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("Gate entry must be an object")
            continue
        gid = gate.get("id")
        if not isinstance(gid, str) or not re.fullmatch(r"G\d{2,}", gid):
            errors.append("Invalid gate ID: " + repr(gid))
            continue
        if gid in seen:
            errors.append("Duplicate gate ID " + gid)
        seen.add(gid)
        required = gate.get("required_for_target")
        if type(required) is not bool:
            errors.append(gid + ": required_for_target must be boolean")
        if required is True:
            required_count += 1
        reviewer = gate.get("reviewer") if isinstance(gate.get("reviewer"), dict) else {}
        errors += check_gate_entry(gate, gid, root, False,
                                   gid == "G10" and reviewer.get("independence") == "external_approval")
        if strict and required is True and gate.get("status") not in ("PASS", "NOT_APPLICABLE"):
            errors.append(gid + ": required target gate is " + str(gate.get("status")))
    missing = {"G%02d" % i for i in range(1, 11)} - seen
    if missing:
        errors.append("Missing default gates (use explicit scope, not deletion): " + ", ".join(sorted(missing)))
    if strict and required_count == 0:
        errors.append("No required target gates: do not silently remove acceptance requirements")
    snapshot = state.get("snapshot", {})
    if not isinstance(snapshot, dict):
        errors.append("STATE.snapshot must be an object")
    elif snapshot.get("artifact_path"):
        try:
            artifact = safe_path(root, snapshot["artifact_path"])
            sha = snapshot.get("artifact_sha256", "")
            if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
                errors.append("Candidate artifact requires SHA-256")
            elif not artifact.is_file() or digest(artifact) != sha.lower():
                errors.append("Candidate artifact missing or SHA-256 does not match")
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    for name in ("BACKLOG.md", "HANDOFF.md", "RIGHTS_LEDGER.md"):
        if not (root / ".production" / name).is_file():
            errors.append("Missing project record: " + name)
    warnings.append("v3 single-game records: valid for continuation; new games and Bases need the v4 workspace (`migrate`).")
    return errors, warnings


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


def validate_base(ws: Workspace, bid: str) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    label = "Base " + bid
    try:
        base, gates = ws.load_base(bid)
    except ValueError as exc:
        return [label + ": " + str(exc)], warnings
    if base.get("schema_version") != SCHEMA_VERSION:
        errors.append(label + ": BASE.json unsupported schema_version")
    if base.get("base_id") != bid:
        errors.append(label + ": BASE.json base_id does not match the registry")
    try:
        code = base.get("code_path", "")
        code_root = ws.root if code == "." else safe_path(ws.root, code)
        if not code_root.exists():
            warnings.append(label + ": code_path %s does not exist yet" % code)
    except ValueError as exc:
        errors.append(label + ": code_path " + str(exc))
    versions = base.get("versions")
    seen = set()
    if not isinstance(versions, list) or not versions:
        errors.append(label + ": versions must be a nonempty list")
        versions = []
    for entry in versions:
        version = entry.get("version") if isinstance(entry, dict) else None
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version) or version in seen:
            errors.append(label + ": invalid or duplicate version entry " + repr(version))
            continue
        seen.add(version)
        if entry.get("readiness") not in BASE_LEVELS:
            errors.append(label + "@" + version + ": invalid readiness")
        if entry.get("frozen") is True and level_index(BASE_LEVELS, entry.get("readiness")) < BASE_LEVELS.index("BASE_READY"):
            errors.append(label + "@" + version + ": frozen baseline must be at least BASE_READY")
    current = base.get("current_version")
    if current not in seen:
        errors.append(label + ": current_version is not in versions")
    errors += check_gate_file(gates, BASE_GATE_IDS, ws.root, label + " GATES", BASE_GATE_IDS, set())
    if current in seen and not errors:
        claim = version_entry(base, current).get("readiness")
        derived = derive_base_level(ws, bid, current, (base, gates))
        if level_index(BASE_LEVELS, claim) > level_index(BASE_LEVELS, derived):
            problems = base_level_problems(ws, bid, current, claim, (base, gates))
            errors.append("%s@%s claims %s but evidence supports %s: %s" % (label, current, claim, derived, problems[0] if problems else ""))
    stale = dependents_needing_regression(ws, bid) if not errors else []
    for gid, old in stale:
        warnings.append("%s: game %s still bound to %s; regression needed before moving to %s" % (label, gid, old, current))
    if stale and gates_by_id(gates).get("B08", {}).get("status") == "NOT_APPLICABLE":
        warnings.append(label + ": B08 is NOT_APPLICABLE although games depend on other versions; re-check compatibility")
    return errors, warnings


def validate_game(ws: Workspace, gid: str, strict: bool = False) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    label = "Game " + gid
    if ws.is_legacy(gid):
        legacy_errors, legacy_warnings = validate_legacy_v3(ws.game_root(gid), strict)
        return [label + " (v3): " + e for e in legacy_errors], [label + " (v3): " + w for w in legacy_warnings]
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
        base, _ = ws.load_base(text(binding.get("base_id")))
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
        if (root / ".production/PROJECT.json").is_file():
            errors, warnings = validate_legacy_v3(root, strict)
            return errors, warnings + ["Run `project.py migrate` to enable Bases and multiple games."]
        return ["No workspace records here (.production/WORKSPACE.json)."], []
    try:
        ws = Workspace(root)
    except ValueError as exc:
        return [str(exc)], []
    errors, warnings = [], []
    data = ws.data
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("WORKSPACE: unsupported schema_version")
    if data.get("kit_version") != KIT_VERSION:
        warnings.append("WORKSPACE kit_version %s differs from tool %s; review migration notes." % (data.get("kit_version"), KIT_VERSION))
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
        base_errors, base_warnings = validate_base(ws, item["id"])
        errors += base_errors
        warnings += base_warnings
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
    for item in ws.entries("research"):
        lines.append("Research %s: %s" % (item.get("id"), ", ".join(item.get("sources", [])) or "(no sources)"))
    for item in ws.entries("bases"):
        base, gates = ws.load_base(item["id"])
        current = base.get("current_version")
        versions = ", ".join("%s=%s%s" % (v.get("version"), v.get("readiness"), "(frozen)" if v.get("frozen") else "")
                             for v in base.get("versions", []) if isinstance(v, dict))
        derived = derive_base_level(ws, item["id"], current, (base, gates))
        lines.append("Base %s current=%s evidence-supports=%s versions: %s" % (item["id"], current, derived, versions))
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
    elif ws.run.get("status") in STOP_STATUSES + ("HANDOFF_READY",) and workspace_handoff.read_bytes() == template("HANDOFF.md").read_bytes():
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
             "Re-probe this device (`project.py env`), verify asset sync and run a smoke test. No commands from records were executed."]
    if check:
        lines.append("Handoff check: " + ("COMPLETE" if not problems else "INCOMPLETE\n- " + "\n- ".join(problems)))
    return "\n".join(lines), problems


# ---------------------------------------------------------------- CLI

def split_list(value: Optional[str]) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, help_text):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--project", required=True, type=Path, help="workspace root")
        return command

    p = add("init", "Create a v4 workspace (install Skill, records); never overwrites files")
    p.add_argument("--name")
    p.add_argument("--target", choices=TARGETS, default="full_pipeline")
    p.add_argument("--game-quota", type=int)
    p.add_argument("--reference", action="append", default=[], help="reference game/repo URL (repeatable)")
    p.add_argument("--basis", default="", help="the user's instruction defining the scope")
    p = add("migrate", "Upgrade a v3 single-game project without changing its records")
    p.add_argument("--game-id")
    p.add_argument("--accept-archive", action="store_true", help="archive a locally modified old Skill copy and continue")
    p = add("research", "Register a research topic and its sources")
    p.add_argument("--id", required=True)
    p.add_argument("--source", action="append", default=[])
    p = add("base", "Register / version / update a reusable Base")
    p.add_argument("action", choices=("register", "bump", "update"))
    p.add_argument("--id", required=True)
    p.add_argument("--version")
    p.add_argument("--code-path", default="")
    p.add_argument("--name", default="")
    p.add_argument("--research", default="", help="comma-separated research IDs")
    p.add_argument("--summary", default="")
    p.add_argument("--readiness", choices=BASE_LEVELS)
    p.add_argument("--freeze", action="store_true")
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
    p = add("focus", "Switch the current research / Base / game / stage / task")
    for option in ("--research", "--base", "--game", "--stage", "--task"):
        p.add_argument(option)
    p = add("scope", "Record the user-authorized target (prevents silent scope growth)")
    p.add_argument("--target", choices=TARGETS, required=True)
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
    p = add("status", "Print workspace, Base and game status (read-only)")
    p.add_argument("--game")
    p = add("validate", "Validate records, evidence, readiness claims and isolation (NOT game/legal quality)")
    p.add_argument("--game")
    p.add_argument("--strict-target", action="store_true")
    p = add("handoff", "Print a read-only handoff summary; --check verifies completeness")
    p.add_argument("--game")
    p.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.project
        if args.command == "init":
            output = init_workspace(root, args.name, args.target, args.reference, args.game_quota, args.basis)
        elif args.command == "migrate":
            output = migrate_v3(root, args.game_id, args.accept_archive)
        elif args.command == "validate":
            errors, warnings = validate_workspace(root, args.strict_target, args.game)
            for line in warnings:
                print("NOTE: " + line)
            for line in errors:
                print("ERROR: " + line)
            print("RECORD_CHECK_FAILED" if errors else "RECORD_CHECK_PASSED — not a gameplay/art/legal verdict")
            return 1 if errors else 0
        elif args.command == "env":
            Workspace(root)
            env = probe_environment(root.resolve(), args.device_label)
            output = ["Device facts refreshed (local only): %s, python %s, git %s" % (env["os"], env["tools"]["python"], env["tools"]["git"]),
                      "Shared records unchanged. Re-verify dependencies, asset sync and a smoke test before continuing."]
        else:
            ws = Workspace(root)
            if args.command == "research":
                output = research_add(ws, args.id, args.source)
            elif args.command == "base":
                if args.action == "register":
                    if not args.version or not args.code_path:
                        raise ValueError("base register needs --version and --code-path")
                    output = base_register(ws, args.id, args.version, args.code_path, args.name, split_list(args.research))
                elif args.action == "bump":
                    output = base_bump(ws, args.id, args.version or "", args.summary)
                else:
                    output = base_update(ws, args.id, args.version, args.readiness, args.freeze)
            elif args.command == "game":
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
                output = set_focus(ws, args.research, args.base, args.game, args.stage, args.task)
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
