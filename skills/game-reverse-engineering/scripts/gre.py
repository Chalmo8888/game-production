#!/usr/bin/env python3
"""Game Reverse Engineering Skill tool. Python 3.9+, standard library only.

Keeps the reverse-engineering and Base-building records of a shared production
workspace (schema 3.0): capability parity matrix (with game-specific discovery and
PARITY / REPLACEMENT / EXTENSION classes), reuse assessment, presentation research
and experiments, Creator probes, creator gates (decoupling, creator kit, clean
first-use, independent reuse), delivery levels (LOGIC_READY / PRESENTATION_READY /
CREATOR_CANDIDATE / CREATOR_READY), value-ranked next tasks, timeouts, checkpoints,
an append-only history and the creator handoff export read by game-creation-polish.
Never runs games, decompilers, builds or untrusted scripts; never commits, pushes
or deploys. Validation checks records, evidence bytes, code fingerprints and
claims; it does not judge gameplay quality, art quality or legal clearance.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Dict, List, Optional, Tuple

KIT_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "game-reverse-engineering"
SKILL_VERSION = "2.0.0"
GRE_SCHEMA = "gre-1.0"
WORKSPACE_SCHEMA = "3.0"
SKILL_PATH = ".agents/skills/" + SKILL_NAME
WORKSPACE_FILE = ".production/WORKSPACE.json"
RE_DIRNAME = "re"
AGENTS_MARKERS = ("<!-- GAME_REVERSE_ENGINEERING_V1_BEGIN -->", "<!-- GAME_REVERSE_ENGINEERING_V1_END -->")
IGNORE_MARKER = "# GAME_REVERSE_ENGINEERING_LOCAL"
IGNORE_BLOCK = IGNORE_MARKER + "\n.production/local/\nresearch-private/\n"
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|\\\\[A-Za-z0-9_.$-]+\\|(?<![\w.])/(?:Users|home)/[^\s\"'`)]+")
UNFILLED_MARKER = "TEMPLATE_UNFILLED"
RESEARCH_PRIVATE = "research-private"

LEVELS = ["NONE", "LOGIC_READY", "PRESENTATION_READY", "CREATOR_CANDIDATE", "CREATOR_READY"]
GROUP_LEVEL = {"logic": "LOGIC_READY", "presentation": "PRESENTATION_READY", "creator": "CREATOR_READY"}
GROUP_MIN_LEVEL = {"logic": "LOGIC_READY", "presentation": "PRESENTATION_READY", "creator": "CREATOR_CANDIDATE"}
DOMAIN_GROUP = {d: "logic" for d in ("L1", "L2", "L3", "L4", "L5", "L6")}
DOMAIN_GROUP.update({d: "presentation" for d in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8")})
DOMAIN_GROUP["C1"] = "creator"
OPTIONAL_DOMAINS = {"L3", "L4"}
GAMEPLAY_DOMAINS = {"L1", "L2", "L3", "L4", "L5", "C1"}
ITEM_STATUSES = ["NOT_STARTED", "RESEARCHING", "INTERFACE_ONLY", "DOCUMENTED", "IMPLEMENTED", "VERIFIED", "NOT_APPLICABLE"]
NON_COUNTING = {"INTERFACE_ONLY", "DOCUMENTED"}
APPROACHES = ["UNDECIDED", "REUSE", "ADAPT", "REIMPLEMENT", "IMPROVE", "OMIT"]
EVIDENCE_LEVELS = ["VERIFIED", "STATIC_ONLY", "INFERRED", "PROXY", "UNKNOWN"]
SCOPES = ["core", "optional", "legacy", "excluded"]
CLASSES = ["PARITY", "REPLACEMENT", "EXTENSION"]
ORIGINS = ["template", "discovered", "extension"]
DISCOVERY_SOURCES = ["code", "runtime", "assets"]
DISCOVERY_STATUSES = ["PENDING", "DONE", "UNAVAILABLE"]
DYNAMIC_KINDS = {"runtime-capture", "trace", "comparison", "measurement", "recording"}
VERIFY_KINDS = {"test", "runtime-capture", "measurement", "trace", "benchmark", "comparison", "recording"}
VISUAL_KINDS = {"runtime-capture", "measurement", "recording", "comparison"}
RUNTIME_KINDS = VISUAL_KINDS | {"test"}
REUSE_DECISIONS = ["KEEP", "ADAPT", "REPLACE", "QUARANTINE", "REVIEW"]
SOURCE_KINDS = ["original_decompiled", "original_source", "open_source", "own_code", "third_party_library", "generated"]
EXECUTION_POLICIES = ["never", "sandboxed", "reviewed"]
FOREIGN_SOURCES = {"original_decompiled", "original_source", "open_source", "third_party_library"}
TASK_KINDS = ["research", "build", "verify", "fix", "polish", "docs"]
LOW_VALUE_KINDS = {"polish", "docs"}
TASK_RESULTS = ["ok", "failed", "blocked"]
REVIEW_MODES = ("self_review", "separate_context_same_environment", "independent_reviewer", "external_approval")
APPROVAL_ROLES = {"RE02": {"user"}, "RE03": {"rights_holder", "rights_holder_counsel"}}
GATE_IDS = ("RE01", "RE02", "RE03")
GATE_STATUSES = ("PASS", "FAIL", "UNVERIFIED", "BLOCKED", "NOT_APPLICABLE")
PROBE_CATEGORIES = ["character", "animation", "unit", "map", "visual_style"]
LOOP_STEPS = ["start", "play", "end", "result", "restart"]
COST_SCORE = {"S": 2, "M": 1, "L": 0}
DEFAULT_GUARDS = {"research_streak_limit": 6, "polish_streak_limit": 5, "same_failure_limit": 3,
                  "research_budget_per_item": 3, "neglect_limit": 8, "high_priority_score": 10}
EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".cache", ".venv"}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
ITEM_ID_RE = re.compile(r"(L[1-6]|P[1-8]|C1)-\d{2,}")
RESIDUAL_RISK = "Not legal advice; residual rights risk is never zero."


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
    win_path = PureWindowsPath(relative)
    path = PurePosixPath(relative.replace("\\", "/"))
    if path.is_absolute() or win_path.drive or win_path.root or ".." in path.parts:
        raise ValueError("absolute paths and '..' are not allowed: " + relative)
    resolved = (root / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path escapes its root (possibly symlink): " + relative) from exc
    return resolved


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


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
    """Exclusive create; never overwrite an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as out:
            out.write(data)
        return True
    except FileExistsError:
        return False


def append_text(path: Path, addition: str) -> None:
    existing = path.read_bytes() if path.exists() else b""
    path.write_bytes(existing + addition.encode("utf-8"))


def template(relative: str) -> Path:
    return KIT_ROOT / "templates" / relative


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def level_index(value: Any) -> int:
    return LEVELS.index(value) if value in LEVELS else 0


def version_tuple(value: Any) -> Tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", str(value))[:3]) or (0,)


def check_slug(value: str, kind: str) -> str:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        raise ValueError(kind + " ID must be lowercase letters, digits and '-' (max 48): " + repr(value))
    return value


def git_text(root: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root)] + args, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=8)
        return result.stdout.strip() if result.returncode == 0 else "not available (not a repository or command failed)"
    except (OSError, subprocess.SubprocessError):
        return "not available (Git missing or timed out)"


def iter_files(folder: Path):
    if folder.is_file():
        yield folder
        return
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not (set(path.relative_to(folder).parts[:-1]) & EXCLUDED_DIRS):
            yield path


def inside(path: PurePosixPath, folder: PurePosixPath) -> bool:
    return path == folder or folder in path.parents


def strip_kind(spec: str) -> Tuple[str, str]:
    """Split 'path:kind' (kind optional)."""
    if re.match(r"^[A-Za-z]:[\\/]", spec):
        return spec, ""
    path, _, kind = spec.partition(":")
    return path, kind


# ---------------------------------------------------------------- Skill package

def kit_manifest(kit_root: Path = KIT_ROOT) -> List[Tuple[str, str]]:
    entries = []
    for line in (kit_root / "SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})  (.+)", line.strip())
        if not match:
            raise ValueError("Malformed SHA256SUMS line: " + line)
        entries.append((match.group(2), match.group(1).lower()))
    return entries


def manifest_bytes(path: Path, sha: str) -> Optional[bytes]:
    """Bytes matching the manifest; tolerates CRLF checkouts by normalizing to LF."""
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() == sha:
        return data
    normalized = data.replace(b"\r\n", b"\n")
    return normalized if hashlib.sha256(normalized).hexdigest() == sha else None


def install_plan(root: Path) -> List[Tuple[Path, bytes]]:
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


def probe_environment(root: Path, label: Optional[str] = None) -> Dict[str, Any]:
    path = safe_path(root, ".production/local/ENVIRONMENT.json")
    env = load_json(path) if path.is_file() else load_json(template("workspace/ENVIRONMENT.local.json"))
    env["os"] = "%s %s (%s)" % (platform.system(), platform.release(), platform.machine())
    env["probed_utc"] = now_utc()
    env["project_root"] = str(root)
    if label:
        env["device_label"] = label
    tools = env.setdefault("tools", {})
    tools["python"] = platform.python_version()
    version = git_text(root, ["--version"])
    tools["git"] = version if version.startswith("git version") else "missing_or_unavailable"
    save_json(path, env)
    return env


# ---------------------------------------------------------------- evidence and gates

def evidence_entry(root: Path, relative: str, kind: str, observed: str, location: str = "") -> Dict[str, Any]:
    path = safe_path(root, relative)
    if not path.is_file():
        raise ValueError("Evidence file not found: " + relative)
    if not text(kind) or not text(observed):
        raise ValueError("Evidence needs --kind and --observed")
    entry = {"path": rel(root, path), "sha256": digest(path), "kind": kind, "observed": observed, "utc": now_utc()}
    if location:
        entry["location"] = location
    return entry


def check_evidence(evidence: Any, root: Path, label: str, allow_local: bool = False) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    if not isinstance(evidence, list):
        return [label + ": evidence must be a list"], warnings
    for index, item in enumerate(evidence):
        item_label = label + ": evidence[%d] " % index
        if not isinstance(item, dict):
            errors.append(item_label + "must be an object")
            continue
        if not text(item.get("kind")) or not text(item.get("observed")):
            errors.append(item_label + "requires kind and observed result")
        sha = item.get("sha256", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            errors.append(item_label + "requires SHA-256")
            continue
        try:
            path = safe_path(root, item.get("path", ""))
            if not path.is_file():
                if allow_local and item.get("location") == "local_research":
                    warnings.append(item_label + "kept in local research (not synced): " + str(item.get("path")))
                else:
                    errors.append(item_label + "file missing: " + str(item.get("path")))
            elif digest(path) != sha.lower():
                errors.append(item_label + "SHA-256 mismatch (overwritten?): " + str(item.get("path")))
        except (ValueError, OSError) as exc:
            errors.append(item_label + str(exc))
    return errors, warnings


def check_gate(gate: Dict[str, Any], label: str, root: Path) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    gid = gate.get("id")
    approval = gid in APPROVAL_ROLES
    status = gate.get("status")
    if status not in GATE_STATUSES:
        return [label + ": invalid status"], warnings
    if status == "NOT_APPLICABLE":
        if not text(gate.get("scope_basis")):
            errors.append(label + ": NOT_APPLICABLE requires a scope basis")
        if gid == "RE02":
            errors.append(label + ": publication approval cannot be NOT_APPLICABLE; leave it UNVERIFIED until the user approves")
    if status != "PASS":
        return errors, warnings
    if not text(gate.get("criteria")):
        errors.append(label + ": PASS requires concrete criteria")
    if not text(gate.get("subject_revision")):
        errors.append(label + ": PASS requires subject_revision")
    reviewer = gate.get("reviewer") if isinstance(gate.get("reviewer"), dict) else {}
    independence = reviewer.get("independence")
    if not text(reviewer.get("identity")) or independence not in REVIEW_MODES:
        errors.append(label + ": PASS requires reviewer identity and actual independence")
    elif approval and independence != "external_approval":
        errors.append(label + ": this approval must come from outside the Agent (external_approval); technical tests and Agent self-review cannot grant it")
    elif not approval and independence == "external_approval":
        errors.append(label + ": external_approval is reserved for RE02/RE03")
    if approval:
        role = text(reviewer.get("role"))
        if not role:
            (warnings if gid == "RE02" else errors).append(label + ": reviewer.role is required (%s)" % "/".join(sorted(APPROVAL_ROLES[gid])))
        elif role not in APPROVAL_ROLES[gid]:
            errors.append(label + ": role %s cannot grant this; %s" % (role, "the user's publication approval does not replace the original rights holder's grant" if gid == "RE03" else "publication approval comes from the user"))
    evidence = gate.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(label + ": PASS requires evidence files, not only a claim")
    else:
        errors += check_evidence(evidence, root, label)[0]
    return errors, warnings


# ---------------------------------------------------------------- context

class Context:
    """One Base's GRE records inside a shared production workspace."""

    def __init__(self, root: Path, base_id: Optional[str] = None):
        self.root = root.resolve()
        ws_path = self.root / WORKSPACE_FILE
        if not ws_path.is_file():
            if (self.root / ".production/PROJECT.json").is_file():
                raise ValueError("v3 single-game records found (retired format, not supported); convert them with the last single-skill release (commit 9fc83fe) or start a new workspace.")
            raise ValueError("No workspace here. Run `gre.py init --project <root> ...` first.")
        self.workspace = load_json(ws_path)
        bases = [b for b in self.workspace.get("bases", []) if isinstance(b, dict)]
        base_id = base_id or self.workspace.get("focus", {}).get("base") or (bases[0]["id"] if len(bases) == 1 else "")
        entry = next((b for b in bases if b.get("id") == base_id), None)
        if entry is None:
            raise ValueError("Unknown Base %r; pass --base-id" % base_id)
        self.base_id = base_id
        self.base_dir = safe_path(self.root, entry["records"])
        self.re_dir = self.base_dir / RE_DIRNAME
        if not (self.re_dir / "RE_STATE.json").is_file():
            raise ValueError("Base %s has no reverse-engineering records; run `gre.py init --base-id %s` to adopt it." % (base_id, base_id))
        self._fingerprints: Dict[Tuple[str, ...], str] = {}

    def path(self, name: str) -> Path:
        return self.re_dir / name

    def load(self, name: str) -> Dict[str, Any]:
        return load_json(self.path(name))

    def save(self, name: str, obj: Dict[str, Any]) -> None:
        save_json(self.path(name), obj)

    def base(self) -> Dict[str, Any]:
        return load_json(self.base_dir / "BASE.json")

    def current_version(self) -> str:
        return text(self.base().get("current_version"))

    def log(self, event: str, **fields: Any) -> None:
        record = {"utc": now_utc(), "event": event}
        record.update(fields)
        with self.path("HISTORY.jsonl").open("ab") as out:
            out.write((json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8"))

    def history(self) -> List[Dict[str, Any]]:
        path = self.path("HISTORY.jsonl")
        if not path.is_file():
            return []
        events = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    events.append({"event": "CORRUPT", "line": number})
        return events

    def core_paths(self, state: Optional[Dict[str, Any]] = None) -> List[str]:
        state = state or self.load("RE_STATE.json")
        return [p for p in state.get("core_paths", []) if isinstance(p, str)]

    def fingerprint(self, paths: List[str]) -> str:
        key = tuple(sorted(paths))
        if key not in self._fingerprints:
            self._fingerprints[key] = core_fingerprint(self.root, list(key))
        return self._fingerprints[key]


def core_fingerprint(root: Path, core_paths: List[str]) -> str:
    """Hash of every file (path + content) under the given paths. Equal fingerprints mean unchanged code."""
    result = hashlib.sha256()
    entries = []
    for relative in core_paths:
        folder = safe_path(root, relative)
        if not folder.exists():
            continue
        for path in iter_files(folder):
            entries.append((rel(root, path), digest(path)))
    for name, sha in sorted(set(entries)):
        result.update((name + "\0" + sha + "\n").encode("utf-8"))
    return result.hexdigest() if entries else ""


def guards(state: Dict[str, Any]) -> Dict[str, int]:
    merged = dict(DEFAULT_GUARDS)
    merged.update({k: v for k, v in state.get("guards", {}).items() if isinstance(v, int)})
    return merged


# ---------------------------------------------------------------- init / adopt / upgrade

def init(root: Path, base_id: str = "core", version: str = "0.1.0", code_path: str = "",
         core_paths: Optional[List[str]] = None, references: Optional[List[str]] = None,
         name: str = "", target: str = "CREATOR_READY", basis: str = "", agent: str = "",
         starter_paths: Optional[List[str]] = None) -> List[str]:
    root = root.resolve()
    if root == KIT_ROOT or KIT_ROOT in root.parents:
        raise ValueError("Select the workspace root, not the Skill folder.")
    if root.exists() and not root.is_dir():
        raise ValueError("Project is not a directory: " + str(root))
    if (root / ".production/PROJECT.json").is_file() and not (root / WORKSPACE_FILE).is_file():
        raise ValueError("v3 single-game records found (retired format, not supported); convert them with the last single-skill release (commit 9fc83fe) or start a new workspace.")
    if target not in LEVELS[1:]:
        raise ValueError("target must be one of " + ", ".join(LEVELS[1:]))
    check_slug(base_id, "Base")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Version must look like 0.1.0")
    for path in core_paths or []:
        if PurePosixPath(path.replace("\\", "/")).parts[:1] == (RESEARCH_PRIVATE,):
            raise ValueError("core paths must not be inside research-private/")
    planned = install_plan(root)
    for destination, data in planned:
        if destination.exists() and (not destination.is_file() or not same_text_bytes(destination.read_bytes(), data)):
            raise ValueError("Installed Skill differs; review and merge manually (or update the pinned copy deliberately): " + str(destination))
    messages = []
    root.mkdir(parents=True, exist_ok=True)
    added = sum(1 for destination, data in planned if create_new(destination, data))
    messages.append("Skill files added: %d (identical existing files kept)" % added)

    ws_path = root / WORKSPACE_FILE
    if ws_path.is_file():
        workspace = load_json(ws_path)
        if workspace.get("schema_version") != WORKSPACE_SCHEMA:
            raise ValueError("WORKSPACE.json schema %s is not supported (expected %s)" % (workspace.get("schema_version"), WORKSPACE_SCHEMA))
        messages.append("Using existing workspace (schema 3.0); its records are kept.")
        ws_changed = False
    else:
        workspace = load_json(template("workspace/WORKSPACE.json"))
        existing_code = bool(code_path) and code_path != "." and safe_path(root, code_path).is_dir() and any(safe_path(root, code_path).iterdir())
        existing_code = existing_code or (code_path == "." and any(p.name not in (".agents", ".production") for p in root.iterdir()))
        workspace.update(workspace_id="ws-" + uuid.uuid4().hex[:12], name=name or root.name)
        workspace["intake"].update(status="IN_PROGRESS", route="adopt_existing" if existing_code else "new_research")
        workspace["run"]["scope"] = {"target": "base", "required_readiness": "RELEASE_CANDIDATE", "game_quota": 0, "games": [],
                                     "basis": basis or "Reverse engineering and Base building only (game-reverse-engineering); no games."}
        workspace["run"]["allowed_stages"] = ["R0", "R1", "R2"]
        for relative, source in ((".production/BACKLOG.md", "workspace/BACKLOG.md"), (".production/HANDOFF.md", "workspace/HANDOFF.md"),
                                 (".production/RIGHTS_LEDGER.md", "workspace/RIGHTS_LEDGER.md")):
            create_new(safe_path(root, relative), template(source).read_bytes())
        ws_changed = True
        messages.append("Created workspace (scope: base only, no games).")
    if references and not workspace.get("research"):
        workspace["research"] = [{"id": "research-01", "sources": list(references), "records": ".production/research/research-01"}]
        workspace["focus"]["research"] = "research-01"
        create_new(safe_path(root, ".production/research/research-01/MECHANICS_MATRIX.md"), template("workspace/MECHANICS_MATRIX.md").read_bytes())
        ws_changed = True

    entry = next((b for b in workspace.get("bases", []) if isinstance(b, dict) and b.get("id") == base_id), None)
    if entry is None:
        if not code_path:
            raise ValueError("Registering a new Base needs --code-path (where the Base engine lives or will live).")
        code_root = root if code_path == "." else safe_path(root, code_path)
        records = workspace.get("layout", {}).get("base_records_dir", ".production/bases") + "/" + base_id
        folder = safe_path(root, records)
        base = load_json(template("workspace/base/BASE.json"))
        base.update(base_id=base_id, name=name or base_id, code_path=code_path, current_version=version,
                    research_ids=[r["id"] for r in workspace.get("research", []) if isinstance(r, dict)])
        base["versions"] = [{"version": version, "readiness": "NONE", "frozen": False,
                             "summary": "registered by game-reverse-engineering", "created_utc": now_utc()}]
        create_new(folder / "BASE.json", json_bytes(base))
        create_new(folder / "CAPABILITIES.md", template("workspace/base/CAPABILITIES.md").read_bytes())
        create_new(folder / "RIGHTS_LEDGER.md", template("workspace/RIGHTS_LEDGER.md").read_bytes())
        workspace.setdefault("bases", []).append({"id": base_id, "records": records})
        workspace["focus"]["base"] = workspace["focus"].get("base") or base_id
        ws_changed = True
        messages.append("Registered Base %s@%s at %s (code: %s)%s" % (base_id, version, records, code_path,
                        "" if code_root.exists() else " — code path does not exist yet"))
        default_core = [code_path] if code_path != "." else []
    else:
        folder = safe_path(root, entry["records"])
        base = load_json(folder / "BASE.json")
        messages.append("Adopting existing Base %s@%s; existing Base records are not modified." % (base_id, base.get("current_version")))
        default_core = [base.get("code_path")] if base.get("code_path") not in ("", ".") else []
    if ws_changed:
        save_json(ws_path, workspace)

    re_dir = folder / RE_DIRNAME
    state_path = re_dir / "RE_STATE.json"
    if state_path.exists():
        messages.append("Kept existing reverse-engineering records (run `gre.py upgrade` to add fields of newer Skill versions).")
    else:
        cores = list(core_paths or default_core)
        for path in cores:
            safe_path(root, path)
        state = load_json(template("RE_STATE.json"))
        for path in starter_paths or []:
            safe_path(root, path)
        state.update(base_id=base_id, target_level=target, core_paths=cores, starter_paths=list(starter_paths or []))
        if agent:
            state["assignment"] = {"agent_label": agent, "scope": "E0-E7", "since_utc": now_utc()}
        for name_, source in (("PARITY.json", "PARITY.json"), ("REUSE.json", "REUSE.json"), ("PROBES.json", "PROBES.json"),
                              ("PRESENTATION.json", "PRESENTATION.json"), ("CREATOR_KIT.json", "CREATOR_KIT.json"),
                              ("FIRST_USE.json", "FIRST_USE.json"), ("REUSE_TRIAL.json", "REUSE_TRIAL.json"),
                              ("GATES.json", "GATES.json"), ("TECH_SURVEY.md", "TECH_SURVEY.md"),
                              ("DYNAMIC_STUDY.md", "DYNAMIC_STUDY.md"), ("BASE_HANDOFF.md", "BASE_HANDOFF.md")):
            create_new(re_dir / name_, template(source).read_bytes())
        create_new(state_path, json_bytes(state))
        (re_dir / "evidence").mkdir(exist_ok=True)
        (re_dir / "reports").mkdir(exist_ok=True)
        with (re_dir / "HISTORY.jsonl").open("ab") as out:
            out.write((json.dumps({"utc": now_utc(), "event": "init", "base": base_id, "target": target,
                                   "core_paths": cores, "skill_version": SKILL_VERSION}, ensure_ascii=False) + "\n").encode("utf-8"))
        messages.append("Created reverse-engineering records at %s (target %s)." % (rel(root, re_dir), target))
        if not cores:
            messages.append("NOTE: set core_paths (engine core only, not sample content) before verification.")
    if not (root / ".production/local/ENVIRONMENT.json").exists():
        probe_environment(root)
    agents = root / "AGENTS.md"
    current = agents.read_text(encoding="utf-8-sig") if agents.exists() else ""
    if AGENTS_MARKERS[0] not in current:
        block = template("AGENTS.block.md").read_text(encoding="utf-8").rstrip("\n")
        append_text(agents, ("\n\n" if current else "") + block + "\n")
        messages.append("Appended reverse-engineering guide to AGENTS.md; existing instructions retained.")
    ignores = root / ".gitignore"
    current = ignores.read_text(encoding="utf-8-sig") if ignores.exists() else ""
    if IGNORE_MARKER not in current:
        append_text(ignores, ("\n" if current and not current.endswith("\n") else "") + IGNORE_BLOCK)
        messages.append("Ignored .production/local/ and research-private/ (quarantined research material stays out of Git).")
    messages.append("Next: E0 technical survey, E1 reuse assessment, discovery of game-specific capabilities. No quality or legal pass granted.")
    return messages


def upgrade(ctx: Context) -> List[str]:
    """Add fields introduced by newer Skill versions; never changes or removes existing values."""
    added = []
    gates = ctx.load("GATES.json")
    have = {g.get("id") for g in gates.get("gates", []) if isinstance(g, dict)}
    for gate in load_json(template("GATES.json"))["gates"]:
        if gate["id"] not in have:
            gates["gates"].append(gate)
            added.append("GATES " + gate["id"])
    if added:
        ctx.save("GATES.json", gates)
    parity = ctx.load("PARITY.json")
    if "discovery" not in parity:
        parity["discovery"] = load_json(template("PARITY.json"))["discovery"]
        ctx.save("PARITY.json", parity)
        added.append("PARITY.discovery")
    if create_new(ctx.path("PRESENTATION.json"), template("PRESENTATION.json").read_bytes()):
        added.append("PRESENTATION.json")
    else:
        presentation = ctx.load("PRESENTATION.json")
        merged = load_presentation(ctx)
        new_keys = [t for t in merged["study"] if t not in presentation.get("study", {})] + \
                   [c for c in merged["experiment"]["checks"] if c not in presentation.get("experiment", {}).get("checks", {})] + \
                   [k for k in ("reference", "frames") if k not in presentation]
        if new_keys:
            ctx.save("PRESENTATION.json", merged)
            added.append("PRESENTATION " + ",".join(new_keys))
    for name in ("CREATOR_KIT.json", "FIRST_USE.json", "REUSE_TRIAL.json"):
        if create_new(ctx.path(name), template(name).read_bytes()):
            added.append(name)
    probes = ctx.load("PROBES.json")
    if "max_visual_overlap" not in probes:
        probes["max_visual_overlap"] = load_json(template("PROBES.json"))["max_visual_overlap"]
        ctx.save("PROBES.json", probes)
        added.append("PROBES.max_visual_overlap")
    state = ctx.load("RE_STATE.json")
    missing = {k: v for k, v in DEFAULT_GUARDS.items() if k not in state.get("guards", {})}
    fields = {k: v for k, v in (("starter_paths", []), ("content_terms", []), ("decoupling_allow", []),
                                ("budget", {"paid_tools_allowed": False, "limits": []})) if k not in state}
    if missing or fields or state.get("upgraded_to") != SKILL_VERSION:
        state.update(fields)
        added += ["RE_STATE." + k for k in fields]
        state.setdefault("guards", {}).update(missing)
        state["upgraded_to"] = SKILL_VERSION
        ctx.save("RE_STATE.json", state)
        added += ["RE_STATE.guards." + k for k in missing]
    ctx.log("upgrade", to=SKILL_VERSION, added=added)
    return ["Upgrade to %s: added %s; existing values unchanged." % (SKILL_VERSION, ", ".join(added) or "nothing (already current)"),
            "Items without capability_class/scope or code fingerprints are still read with conservative defaults; re-verify to bind them."]


# ---------------------------------------------------------------- reuse assessment

def reuse_errors(ctx: Context, reuse: Dict[str, Any], core: List[str]) -> List[str]:
    errors = []
    if reuse.get("schema_version") != GRE_SCHEMA:
        errors.append("REUSE: unsupported schema_version")
    modules = reuse.get("modules")
    if not isinstance(modules, list):
        return errors + ["REUSE.modules must be a list"]
    seen = set()
    core_pure = [PurePosixPath(p) for p in core]
    for path in core_pure:
        if path.parts[:1] == (RESEARCH_PRIVATE,):
            errors.append("core path %s is inside research-private/" % path)
    for module in modules:
        if not isinstance(module, dict):
            errors.append("REUSE: module must be an object")
            continue
        mid = module.get("id")
        label = "REUSE %s" % mid
        if not isinstance(mid, str) or not SLUG_RE.fullmatch(mid) or mid in seen:
            errors.append(label + ": invalid or duplicate id")
            continue
        seen.add(mid)
        decision, kind = module.get("decision"), module.get("source_kind")
        if decision not in REUSE_DECISIONS:
            errors.append(label + ": invalid decision")
            continue
        if kind not in SOURCE_KINDS:
            errors.append(label + ": invalid source_kind")
        base_paths = [p for p in module.get("base_paths", []) if isinstance(p, str)]
        research_paths = [p for p in module.get("research_paths", []) if isinstance(p, str)]
        for path in base_paths + research_paths:
            try:
                safe_path(ctx.root, path)
            except ValueError as exc:
                errors.append(label + ": " + str(exc))
        execution = module.get("execution")
        if execution is not None and execution not in EXECUTION_POLICIES:
            errors.append(label + ": execution must be one of " + ", ".join(EXECUTION_POLICIES))
        if execution in ("sandboxed", "reviewed") and not text(module.get("execution_note")):
            errors.append(label + ": execution %s needs execution_note (what was reviewed or how it was isolated)" % execution)
        if decision in ("KEEP", "ADAPT"):
            license_text = text(module.get("license"))
            if not license_text or license_text.lower() in ("unknown", "none", "?"):
                errors.append(label + ": %s requires a known license or written grant" % decision)
            evidence = module.get("license_evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(label + ": %s requires license_evidence files" % decision)
            else:
                errors += check_evidence(evidence, ctx.root, label)[0]
            if kind == "original_decompiled" and not text(module.get("rights_basis")):
                errors.append(label + ": decompiled original code may only be kept with an explicit rights_basis (owner grant); otherwise QUARANTINE and reimplement")
            if not base_paths:
                errors.append(label + ": %s requires base_paths (where it lives in the Base)" % decision)
        if decision == "QUARANTINE":
            if base_paths:
                errors.append(label + ": QUARANTINE material must not have base_paths")
            if execution == "reviewed":
                errors.append(label + ": quarantined material may only be executed never or sandboxed")
            for path in research_paths:
                pure = PurePosixPath(path)
                for core_path in core_pure:
                    if inside(pure, core_path) or inside(core_path, pure):
                        errors.append(label + ": quarantined material %s overlaps Base core path %s" % (path, core_path))
    return errors


def reuse_warnings(reuse: Dict[str, Any]) -> List[str]:
    warnings = []
    for module in reuse.get("modules", []):
        if isinstance(module, dict) and module.get("source_kind") in FOREIGN_SOURCES and module.get("execution") is None:
            warnings.append("REUSE %s: record the execution boundary (never / sandboxed / reviewed) for foreign code and its build scripts" % module.get("id"))
    return warnings


def reuse_index(reuse: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {m["id"]: m for m in reuse.get("modules", []) if isinstance(m, dict) and isinstance(m.get("id"), str)}


def quarantine_paths(reuse: Dict[str, Any]) -> List[PurePosixPath]:
    paths = [PurePosixPath(RESEARCH_PRIVATE)]
    for module in reuse.get("modules", []):
        if isinstance(module, dict) and module.get("decision") == "QUARANTINE":
            paths += [PurePosixPath(p) for p in module.get("research_paths", []) if isinstance(p, str)]
    return paths


# ---------------------------------------------------------------- parity matrix

def item_scope(item: Dict[str, Any]) -> str:
    scope = item.get("scope")
    if scope in SCOPES:
        return scope
    return "optional" if item.get("importance") == "minor" else "core"


def item_class(item: Dict[str, Any]) -> Tuple[str, bool]:
    """(class, explicit). Missing classes of older records are derived conservatively."""
    cls = item.get("capability_class")
    if cls in CLASSES:
        return cls, True
    level = item.get("original", {}).get("evidence_level") if isinstance(item.get("original"), dict) else None
    if level == "UNKNOWN" or (item.get("approach") == "IMPROVE" and level not in ("VERIFIED", "STATIC_ONLY")):
        return "EXTENSION", False
    if level in ("VERIFIED", "STATIC_ONLY"):
        return "PARITY", False
    return "REPLACEMENT", False


def item_paths(item: Dict[str, Any], core: List[str]) -> List[str]:
    paths = [p for p in item.get("code_paths", []) if isinstance(p, str)] if isinstance(item.get("code_paths"), list) else []
    return paths or core


def item_errors(ctx: Context, item: Dict[str, Any], modules: Dict[str, Dict[str, Any]]) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    iid = item.get("id")
    label = "PARITY %s" % iid
    domain = item.get("domain")
    if domain not in DOMAIN_GROUP:
        return [label + ": invalid domain"], warnings
    if item.get("required_for") != GROUP_LEVEL[DOMAIN_GROUP[domain]]:
        errors.append(label + ": required_for must be %s for domain %s" % (GROUP_LEVEL[DOMAIN_GROUP[domain]], domain))
    status, approach = item.get("status"), item.get("approach")
    if status not in ITEM_STATUSES:
        return errors + [label + ": invalid status"], warnings
    if approach not in APPROACHES:
        errors.append(label + ": invalid approach")
    scope = item_scope(item)
    if item.get("scope") is not None and item.get("scope") not in SCOPES:
        errors.append(label + ": scope must be one of " + ", ".join(SCOPES))
    origin = item.get("origin", "template")
    if origin not in ORIGINS:
        errors.append(label + ": origin must be one of " + ", ".join(ORIGINS))
    if scope == "excluded" and not text(item.get("scope_reason")):
        errors.append(label + ": excluding an original capability needs scope_reason (why the Base deliberately leaves it out)")
    if origin == "template" and scope in ("optional", "legacy") and not text(item.get("scope_reason")):
        errors.append(label + ": a checklist capability downgraded to %s needs scope_reason" % scope)
    if origin == "discovered":
        discovery = item.get("discovery") if isinstance(item.get("discovery"), dict) else {}
        if discovery.get("source") not in DISCOVERY_SOURCES:
            errors.append(label + ": discovered items need discovery.source (code/runtime/assets)")
        if not discovery.get("evidence"):
            errors.append(label + ": discovered items need discovery evidence (where the unique mechanic was found)")
        else:
            e, w = check_evidence(discovery["evidence"], ctx.root, label + " discovery", allow_local=True)
            errors += e
            warnings += w
    for path in item.get("code_paths", []) or []:
        try:
            safe_path(ctx.root, path)
        except ValueError as exc:
            errors.append(label + ": code_paths " + str(exc))
    original = item.get("original") if isinstance(item.get("original"), dict) else {}
    level = original.get("evidence_level")
    if level not in EVIDENCE_LEVELS:
        errors.append(label + ": original.evidence_level must be one of " + ", ".join(EVIDENCE_LEVELS))
    refs = original.get("refs", [])
    ref_errors, ref_warnings = check_evidence(refs, ctx.root, label + " original", allow_local=True)
    errors += ref_errors
    warnings += ref_warnings
    if level == "VERIFIED" and not any(isinstance(r, dict) and r.get("kind") in DYNAMIC_KINDS for r in refs if isinstance(refs, list)):
        errors.append(label + ": original VERIFIED needs dynamic evidence (runtime-capture/trace/comparison/measurement/recording); otherwise use STATIC_ONLY")
    if level in ("STATIC_ONLY", "INFERRED", "PROXY") and not text(original.get("dynamic_gap")):
        errors.append(label + ": %s evidence needs dynamic_gap (what was not confirmed by running the original, and the impact)" % level)
    cls, explicit = item_class(item)
    if item.get("capability_class") not in (None, "") and item.get("capability_class") not in CLASSES:
        errors.append(label + ": capability_class must be PARITY, REPLACEMENT or EXTENSION")
    building = status in ("IMPLEMENTED", "VERIFIED")
    strict = errors if explicit else warnings
    if building and not explicit:
        warnings.append(label + ": capability_class not recorded; read as %s — confirm with `parity set --class`" % cls)
    if level == "UNKNOWN" and building and not (explicit and cls == "EXTENSION"):
        legacy_ok = item.get("approach") == "IMPROVE" and text(original.get("dynamic_gap")) and not explicit
        (warnings if legacy_ok else errors).append(label + ": original behavior is UNKNOWN; it may only be built when explicitly marked EXTENSION (`--class EXTENSION --design-note ...`), never as PARITY")
    if cls == "PARITY" and level not in ("VERIFIED", "STATIC_ONLY"):
        errors.append(label + ": PARITY needs original evidence (VERIFIED, or STATIC_ONLY with dynamic_gap); inferred or unknown behavior may only be REPLACEMENT or EXTENSION")
    if cls == "REPLACEMENT":
        if level == "UNKNOWN":
            errors.append(label + ": REPLACEMENT needs evidence of the original capability it replaces; unknown behavior is EXTENSION")
        if building and not text(item.get("differences")):
            strict.append(label + ": REPLACEMENT needs differences (how the compliant implementation differs from the original)")
    if cls == "EXTENSION" and building and not (text(item.get("design_note")) or text(original.get("dynamic_gap"))):
        strict.append(label + ": EXTENSION needs design_note (an original design, not a reverse-engineering result)")
    for mid in item.get("reuse_modules", []) or []:
        module = modules.get(mid)
        if module is None:
            errors.append(label + ": reuse_modules references unknown module " + str(mid))
        elif module.get("decision") in ("QUARANTINE", "REVIEW", "REPLACE"):
            errors.append(label + ": cannot reuse module %s (%s); list it in research_basis and reimplement" % (mid, module.get("decision")))
        elif approach == "REUSE" and module.get("decision") != "KEEP":
            errors.append(label + ": approach REUSE needs KEEP modules (use ADAPT for adapted code)")
    for mid in item.get("research_basis", []) or []:
        if mid not in modules:
            errors.append(label + ": research_basis references unknown module " + str(mid))
    if approach in ("REUSE", "ADAPT") and not item.get("reuse_modules"):
        errors.append(label + ": approach %s needs reuse_modules from REUSE.json" % approach)
    if status == "NOT_APPLICABLE" and not text(item.get("na_basis")):
        errors.append(label + ": NOT_APPLICABLE needs na_basis (original lacks it, or out of the user's scope)")
    if status == "VERIFIED":
        if approach in ("UNDECIDED", "OMIT"):
            errors.append(label + ": VERIFIED needs a real approach (REUSE/ADAPT/REIMPLEMENT/IMPROVE)")
        if not text(item.get("base_version")):
            errors.append(label + ": VERIFIED needs base_version")
        verification = item.get("verification")
        if not isinstance(verification, list) or not verification:
            errors.append(label + ": VERIFIED needs verification evidence; interfaces or documents do not count")
        else:
            errors += check_evidence(verification, ctx.root, label + " verification")[0]
            kinds = {v.get("kind") for v in verification if isinstance(v, dict)}
            if not kinds & VERIFY_KINDS:
                errors.append(label + ": verification needs a test, runtime capture, measurement, trace, benchmark or comparison (docs/specs do not count)")
            if DOMAIN_GROUP[domain] == "presentation" and not kinds & VISUAL_KINDS:
                errors.append(label + ": presentation items need runtime-capture/measurement/recording evidence with a real asset, not only unit tests")
        if "verified_fingerprint" not in item:
            warnings.append(label + ": verification is not bound to a code fingerprint (recorded by an older version); re-verify to bind it")
    if not isinstance(item.get("history"), list):
        errors.append(label + ": history must be a list")
    return errors, warnings


def discovery_errors(ctx: Context, parity: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    discovery = parity.get("discovery")
    if discovery is None:
        return [], ["PARITY has no discovery section (older record); run `gre.py upgrade`"]
    sources = discovery.get("sources", {}) if isinstance(discovery, dict) else {}
    for source in DISCOVERY_SOURCES:
        entry = sources.get(source, {}) if isinstance(sources.get(source), dict) else {}
        status = entry.get("status", "PENDING")
        if status not in DISCOVERY_STATUSES:
            errors.append("DISCOVERY %s: invalid status" % source)
        elif status == "DONE":
            if not entry.get("evidence"):
                errors.append("DISCOVERY %s: DONE needs evidence of the review" % source)
            else:
                e, w = check_evidence(entry["evidence"], ctx.root, "DISCOVERY " + source, allow_local=True)
                errors += e
                warnings += w
        elif status == "UNAVAILABLE" and not text(entry.get("reason")):
            errors.append("DISCOVERY %s: UNAVAILABLE needs a reason" % source)
    return errors, warnings


def discovery_problems(parity: Dict[str, Any]) -> List[str]:
    sources = (parity.get("discovery") or {}).get("sources", {})
    problems = []
    for source in DISCOVERY_SOURCES:
        entry = sources.get(source, {}) if isinstance(sources.get(source), dict) else {}
        if entry.get("status") not in ("DONE", "UNAVAILABLE"):
            problems.append("game-specific capability discovery from %s is not done (`gre.py discover --source %s`)" % (source, source))
    return problems


def parity_errors(ctx: Context, parity: Dict[str, Any], modules) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    if parity.get("schema_version") != GRE_SCHEMA:
        errors.append("PARITY: unsupported schema_version")
    items = parity.get("items")
    if not isinstance(items, list):
        return errors + ["PARITY.items must be a list"], warnings
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            errors.append("PARITY: item must be an object")
            continue
        iid = item.get("id")
        if not isinstance(iid, str) or not ITEM_ID_RE.fullmatch(iid) or iid in seen:
            errors.append("PARITY: invalid or duplicate item id %r" % iid)
            continue
        if not iid.startswith(str(item.get("domain")) + "-"):
            errors.append("PARITY %s: id prefix must match its domain" % iid)
        seen.add(iid)
        e, w = item_errors(ctx, item, modules)
        errors += e
        warnings += w
    present = {i.get("domain") for i in items if isinstance(i, dict)}
    missing = set(DOMAIN_GROUP) - present
    if missing:
        errors.append("PARITY: capability domains have no items (do not delete domains): " + ", ".join(sorted(missing)))
    e, w = discovery_errors(ctx, parity)
    return errors + e, warnings + w


def item_counts(ctx: Context, item: Dict[str, Any], current: str, core: List[str],
                presentation: Optional[Dict[str, Any]] = None) -> Optional[str]:
    status = item.get("status")
    if status == "NOT_APPLICABLE":
        return None if text(item.get("na_basis")) else "NOT_APPLICABLE without na_basis"
    if status in NON_COUNTING:
        return "is %s (an interface or document is not a finished capability)" % status
    if status != "VERIFIED":
        return "is " + str(status)
    if text(item.get("base_version")) != current:
        return "verified against base %s, not current %s" % (item.get("base_version") or "(none)", current)
    if "verified_fingerprint" in item and item["verified_fingerprint"] != ctx.fingerprint(item_paths(item, core)):
        return "stale: code under %s changed after verification; re-verify" % ", ".join(item_paths(item, core))
    if presentation is not None:
        revisions = study_revisions(presentation)
        recorded = item.get("study_revisions") if isinstance(item.get("study_revisions"), dict) else {}
        corrected = [t for t in topics_for_item(presentation, item.get("id")) if revisions.get(t, 0) > int(recorded.get(t, 0))]
        if corrected:
            return "stale: the study conclusion of %s was corrected after verification; re-verify the implementation" % ", ".join(corrected)
    return None


# ---------------------------------------------------------------- creator probes

def probe_errors(ctx: Context, probes: Dict[str, Any], data: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    current, fingerprint, core = data["current"], data["fingerprint"], data["core"]
    items = {i.get("id"): i for i in data["parity"].get("items", []) if isinstance(i, dict)}
    quarantine = quarantine_paths(data["reuse"])
    errors = []
    if probes.get("schema_version") != GRE_SCHEMA:
        errors.append("PROBES: unsupported schema_version")
    valid = []
    core_pure = [PurePosixPath(p) for p in core]
    entries = probes.get("probes") if isinstance(probes.get("probes"), list) else []
    seen = set()

    def files_ok(label, files, allow_core):
        problems = []
        for entry in files:
            try:
                path = safe_path(ctx.root, entry.get("path", ""))
                pure = PurePosixPath(rel(ctx.root, path))
                if not allow_core and any(inside(pure, c) for c in core_pure):
                    problems.append(label + " %s is inside the engine core; probe content must live outside core_paths" % entry.get("path"))
                if any(inside(pure, q) for q in quarantine):
                    problems.append(label + " %s is inside quarantined research material" % entry.get("path"))
                if not path.is_file() or digest(path) != str(entry.get("sha256", "")).lower():
                    problems.append(label + " missing or changed: %s" % entry.get("path"))
            except (ValueError, AttributeError) as exc:
                problems.append(label + " " + str(exc))
        return problems

    def bound(label, record):
        problems = []
        if text(record.get("base_version")) != current:
            problems.append(label + ": recorded for base %s, current is %s; re-run" % (record.get("base_version"), current))
        if not fingerprint:
            problems.append(label + ": core_paths are empty or missing; cannot prove the core stayed unchanged")
        elif record.get("core_fingerprint") != fingerprint:
            problems.append(label + ": core fingerprint differs from the current core (the core changed); re-run on the current core")
        return problems

    for probe in entries:
        if not isinstance(probe, dict):
            errors.append("PROBES: probe must be an object")
            continue
        pid = probe.get("id")
        label = "PROBE %s" % pid
        own = []
        if not isinstance(pid, str) or not SLUG_RE.fullmatch(pid) or pid in seen:
            errors.append(label + ": invalid or duplicate id")
            continue
        seen.add(pid)
        own += bound(label, probe)
        if not text(probe.get("license")):
            own.append(label + ": license required (original test content)")
        for field in ("config_files", "asset_files"):
            files = probe.get(field)
            if not isinstance(files, list) or not files:
                own.append(label + ": %s must list files with SHA-256" % field)
            else:
                own += files_ok(label + " " + field, files, False)
        own += files_ok(label + " shared_files", probe.get("shared_files", []) or [], True)
        scenes = probe.get("scene_files")
        if not isinstance(scenes, list) or not scenes:
            own.append(label + ": no scene configuration; Creator probes must assemble their scene through the Base's scene configuration (see PX01)")
        else:
            own += files_ok(label + " scene_files", scenes, False)
        replaces = probe.get("replaces") if isinstance(probe.get("replaces"), dict) else {}
        for category in PROBE_CATEGORIES:
            evidence = (replaces.get(category) or {}).get("evidence") if isinstance(replaces.get(category), dict) else None
            if not isinstance(evidence, list) or not evidence:
                own.append(label + ": no runtime evidence that %s was replaced" % category)
                continue
            own += check_evidence(evidence, ctx.root, label + " " + category)[0]
            if not any(isinstance(e, dict) and e.get("kind") in RUNTIME_KINDS for e in evidence):
                own.append(label + ": %s evidence needs a runtime capture, measurement or test" % category)
        changes = probe.get("gameplay_changes") if isinstance(probe.get("gameplay_changes"), list) else []
        if not changes:
            own.append(label + ": no gameplay change; swapping images alone does not prove production capability (`gre.py probe-gameplay`)")
        for index, change in enumerate(changes):
            c_label = "%s gameplay[%d]" % (label, index)
            if not isinstance(change, dict) or not text(change.get("mechanic")):
                own.append(c_label + ": mechanic description required")
                continue
            linked = [items.get(i) for i in change.get("items", [])]
            if not linked or any(i is None for i in linked):
                own.append(c_label + ": must reference existing parity items")
            elif not any(i.get("domain") in GAMEPLAY_DOMAINS for i in linked):
                own.append(c_label + ": must change a gameplay mechanic (items in L1-L5 or C1), not only presentation")
            files = change.get("config_files")
            if not isinstance(files, list) or not files:
                own.append(c_label + ": must be made through configuration or extension files (config_files)")
            else:
                own += files_ok(c_label + " config", files, False)
            evidence = change.get("evidence", [])
            if not evidence or not any(isinstance(e, dict) and e.get("kind") in RUNTIME_KINDS for e in evidence):
                own.append(c_label + ": needs runtime evidence that the changed mechanic actually plays")
            else:
                own += check_evidence(evidence, ctx.root, c_label)[0]
            own += bound(c_label, change)
        loop = probe.get("loop") if isinstance(probe.get("loop"), dict) else None
        if not loop:
            own.append(label + ": no complete short game loop recorded (`gre.py probe-loop`)")
        else:
            covers = set(loop.get("covers", []))
            missing = [s for s in LOOP_STEPS if s not in covers]
            if missing:
                own.append(label + ": loop does not cover " + ", ".join(missing))
            if loop.get("input") != "normal":
                own.append(label + ": loop must be played with normal input (no debug skips, god mode or forced wins)")
            evidence = loop.get("evidence", [])
            if not any(isinstance(e, dict) and e.get("kind") in ("recording", "runtime-capture") for e in evidence):
                own.append(label + ": loop needs a recording or runtime capture")
            else:
                own += check_evidence(evidence, ctx.root, label + " loop")[0]
            own += bound(label + " loop", loop)
        if probe.get("core_changes_needed"):
            own.append(label + ": needed engine-core changes; move them into the Base, bump the version and re-run both probes")
        errors += own
        if not own:
            valid.append(probe)
    limit = probes.get("max_visual_overlap", 0.2)
    limit = limit if isinstance(limit, (int, float)) and 0 <= limit < 1 else 0.2
    for index, first in enumerate(valid):
        for second in valid[index + 1:]:
            pair = "PROBES %s/%s" % (first["id"], second["id"])
            a = {f["sha256"] for f in first["asset_files"]}
            b = {f["sha256"] for f in second["asset_files"]}
            overlap = len(a & b) / max(1, min(len(a), len(b)))
            if overlap > limit:
                errors.append(pair + ": %d%% of visual assets are identical (limit %d%%); the two visual configurations must be clearly different (put shared fonts/tools in shared_files)" % (round(overlap * 100), round(limit * 100)))
            ca = {f["sha256"] for c in first["gameplay_changes"] for f in c["config_files"]}
            cb = {f["sha256"] for c in second["gameplay_changes"] for f in c["config_files"]}
            if ca == cb:
                errors.append(pair + ": gameplay configurations are identical; each probe must change gameplay differently")
            if {f["sha256"] for f in first["scene_files"]} == {f["sha256"] for f in second["scene_files"]}:
                errors.append(pair + ": scene configurations are identical; each probe must assemble its own scene")
            for category in PROBE_CATEGORIES:
                ea = {e["sha256"] for e in first["replaces"][category]["evidence"]}
                eb = {e["sha256"] for e in second["replaces"][category]["evidence"]}
                if ea & eb:
                    errors.append(pair + ": identical %s evidence; each probe needs its own runtime proof" % category)
    return errors, [p["id"] for p in valid]


# ---------------------------------------------------------------- presentation reconstruction

PR_TOPICS = ["PR%02d" % i for i in range(1, 14)]
PX_CHECKS = {
    "PX01": {"runtime-capture", "recording"},
    "PX02": {"measurement"},
    "PX03": {"measurement", "runtime-capture"},
    "PX04": {"recording"},
    "PX05": {"measurement", "trace"},
    "PX06": {"measurement"},
    "PX07": {"measurement"},
    "PX08": {"measurement"},
    "PX09": {"measurement"},
}
PX_TOPICS = {"PX01": ["PR07", "PR11"], "PX02": ["PR01", "PR02"], "PX03": ["PR03"], "PX04": ["PR04"], "PX05": ["PR05"],
             "PX06": ["PR06", "PR12"], "PX07": ["PR09", "PR11"], "PX08": ["PR09"], "PX09": ["PR11", "PR12"]}
STUDY_FIELDS = ("inputs", "outputs", "data_structures", "constraints", "unknowns", "reuse")
METHOD_FIELDS = ("original_method", "base_method")
DECISIONS = {"A": "original method confirmed and legally reusable as is",
             "B": "original method confirmed; compliant equivalent rebuild of the same method",
             "C": "deliberate extension or change of the original method (difference, reason and impact disclosed)",
             "D": "original method not established by evidence (UNKNOWN)"}
BASE_RELATIONS = ("same_method", "different_method", "downgrade", "missing")
ASSET_SOURCES = ("original", "placeholder", "own_test")
REFERENCE_RUNTIME = ("UNKNOWN", "AVAILABLE", "UNAVAILABLE")
REFERENCE_ASSETS = ("UNKNOWN", "LEGAL_ORIGINAL", "PLACEHOLDER_ONLY", "NONE")
PRODUCTION_TOPIC = "PR13"
AUTHOR_DOC_KINDS = {"author-documentation"}
CREATOR_GUIDE = ("怎样新增一套场景：", "怎样修改背景、地形、前景和 UI：", "怎样添加新角色和动画：",
                 "怎样配置不同对象的布局与层级：", "怎样配置攻击、技能及特效挂点：",
                 "怎样更换视觉风格而不修改战斗逻辑：", "已实现与仍需扩展的能力：")
STATIC_KINDS = {"static-analysis", "source", "data", "disassembly", "asset-structure"}
PRESENTATION_DYNAMIC = {"trace", "measurement", "recording", "comparison"}
TRACE_KEYS = ("image", "src_rect", "corners", "blend", "render_item", "sort_key")


def study_errors(ctx: Context, tid: str, topic: Dict[str, Any], items: Dict[str, Any],
                 modules: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[str]]:
    """What the original actually does, with graded evidence, and how the Base relates to that method."""
    errors, warnings = [], []
    label = "PRESENTATION %s" % tid
    level = topic.get("evidence_level")
    if level not in EVIDENCE_LEVELS:
        return [label + ": invalid evidence_level"], warnings
    refs = topic.get("refs", [])
    e, w = check_evidence(refs, ctx.root, label, allow_local=True)
    errors += e
    warnings += w
    kinds = {r.get("kind") for r in refs if isinstance(r, dict)}
    if any(isinstance(r, dict) and r.get("subject") == "base" for r in refs):
        errors.append(label + ": evidence produced by the Base or with own test art proves self-consistency only; it cannot be evidence of the original")
    if level == "VERIFIED" and not kinds & PRESENTATION_DYNAMIC:
        errors.append(label + ": VERIFIED needs dynamic evidence (trace, measurement, recording or comparison); screenshots alone support at most INFERRED")
    if level == "STATIC_ONLY" and not kinds & (STATIC_KINDS | AUTHOR_DOC_KINDS):
        errors.append(label + ": STATIC_ONLY needs static evidence (source, data, disassembly, asset-structure); screenshots alone support at most INFERRED")
    if level in ("STATIC_ONLY", "INFERRED", "PROXY") and not text(topic.get("dynamic_gap")):
        errors.append(label + ": %s needs dynamic_gap (what the evidence does not prove)" % level)
    if tid == PRODUCTION_TOPIC and level in ("VERIFIED", "STATIC_ONLY") and not kinds & AUTHOR_DOC_KINDS:
        errors.append(label + ": production tools and process are UNKNOWN unless the original authors documented them; never infer a tool from a data format")
    for iid in topic.get("items", []):
        if iid not in items:
            errors.append(label + ": linked parity item %s does not exist" % iid)
    decision, relation = topic.get("decision", ""), topic.get("base_relation", "")
    if decision and decision not in DECISIONS:
        errors.append(label + ": decision must be A, B, C or D")
    if relation and relation not in BASE_RELATIONS:
        errors.append(label + ": base_relation must be one of " + ", ".join(BASE_RELATIONS))
    if decision in ("A", "B") and level not in ("VERIFIED", "STATIC_ONLY"):
        errors.append(label + ": %s needs the original method confirmed by source or runtime evidence; inferred or unknown methods are D" % decision)
    if decision in ("A", "B") and relation and relation != "same_method":
        errors.append(label + ": %s means the Base uses the original's method; a different method, downgrade or missing capability must be C (with difference, reason and impact) or D" % decision)
    if decision == "A":
        reuse = [m for m in topic.get("reuse_modules", []) if (modules or {}).get(m, {}).get("decision") in ("KEEP", "ADAPT")]
        if not reuse:
            errors.append(label + ": A needs the original implementation as a legally reusable KEEP/ADAPT module in REUSE.json; otherwise it is B")
    deviation = topic.get("deviation") if isinstance(topic.get("deviation"), dict) else {}
    if decision == "C":
        if level == "UNKNOWN":
            errors.append(label + ": C changes a known original method; with no evidence of the original it is D")
        missing = [k for k in ("difference", "reason", "impact") if not text(deviation.get(k))]
        if missing:
            errors.append(label + ": C must disclose %s of the deviation from the original method" % ", ".join(missing))
    if decision == "D" and level in ("VERIFIED", "STATIC_ONLY"):
        errors.append(label + ": the original method is confirmed by evidence; choose A, B or C instead of D")
    for index, correction in enumerate(topic.get("corrections", [])):
        if not isinstance(correction, dict) or not text(correction.get("was")) or not text(correction.get("now")) or not correction.get("affects"):
            errors.append(label + ": correction %d must record what was wrong, the corrected fact and the downstream implementations it affects" % index)
    return errors, warnings


def study_revisions(presentation: Optional[Dict[str, Any]]) -> Dict[str, int]:
    study = (presentation or {}).get("study", {})
    return {tid: int(topic.get("revision", 0)) for tid, topic in study.items() if isinstance(topic, dict)}


def topics_for_item(presentation: Optional[Dict[str, Any]], iid: str) -> List[str]:
    study = (presentation or {}).get("study", {})
    return [tid for tid, topic in study.items() if isinstance(topic, dict) and iid in topic.get("items", [])]


def study_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    presentation = data.get("presentation")
    if presentation is None:
        return ["PRESENTATION.json is missing (records from before 1.2.0); run `gre.py upgrade`"]
    items = {i.get("id"): i for i in data["parity"].get("items", []) if isinstance(i, dict)}
    problems = []
    for tid in PR_TOPICS:
        topic = presentation.get("study", {}).get(tid)
        if not isinstance(topic, dict):
            problems.append("%s is missing from the presentation study (run `gre.py upgrade`)" % tid)
            continue
        errors, _ = study_errors(ctx, tid, topic, items, data["modules"])
        if errors:
            problems.append(errors[0])
            continue
        if text(topic.get("na_basis")):
            if not topic.get("refs"):
                problems.append("%s is NOT_APPLICABLE but has no evidence that the original lacks it" % tid)
            continue
        if not topic.get("refs") or (topic.get("evidence_level") == "UNKNOWN" and topic.get("decision") != "D"):
            problems.append("%s %s: not studied (record actual source evidence)" % (tid, topic.get("name", "")))
            continue
        empty = [f for f in STUDY_FIELDS if not text(topic.get(f))]
        if empty:
            problems.append("%s: record %s (write 'none known' only when that is the finding)" % (tid, ", ".join(empty)))
            continue
        if topic.get("decision") not in DECISIONS or topic.get("base_relation") not in BASE_RELATIONS:
            problems.append("%s: record the Original Pipeline First decision (A/B/C/D) and how the Base relates to the original method" % tid)
            continue
        needed = ["base_method"] + ([] if topic.get("decision") == "D" else ["original_method"])
        empty = [f for f in needed if not text(topic.get(f))]
        if empty:
            problems.append("%s: describe %s" % (tid, " and ".join(empty)))
    return problems


def files_changed(ctx: Context, files: List[Dict[str, Any]]) -> List[str]:
    changed = []
    for entry in files:
        try:
            path = safe_path(ctx.root, entry.get("path", ""))
            if not path.is_file() or digest(path) != entry.get("sha256"):
                changed.append(entry.get("path"))
        except (ValueError, AttributeError):
            changed.append(str(entry))
    return changed


def check_problems(ctx: Context, cid: str, check: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
    label = "%s %s" % (cid, check.get("name", ""))
    if check.get("status") != "PASS":
        return [label + ": is " + str(check.get("status"))]
    problems = []
    evidence = check.get("evidence", [])
    errors, _ = check_evidence(evidence, ctx.root, cid)
    problems += errors[:1]
    kinds = {e.get("kind") for e in evidence if isinstance(e, dict)}
    if not kinds & PX_CHECKS[cid]:
        problems.append(label + ": needs %s evidence from the running Base" % " or ".join(sorted(PX_CHECKS[cid])))
    if text(check.get("base_version")) != data["current"]:
        problems.append(label + ": recorded for base %s, current is %s" % (check.get("base_version") or "(none)", data["current"]))
    if not data["fingerprint"] or check.get("core_fingerprint") != data["fingerprint"]:
        problems.append(label + ": stale — the engine core changed after this check; re-run it")
    changed = files_changed(ctx, check.get("bound_files", []))
    if changed:
        problems.append(label + ": stale — scene/layout/anchor files changed after this check (%s); re-run and record new evidence" % ", ".join(changed[:3]))
    revisions = study_revisions(data.get("presentation"))
    recorded = check.get("study_revisions", {}) if isinstance(check.get("study_revisions"), dict) else {}
    corrected = [t for t in PX_TOPICS.get(cid, []) if revisions.get(t, 0) > int(recorded.get(t, 0))]
    if corrected:
        problems.append(label + ": stale — the study conclusion of %s was corrected after this check; re-verify the downstream implementation" % ", ".join(corrected))
    quarantine = quarantine_paths(data["reuse"])
    swap = check.get("swap") if isinstance(check.get("swap"), dict) else {}
    for entry in check.get("bound_files", []) + [f for k in ("before", "after", "ui_before", "ui_after") for f in swap.get(k, [])]:
        pure = PurePosixPath(str(entry.get("path", "")))
        if any(inside(pure, q) for q in quarantine):
            problems.append(label + ": uses quarantined research material %s; experiments need original-licensed or own test assets" % entry.get("path"))
    if cid == "PX01":
        scenes = {f.get("sha256") for f in check.get("bound_files", [])}
        if len(scenes) < 2:
            problems.append(label + ": needs at least two different scene configurations; one fixed screen is not a configurable scene system")
    if cid == "PX07":
        before = {f.get("sha256") for f in swap.get("before", [])}
        after = {f.get("sha256") for f in swap.get("after", [])}
        ui_before = {f.get("sha256") for f in swap.get("ui_before", [])}
        ui_after = {f.get("sha256") for f in swap.get("ui_after", [])}
        if not before or not after or before == after:
            problems.append(label + ": record scene assets before and after the swap; they must differ")
        if not ui_before or not ui_after or ui_before == ui_after:
            problems.append(label + ": record UI theme files before and after the swap; they must differ")
        if swap.get("core_fingerprint_before") != check.get("core_fingerprint"):
            problems.append(label + ": the core changed between the original theme and the swapped theme; swapping art must not need core edits")
        problems += ["%s: swapped files changed after the check (%s)" % (cid, p) for p in files_changed(ctx, swap.get("after", []) + swap.get("ui_after", []))[:1]]
    if cid == "PX08":
        resolutions = check.get("resolutions", [])
        if not resolutions:
            problems.append(label + ": list the target resolution(s) that were measured")
        elif sum(1 for e in evidence if isinstance(e, dict) and e.get("kind") == "measurement") < len(resolutions):
            problems.append(label + ": each target resolution needs its own measurement")
    if cid == "PX09" and not check.get("bound_files"):
        problems.append(label + ": bind the scene/logic geometry contract (background window, board or map geometry, offsets) that was measured")
    return problems


def load_json_file(ctx: Context, relative: str) -> Tuple[Optional[Any], str]:
    try:
        path = safe_path(ctx.root, relative)
        return json.loads(path.read_text(encoding="utf-8-sig")), ""
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def trace_problems(ctx: Context, frame: Dict[str, Any]) -> List[str]:
    """A runtime frame trace must list real primitives and its formula check must reproduce N/N."""
    label = "frame %s" % frame.get("scene_type")
    problems = []
    for key in ("trace", "formula_check"):
        entry = frame.get(key) or {}
        problems += files_changed(ctx, [entry]) and [label + ": %s file missing or changed" % key] or []
    trace, error = load_json_file(ctx, (frame.get("trace") or {}).get("path", ""))
    primitives = trace.get("primitives") if isinstance(trace, dict) else None
    if not isinstance(primitives, list) or not primitives:
        problems.append(label + ": trace has no primitives %s" % error)
    else:
        bad = [i for i, p in enumerate(primitives) if not isinstance(p, dict) or any(k not in p for k in TRACE_KEYS)
               or not isinstance(p.get("corners"), list) or len(p.get("corners")) != 4]
        if bad:
            problems.append(label + ": %d primitives lack %s (first: #%d)" % (len(bad), "/".join(TRACE_KEYS), bad[0]))
    formula, error = load_json_file(ctx, (frame.get("formula_check") or {}).get("path", ""))
    checks = formula.get("checks") if isinstance(formula, dict) else None
    if not isinstance(checks, list) or not checks:
        problems.append(label + ": formula check has no checks %s" % error)
    else:
        failed = []
        for check in checks:
            try:
                if abs(float(check["expected"]) - float(check["actual"])) > float(check.get("tolerance", 0)):
                    failed.append(check.get("name", "?"))
            except (KeyError, TypeError, ValueError):
                failed.append(str(check.get("name", "?")) if isinstance(check, dict) else "?")
        if failed:
            problems.append(label + ": formula check %d/%d (failing: %s)" % (len(checks) - len(failed), len(checks), ", ".join(failed[:3])))
    if len(frame.get("layers", [])) < 2 or files_changed(ctx, frame.get("layers", [])):
        problems.append(label + ": needs a layer-by-layer rebuild (at least two layer images, unchanged)")
    return problems


def frame_problems(ctx: Context, presentation: Dict[str, Any]) -> List[str]:
    reference = presentation.get("reference", {})
    scene_types = reference.get("scene_types", [])
    frames = {f.get("scene_type"): f for f in presentation.get("frames", []) if isinstance(f, dict)}
    problems = []
    for scene in scene_types:
        frame = frames.get(scene)
        if frame is None:
            problems.append("no frame study for scene type %s (`gre.py present frame`)" % scene)
            continue
        if frame.get("mode") == "runtime":
            problems += trace_problems(ctx, frame)
        elif frame.get("mode") == "source":
            if reference.get("original_runtime") != "UNAVAILABLE":
                problems.append("frame %s: the original can run; trace a real frame instead of a source walkthrough" % scene)
            problems += files_changed(ctx, [frame.get("walkthrough") or {}]) and ["frame %s: walkthrough file missing or changed" % scene] or []
        else:
            problems.append("frame %s: mode must be runtime or source" % scene)
    return problems


def base_outputs(data: Dict[str, Any]) -> set:
    """Hashes of files produced by the Base or with own test art (verification, experiment, probe evidence)."""
    shas = set()
    for item in data["parity"].get("items", []):
        shas |= {v.get("sha256") for v in item.get("verification", []) if isinstance(v, dict)}
    presentation = data.get("presentation") or {}
    for check in presentation.get("experiment", {}).get("checks", {}).values():
        shas |= {e.get("sha256") for e in check.get("evidence", []) if isinstance(e, dict)}
    for probe in data["probes"].get("probes", []):
        for category in probe.get("replaces", {}).values():
            shas |= {e.get("sha256") for e in category.get("evidence", []) if isinstance(e, dict)}
    shas.discard(None)
    return shas


def evidence_misuse(data: Dict[str, Any]) -> List[str]:
    outputs = base_outputs(data)
    problems = []
    presentation = data.get("presentation") or {}
    for tid, topic in presentation.get("study", {}).items():
        if any(isinstance(r, dict) and r.get("sha256") in outputs for r in topic.get("refs", [])):
            problems.append("%s: cites a Base/test output as evidence of the original; own art proves self-consistency only" % tid)
    for item in data["parity"].get("items", []):
        if any(isinstance(r, dict) and r.get("sha256") in outputs for r in item.get("original", {}).get("refs", [])):
            problems.append("%s: cites a Base/test output as original evidence" % item.get("id"))
    return problems


def parity_conflicts(data: Dict[str, Any]) -> List[str]:
    presentation = data.get("presentation") or {}
    items = {i.get("id"): i for i in data["parity"].get("items", []) if isinstance(i, dict)}
    problems = []
    for tid, topic in presentation.get("study", {}).items():
        if topic.get("decision") in ("C", "D") or topic.get("base_relation") in ("different_method", "downgrade", "missing"):
            for iid in topic.get("items", []):
                item = items.get(iid)
                if item and item.get("capability_class") == "PARITY" and item.get("status") in ("IMPLEMENTED", "VERIFIED"):
                    problems.append("%s is claimed PARITY but %s records %s/%s; use REPLACEMENT or EXTENSION and disclose the difference"
                                    % (iid, tid, topic.get("decision") or "-", topic.get("base_relation") or "-"))
    return problems


def presentation_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    """Presentation Reconstruction Gate: reference inventory, Original Pipeline First study, frame study,
    running Base experiment, original comparison record, honest evidence."""
    problems = study_problems(ctx, data)
    presentation = data.get("presentation")
    if presentation is None:
        return problems
    reference = presentation.get("reference", {})
    if reference.get("original_runtime") not in ("AVAILABLE", "UNAVAILABLE") or reference.get("original_assets") not in REFERENCE_ASSETS[1:]:
        problems.append("record what reference material exists: can the original run, and are legal original assets available? (`gre.py present reference`)")
    elif not reference.get("scene_types"):
        problems.append("list the scene types that need a frame study (`gre.py present reference --scene-types ...`)")
    else:
        problems += frame_problems(ctx, presentation)
    checks = presentation.get("experiment", {}).get("checks", {})
    kinds = set()
    for cid in PX_CHECKS:
        check = checks.get(cid)
        if not isinstance(check, dict):
            problems.append(cid + " is missing from the reconstruction experiment (run `gre.py upgrade`)")
            continue
        problems += check_problems(ctx, cid, check, data)
        if check.get("status") == "PASS":
            kinds |= {e.get("kind") for e in check.get("evidence", []) if isinstance(e, dict)}
    missing = [k for k in ("runtime-capture", "recording", "measurement") if k not in kinds]
    if missing:
        problems.append("the experiment must keep screenshots, animation sequences and measurements (missing: %s)" % ", ".join(missing))
    comparison = presentation.get("original_comparison", {})
    if comparison.get("status") == "DONE":
        if not any(isinstance(e, dict) and e.get("kind") in ("comparison", "recording", "measurement") for e in comparison.get("evidence", [])):
            problems.append("original comparison DONE needs comparison/recording/measurement evidence")
        if comparison.get("asset_source") not in ASSET_SOURCES:
            problems.append("original comparison must say whether original, placeholder or own test assets were on screen")
    elif comparison.get("status") == "UNAVAILABLE":
        if not text(comparison.get("reason")):
            problems.append("original comparison UNAVAILABLE needs a reason")
    else:
        problems.append("record the dynamic comparison with the original (`gre.py present compare --status DONE|UNAVAILABLE`)")
    return problems + parity_conflicts(data) + evidence_misuse(data)


def fidelity(data: Dict[str, Any]) -> Dict[str, str]:
    """Mechanism fidelity (how frames are composed) and visual fidelity (real original pixels) are separate claims."""
    presentation = data.get("presentation") or {}
    study = presentation.get("study", {})
    reference = presentation.get("reference", {})
    decisions = {tid: t.get("decision", "") for tid, t in study.items() if isinstance(t, dict) and not text(t.get("na_basis"))}
    undecided = [t for t, d in decisions.items() if d not in DECISIONS]
    unknown = [t for t, d in decisions.items() if d == "D"]
    changed = [t for t, d in decisions.items() if d == "C"]
    runtime_frames = [f for f in presentation.get("frames", []) if isinstance(f, dict) and f.get("mode") == "runtime"]
    if undecided or not decisions:
        mechanism = "NOT ESTABLISHED (undecided: %s)" % ", ".join(undecided[:5] or ["all"])
    else:
        basis = "runtime-traced" if runtime_frames and reference.get("original_runtime") == "AVAILABLE" else "source-confirmed only"
        mechanism = "%s; %s" % (basis, "equivalent method on every topic" if not unknown and not changed else
                                "NOT fully equivalent — changed: %s; unknown: %s" % (", ".join(changed) or "none", ", ".join(unknown) or "none"))
    comparison = presentation.get("original_comparison", {})
    if reference.get("original_assets") != "LEGAL_ORIGINAL":
        visual = "NOT VERIFIED — no legal original pixels in the research environment; never claim visual equivalence"
    elif comparison.get("status") != "DONE" or comparison.get("asset_source") != "original":
        visual = "NOT VERIFIED — no side-by-side comparison with the original's real assets"
    else:
        visual = "compared side by side with legal original assets"
    return {"mechanism": mechanism, "visual": visual}


def presentation_equivalence(data: Dict[str, Any]) -> str:
    comparison = (data.get("presentation") or {}).get("original_comparison", {})
    if comparison.get("status") == "DONE":
        return "dynamically compared with the original (%s assets)" % (comparison.get("asset_source") or "unspecified")
    if comparison.get("status") == "UNAVAILABLE":
        return "NOT dynamically verified (original could not be run: %s); do not claim visual equivalence" % text(comparison.get("reason"))
    return "not compared yet"


def load_presentation(ctx: Context) -> Dict[str, Any]:
    if not ctx.path("PRESENTATION.json").is_file():
        raise ValueError("PRESENTATION.json is missing; run `gre.py upgrade` first")
    presentation = ctx.load("PRESENTATION.json")
    defaults = load_json(template("PRESENTATION.json"))
    for tid, topic in defaults["study"].items():
        presentation.setdefault("study", {}).setdefault(tid, topic)
    for cid, check in defaults["experiment"]["checks"].items():
        presentation.setdefault("experiment", {}).setdefault("checks", {}).setdefault(cid, check)
    presentation.setdefault("reference", defaults["reference"])
    presentation.setdefault("frames", [])
    return presentation


def present_study(ctx: Context, tid: str, level: Optional[str] = None, evidence: Optional[str] = None, kind: str = "",
                  observed: str = "", local: bool = False, gap: Optional[str] = None, items: Optional[List[str]] = None,
                  na_basis: Optional[str] = None, decision: Optional[str] = None, relation: Optional[str] = None,
                  modules: Optional[List[str]] = None, deviation: Optional[Dict[str, str]] = None,
                  correct: Optional[str] = None, affects: Optional[List[str]] = None, **fields: Optional[str]) -> List[str]:
    if tid not in PR_TOPICS:
        raise ValueError("topic must be one of " + ", ".join(PR_TOPICS))
    presentation = load_presentation(ctx)
    topic = presentation["study"][tid]
    added = []
    messages = []
    if correct is not None:
        if not text(correct) or not affects:
            raise ValueError("--correct needs the corrected fact and --affects listing every downstream implementation that relied on the old conclusion")
        previous = "; ".join("%s=%s" % (k, topic.get(k)) for k in ("original_method", "data_structures") if text(topic.get(k)))
        topic.setdefault("corrections", []).append({"utc": now_utc(), "was": previous or "(previous conclusion)", "now": correct, "affects": affects})
        topic["revision"] = int(topic.get("revision", 0)) + 1
        messages.append("%s corrected (revision %d); downstream checks and parity items linked to it are now stale until re-verified: %s"
                        % (tid, topic["revision"], ", ".join(affects)))
    if evidence:
        entry = evidence_entry(ctx.root, evidence, kind or "static-analysis", observed or "original presentation evidence", "local_research" if local else "")
        entry["subject"] = "original"
        topic.setdefault("refs", []).append(entry)
        added.append(entry)
    if level is not None:
        if level not in EVIDENCE_LEVELS:
            raise ValueError("level must be one of " + ", ".join(EVIDENCE_LEVELS))
        topic["evidence_level"] = level
    for key, value in list(fields.items()) + [("dynamic_gap", gap), ("na_basis", na_basis), ("decision", decision), ("base_relation", relation)]:
        if value is not None:
            topic[key] = value
    if items is not None:
        topic["items"] = items
    if modules is not None:
        topic["reuse_modules"] = modules
    if deviation:
        topic.setdefault("deviation", {}).update({k: v for k, v in deviation.items() if v is not None})
    parity_items = {i.get("id"): i for i in ctx.load("PARITY.json").get("items", []) if isinstance(i, dict)}
    errors, _ = study_errors(ctx, tid, topic, parity_items, reuse_index(ctx.load("REUSE.json")))
    if errors:
        raise ValueError("Topic %s rejected:\n- %s" % (tid, "\n- ".join(errors)))
    topic.setdefault("history", []).append({"utc": now_utc(), "level": topic.get("evidence_level"), "decision": topic.get("decision", ""),
                                            "revision": topic.get("revision", 0),
                                            "evidence": [{"path": e["path"], "sha256": e["sha256"]} for e in added]})
    ctx.save("PRESENTATION.json", presentation)
    ctx.log("present_study", topic=tid, level=topic.get("evidence_level"), decision=topic.get("decision", ""),
            revision=topic.get("revision", 0), evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in added],
            locations=[e.get("location", "") for e in added])
    return ["%s %s: %s %s" % (tid, topic.get("name"), topic.get("evidence_level"), topic.get("decision", ""))] + messages


def present_reference(ctx: Context, runtime: str, assets: str, scene_types: Optional[List[str]], evidence: List[Tuple[str, str]],
                      notes: str = "") -> List[str]:
    if runtime not in REFERENCE_RUNTIME or assets not in REFERENCE_ASSETS:
        raise ValueError("runtime must be %s; assets must be %s" % ("/".join(REFERENCE_RUNTIME), "/".join(REFERENCE_ASSETS)))
    presentation = load_presentation(ctx)
    reference = presentation["reference"]
    if reference.get("original_runtime") != "UNKNOWN":
        reference.setdefault("history", []).append({k: reference.get(k) for k in ("original_runtime", "original_assets", "scene_types", "notes")})
    entries = [evidence_entry(ctx.root, p, k or "inventory", "reference inventory") for p, k in evidence]
    reference.update(original_runtime=runtime, original_assets=assets, notes=notes, utc=now_utc())
    reference.setdefault("evidence", []).extend(entries)
    if scene_types is not None:
        reference["scene_types"] = scene_types
    ctx.save("PRESENTATION.json", presentation)
    ctx.log("present_reference", runtime=runtime, assets=assets, evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in entries])
    lines = ["Reference: original runtime %s, original assets %s" % (runtime, assets)]
    if assets != "LEGAL_ORIGINAL":
        lines.append("No legal original pixels: the strongest presentation claim is 'structure confirmed from source/runtime'; visual equivalence stays NOT VERIFIED.")
    return lines


def present_frame(ctx: Context, scene: str, mode: str, trace: str = "", formula: str = "", layers: Optional[List[str]] = None,
                  walkthrough: str = "", asset_source: str = "placeholder") -> List[str]:
    if mode not in ("runtime", "source"):
        raise ValueError("mode must be runtime (per-primitive trace of the original's draw path) or source (walkthrough when the original cannot run)")
    if asset_source not in ASSET_SOURCES:
        raise ValueError("asset source must be " + "/".join(ASSET_SOURCES))
    presentation = load_presentation(ctx)
    frame = {"scene_type": scene, "mode": mode, "asset_source": asset_source, "subject": "original", "utc": now_utc()}
    if mode == "runtime":
        frame.update(trace=collect_files(ctx, [trace])[0], formula_check=collect_files(ctx, [formula])[0], layers=collect_files(ctx, layers or []))
    else:
        frame["walkthrough"] = collect_files(ctx, [walkthrough])[0]
    old = [f for f in presentation["frames"] if f.get("scene_type") == scene]
    presentation.setdefault("frames_history", []).extend(old)
    presentation["frames"] = [f for f in presentation["frames"] if f.get("scene_type") != scene] + [frame]
    ctx.save("PRESENTATION.json", presentation)
    ctx.log("present_frame", scene=scene, mode=mode, asset_source=asset_source,
            evidence=[{"path": f["path"], "sha256": f["sha256"]} for f in [frame.get("trace"), frame.get("formula_check"), frame.get("walkthrough")] + frame.get("layers", []) if f])
    problems = trace_problems(ctx, frame) if mode == "runtime" else []
    return ["Frame study %s recorded (%s, %s pixels)" % (scene, mode, asset_source)] + ["PROBLEM: " + p for p in problems]


def present_check(ctx: Context, cid: str, status: str, evidence: List[Tuple[str, str]], bind: List[str],
                  note: str = "", resolutions: Optional[List[str]] = None, swap: Optional[Dict[str, List[str]]] = None) -> List[str]:
    if cid not in PX_CHECKS:
        raise ValueError("check must be one of " + ", ".join(PX_CHECKS))
    if status not in ("PASS", "FAIL", "UNVERIFIED", "BLOCKED"):
        raise ValueError("status must be PASS, FAIL, UNVERIFIED or BLOCKED")
    presentation = load_presentation(ctx)
    check = presentation["experiment"]["checks"][cid]
    entries = [evidence_entry(ctx.root, p, k or "runtime-capture", "%s %s" % (cid, check.get("name", ""))) for p, k in evidence]
    for entry in entries:
        entry["subject"] = "base"
    if check.get("status") != "UNVERIFIED" or check.get("evidence"):
        check.setdefault("history", []).append({k: check.get(k) for k in ("status", "evidence", "bound_files", "core_fingerprint", "base_version", "swap", "resolutions", "study_revisions") if k in check})
    fingerprint = ctx.fingerprint(ctx.core_paths())
    check.update(status=status, evidence=entries, bound_files=collect_files(ctx, bind), core_fingerprint=fingerprint,
                 base_version=ctx.current_version(), note=note, utc=now_utc(), study_revisions=study_revisions(presentation))
    if resolutions is not None:
        check["resolutions"] = resolutions
    if swap is not None:
        check["swap"] = {key: collect_files(ctx, swap.get(key, [])) for key in ("before", "after", "ui_before", "ui_after")}
        baseline = presentation["experiment"]["checks"].get("PX02", {})
        check["swap"]["core_fingerprint_before"] = swap.get("core_fingerprint_before") or baseline.get("core_fingerprint") or fingerprint
    ctx.save("PRESENTATION.json", presentation)
    ctx.log("present_check", check=cid, status=status, core_fingerprint=fingerprint,
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in entries])
    data = snapshot(ctx)
    if status != "PASS":
        return ["%s = %s" % (cid, status)]
    return ["%s = %s" % (cid, status)] + ["PROBLEM: " + p for p in check_problems(ctx, cid, check, data)]


def present_compare(ctx: Context, status: str, evidence: List[Tuple[str, str]], reason: str = "", asset_source: str = "") -> List[str]:
    if status not in ("DONE", "UNAVAILABLE"):
        raise ValueError("status must be DONE or UNAVAILABLE")
    if status == "DONE" and asset_source not in ASSET_SOURCES:
        raise ValueError("--asset-source original|placeholder|own_test is required: say which pixels were on screen")
    presentation = load_presentation(ctx)
    entries = [evidence_entry(ctx.root, p, k or "comparison", "side-by-side with the original") for p, k in evidence]
    comparison = presentation.setdefault("original_comparison", {})
    if comparison.get("status") not in (None, "PENDING"):
        comparison.setdefault("history", []).append({k: comparison.get(k) for k in ("status", "evidence", "reason", "asset_source")})
    comparison.update(status=status, evidence=entries, reason=reason, asset_source=asset_source, utc=now_utc())
    ctx.save("PRESENTATION.json", presentation)
    ctx.log("present_compare", status=status, asset_source=asset_source, evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in entries])
    note = "" if status == "DONE" and asset_source == "original" else " — visual equivalence stays NOT VERIFIED"
    return ["Original comparison = %s%s" % (status, note)]


# ---------------------------------------------------------------- creator gates

CODE_SUFFIXES = {".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx", ".py", ".cs", ".gd", ".lua", ".cpp", ".cc", ".c", ".h", ".hpp",
                 ".java", ".kt", ".swift", ".rs", ".go", ".json", ".yaml", ".yml", ".glsl", ".frag", ".vert", ".hlsl"}
TERM_KEYS = {"id", "name", "title", "key", "label", "displayName", "display_name", "type", "text"}
GENERIC_TERMS = {"default", "player", "enemy", "enemies", "level", "levels", "scene", "scenes", "index", "config", "image", "images",
                 "sprite", "sprites", "sound", "sounds", "music", "button", "title", "name", "start", "pause", "score", "health",
                 "damage", "speed", "background", "foreground", "shadow", "effect", "effects", "particle", "particles", "true",
                 "false", "null", "string", "number", "value", "values", "width", "height", "normal", "linear", "additive", "multiply"}
RUN_STATUSES = ("RUNNING", "TARGET_REACHED", "HANDOFF_READY", "EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED")
FIRST_USE_KINDS = ("create_content_pack", "import_assets", "validate_assets", "build", "launch_runtime", "playtest",
                   "negative_missing_resource", "regression")
KIT_ITEMS = {"start_here": "Quick Start / START_HERE for creators", "scene_design_template": "scene design reference template",
             "camera_window_rules": "visible window and camera rules", "scene_geometry_contract": "scene and logic geometry contract",
             "character_spec": "character size, anchor and socket conventions",
             "layer_rules": "background, foreground, occlusion and effect organisation", "animation_import": "animation and atlas import",
             "ui_theme": "UI layout and theme replacement", "new_pack_tool": "tool that creates a new resource/content pack",
             "asset_validator": "asset integrity validator", "runnable_example": "runnable example content",
             "concept_to_runtime": "how concept art, design, asset production and integration relate (if the game needs concept art)"}
KIT_REQUIRED = {"start_here", "new_pack_tool", "asset_validator", "runnable_example"}
TRIAL_CHECKS = ("new_content", "replace_background", "replace_character", "replace_animation", "replace_ui",
                "gameplay_config", "playable_slice", "no_internal_research_needed")


def text_files(ctx: Context, paths: List[str]):
    for relative in paths:
        folder = safe_path(ctx.root, relative)
        if folder.exists():
            for path in iter_files(folder):
                if path.suffix.lower() in CODE_SUFFIXES:
                    yield path


def starter_terms(ctx: Context, state: Dict[str, Any]) -> Dict[str, str]:
    """Names that belong to example content: ids/names in starter data files and starter asset file names."""
    terms: Dict[str, str] = {}

    def add(value: Any, origin: str) -> None:
        if isinstance(value, str):
            value = value.strip()
            if (len(value) >= 4 and value.lower() not in GENERIC_TERMS and not re.fullmatch(r"[\d\W_]+", value)
                    and len(value) <= 64 and "\n" not in value):
                terms.setdefault(value, origin)

    def walk(node: Any, origin: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in TERM_KEYS:
                    add(value, origin)
                walk(value, origin)
        elif isinstance(node, list):
            for value in node:
                walk(value, origin)

    for relative in state.get("starter_paths", []):
        folder = safe_path(ctx.root, relative)
        if not folder.exists():
            continue
        for path in iter_files(folder):
            origin = rel(ctx.root, path)
            if path.suffix.lower() == ".json":
                try:
                    walk(json.loads(path.read_text(encoding="utf-8-sig")), origin)
                except (OSError, ValueError):
                    pass
            elif path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".ogg", ".mp3", ".wav", ".atlas", ".skel"):
                add(path.stem, origin)
    for term in state.get("content_terms", []):
        add(term, "RE_STATE.content_terms")
    return terms


def decoupling_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    """The core must not depend on starter/example content, nor name its characters, assets or texts."""
    state = data["state"]
    starters = [p for p in state.get("starter_paths", []) if isinstance(p, str)]
    if not starters:
        return ["declare starter_paths (replaceable example content shipped with the Base) in RE_STATE.json"]
    problems = []
    core = [PurePosixPath(p) for p in data["core"]]
    for starter in starters:
        if any(inside(PurePosixPath(starter), c) for c in core):
            problems.append("starter content %s lives inside the engine core; keep examples outside core_paths" % starter)
    terms = starter_terms(ctx, state)
    allowed = {(a.get("path"), a.get("term")) for a in state.get("decoupling_allow", []) if isinstance(a, dict) and text(a.get("reason"))}
    hits = []
    for path in text_files(ctx, data["core"]):
        relative = rel(ctx.root, path)
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for starter in starters:
            if starter.rstrip("/") + "/" in content.replace("\\", "/") and (relative, starter) not in allowed:
                hits.append("%s references starter path %s" % (relative, starter))
        for term, origin in terms.items():
            if (relative, term) in allowed:
                continue
            pattern = r"(?<![\w])%s(?![\w])" % re.escape(term) if re.fullmatch(r"[\w\- .]+", term, re.ASCII) else re.escape(term)
            if re.search(pattern, content):
                hits.append("%s names example content '%s' (from %s)" % (relative, term, origin))
    if hits:
        problems.append("Base core is coupled to example content (%d hits; first: %s). Move game-specific names, data and rules into content packs or extension modules, or justify in decoupling_allow" % (len(hits), hits[0]))
    return problems


def kit_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    kit = data.get("kit")
    if kit is None:
        return ["CREATOR_KIT.json is missing; run `gre.py upgrade`"]
    problems = []
    items = kit.get("items", {})
    for key in KIT_ITEMS:
        entry = items.get(key) if isinstance(items.get(key), dict) else {}
        if text(entry.get("na_reason")):
            if key in KIT_REQUIRED:
                problems.append("creator kit %s cannot be NOT_APPLICABLE" % key)
            continue
        paths = entry.get("paths", [])
        if not paths:
            problems.append("creator kit is missing %s (%s); give paths or a reason it does not apply to this game" % (key, KIT_ITEMS[key]))
            continue
        for relative in paths:
            try:
                if not safe_path(ctx.root, relative).exists():
                    problems.append("creator kit %s path %s does not exist" % (key, relative))
            except ValueError as exc:
                problems.append("creator kit %s: %s" % (key, exc))
    spec = data.get("first_use") or {}
    commands = {s.get("kind"): " ".join(command_argv(s, display=True)) for s in spec.get("steps", []) if isinstance(s, dict)}
    for key, kind in (("new_pack_tool", "create_content_pack"), ("asset_validator", "validate_assets")):
        paths = (items.get(key) or {}).get("paths", [])
        if paths and not any(p in commands.get(kind, "") for p in paths):
            problems.append("creator kit %s (%s) is not exercised by the first-use %s step" % (key, ", ".join(paths), kind))
    return problems


def command_argv(step: Dict[str, Any], display: bool = False) -> List[str]:
    argv = step.get("argv_windows") if os.name == "nt" and step.get("argv_windows") else step.get("argv_posix") if os.name != "nt" and step.get("argv_posix") else step.get("argv")
    argv = [str(a) for a in (argv or [])]
    return [("python" if a == "{python}" else a) if display else (sys.executable if a == "{python}" else a) for a in argv]


def first_use_spec_problems(ctx: Context, spec: Optional[Dict[str, Any]]) -> List[str]:
    if spec is None:
        return ["FIRST_USE.json is missing; run `gre.py upgrade`"]
    problems = []
    start_here = text(spec.get("start_here"))
    doc = ""
    try:
        doc = safe_path(ctx.root, start_here).read_text(encoding="utf-8", errors="ignore") if start_here else ""
    except (ValueError, OSError):
        doc = ""
    if not doc:
        problems.append("first-use start_here document is missing; creators must be able to follow one official Quick Start")
    steps = [s for s in spec.get("steps", []) if isinstance(s, dict)]
    kinds = [s.get("kind") for s in steps]
    for kind in FIRST_USE_KINDS:
        if kind not in kinds:
            problems.append("first-use has no %s step" % kind)
    for step in steps:
        label = "first-use step %s" % step.get("id")
        if step.get("kind") not in FIRST_USE_KINDS:
            problems.append(label + ": unknown kind")
        if not command_argv(step):
            problems.append(label + ": needs argv")
        if step.get("kind") == "negative_missing_resource":
            if not step.get("remove"):
                problems.append(label + ": must list the required resources it deletes")
            if step.get("expect", "failure") != "failure":
                problems.append(label + ": must expect failure (validation or build has to block missing resources)")
        elif doc and " ".join(command_argv(step, display=True)) not in doc:
            problems.append(label + ": command `%s` does not appear in %s; the Quick Start and the gate must describe the same steps" % (" ".join(command_argv(step, display=True)), start_here))
    return problems


def first_use_run(ctx: Context) -> List[str]:
    """Clone the committed Base into a clean directory and follow the creator Quick Start step by step."""
    import shutil
    import tempfile
    spec = ctx.load("FIRST_USE.json")
    problems = first_use_spec_problems(ctx, spec)
    if problems:
        raise ValueError("First-use spec is incomplete:\n- " + "\n- ".join(problems))
    head = git_text(ctx.root, ["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("first-use needs a Git repository with a commit: it tests the committed Base in a clean checkout")
    dirty = git_text(ctx.root, ["status", "--porcelain"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_dir = ctx.path("evidence") / ("first-use-" + stamp)
    counter = 1
    while log_dir.exists():
        counter += 1
        log_dir = ctx.path("evidence") / ("first-use-%s-%d" % (stamp, counter))
    log_dir.mkdir(parents=True)
    results, passed = [], True
    with tempfile.TemporaryDirectory(prefix="gre-first-use-") as tmp:
        checkout = Path(tmp) / "checkout"
        clone = subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ctx.root), str(checkout)], capture_output=True, text=True)
        if clone.returncode != 0:
            raise ValueError("clean clone failed: " + clone.stderr.strip())
        env = dict(os.environ)
        cache = Path(tmp) / "cache"
        for key in ("npm_config_cache", "YARN_CACHE_FOLDER", "PIP_CACHE_DIR", "XDG_CACHE_HOME", "PNPM_HOME"):
            env[key] = str(cache / key)
        for step in spec["steps"]:
            cwd = safe_path(checkout, step.get("cwd") or ".")
            for relative in step.get("remove", []) or []:
                target = safe_path(checkout, relative)
                if target.is_dir():
                    shutil.rmtree(str(target))
                elif target.exists():
                    target.unlink()
            argv = command_argv(step)
            resolved = shutil.which(argv[0]) or argv[0]
            started = datetime.now(timezone.utc)
            try:
                run = subprocess.run([resolved] + argv[1:], cwd=str(cwd), env=env, capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=int(step.get("timeout_min", 10)) * 60)
                code, out = run.returncode, run.stdout + run.stderr
            except subprocess.TimeoutExpired as exc:
                code, out = -9, "TIMEOUT after %s min\n%s" % (step.get("timeout_min", 10), exc.output or "")
            except OSError as exc:
                code, out = -1, "could not start: %s" % exc
            expect = step.get("expect", "failure" if step.get("kind") == "negative_missing_resource" else "success")
            ok = (code == 0) if expect == "success" else (code not in (0, -1, -9))
            log = log_dir / ("%02d-%s.log" % (len(results) + 1, re.sub(r"[^A-Za-z0-9_-]+", "-", str(step.get("id")))))
            create_new(log, ("$ %s\nexit=%s\n\n%s" % (" ".join(argv), code, out)).encode("utf-8"))
            results.append({"id": step.get("id"), "kind": step.get("kind"), "exit": code, "expect": expect, "ok": ok,
                            "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
                            "log": {"path": rel(ctx.root, log), "sha256": digest(log)}})
            if not ok:
                passed = False
                break
    record = {"utc": now_utc(), "commit": head, "dirty_worktree": bool(dirty), "core_fingerprint": ctx.fingerprint(ctx.core_paths()),
              "base_version": ctx.current_version(), "spec_steps_sha256": steps_hash(spec), "passed": passed,
              "steps": results}
    spec.setdefault("runs", []).append(record)
    ctx.save("FIRST_USE.json", spec)
    ctx.log("first_use", passed=passed, commit=head, evidence=[r["log"] for r in results])
    lines = ["Clean first-use run %s at %s (%d steps executed)" % ("PASSED" if passed else "FAILED", head[:12], len(results))]
    lines += ["  %-28s %s exit=%s (expected %s)" % (r["id"], "ok " if r["ok"] else "FAIL", r["exit"], r["expect"]) for r in results]
    if dirty:
        lines.append("NOTE: uncommitted changes were NOT tested; the clean checkout uses the last commit only.")
    return lines


def first_use_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    spec = data.get("first_use")
    problems = first_use_spec_problems(ctx, spec)
    if problems:
        return problems
    runs = spec.get("runs", [])
    if not runs:
        return ["run the clean first-use gate (`gre.py first-use run`)"]
    last = runs[-1]
    if not last.get("passed"):
        failed = next((s for s in last.get("steps", []) if not s.get("ok")), {})
        return ["the last clean first-use run failed at %s (see %s)" % (failed.get("id"), (failed.get("log") or {}).get("path"))]
    head = git_text(ctx.root, ["rev-parse", "HEAD"])
    if last.get("commit") != head:
        problems.append("the last clean first-use run tested %s, but HEAD is %s; re-run it" % (str(last.get("commit"))[:12], head[:12]))
    if last.get("core_fingerprint") != data["fingerprint"] or last.get("base_version") != data["current"]:
        problems.append("the engine core or Base version changed after the last clean first-use run; re-run it")
    if last.get("spec_steps_sha256") != steps_hash(spec):
        problems.append("FIRST_USE.json steps or Quick Start changed after the last run; re-run it")
    return problems


def steps_hash(spec: Dict[str, Any]) -> str:
    return hashlib.sha256(json_bytes({"start_here": spec.get("start_here"), "steps": spec.get("steps", [])})).hexdigest()


def contributors(ctx: Context, state: Dict[str, Any]) -> set:
    names = {e.get("agent") for e in ctx.history() if e.get("event") == "assign"}
    names |= {e.get("previous") for e in ctx.history() if e.get("event") == "assign"}
    names.add(state.get("assignment", {}).get("agent_label"))
    return {n for n in names if text(n)}


def core_manifest(ctx: Context, paths: List[str]) -> Dict[str, str]:
    manifest = {}
    for relative in paths:
        folder = safe_path(ctx.root, relative)
        if folder.exists():
            for path in iter_files(folder):
                manifest[rel(ctx.root, path)] = digest(path)
    return manifest


def trial_start(ctx: Context, agent: str, independence: str, docs: List[str]) -> List[str]:
    if independence not in REVIEW_MODES[:3]:
        raise ValueError("independence must be self_review, separate_context_same_environment or independent_reviewer")
    for relative in docs:
        if not safe_path(ctx.root, relative).is_file():
            raise ValueError("creator document not found: " + relative)
    trials = ctx.load("REUSE_TRIAL.json")
    state = ctx.load("RE_STATE.json")
    record = {"id": "trial-%02d" % (len(trials.get("trials", [])) + 1), "agent": agent, "independence": independence,
              "docs": docs, "status": "RUNNING", "started_utc": now_utc(), "base_version": ctx.current_version(),
              "core_fingerprint": ctx.fingerprint(ctx.core_paths()), "core_manifest": core_manifest(ctx, ctx.core_paths()),
              "base_contributor": agent in contributors(ctx, state)}
    trials.setdefault("trials", []).append(record)
    ctx.save("REUSE_TRIAL.json", trials)
    ctx.log("reuse_trial_start", trial=record["id"], agent=agent, independence=independence)
    lines = ["Independent reuse trial %s started by %s with: %s" % (record["id"], agent, ", ".join(docs))]
    if record["base_contributor"] or independence != "independent_reviewer":
        lines.append("NOTE: %s worked on this Base or is not an independent reviewer; the trial can be recorded but cannot satisfy CREATOR_READY." % agent)
    return lines


def trial_finish(ctx: Context, result: str, checks: Dict[str, bool], evidence: List[Tuple[str, str]], assets: int, steps: int,
                 manual: List[str], minutes: Optional[float], unverified: List[str], notes: str = "") -> List[str]:
    if result not in ("PASS", "FAIL", "BLOCKED"):
        raise ValueError("result must be PASS, FAIL or BLOCKED")
    trials = ctx.load("REUSE_TRIAL.json")
    running = [t for t in trials.get("trials", []) if t.get("status") == "RUNNING"]
    if not running:
        raise ValueError("no running trial; start one with `gre.py reuse-trial start`")
    trial = running[-1]
    after = core_manifest(ctx, ctx.core_paths())
    before = trial.get("core_manifest", {})
    changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
    entries = [evidence_entry(ctx.root, p, k or "recording", "independent reuse trial") for p, k in evidence]
    trial.update(status=result, finished_utc=now_utc(), checks={k: bool(checks.get(k)) for k in TRIAL_CHECKS},
                 core_files_changed=changed, evidence=entries, assets=assets, steps=steps, manual_interventions=manual,
                 first_success_minutes=minutes, unverified=unverified, notes=notes)
    ctx.save("REUSE_TRIAL.json", trials)
    ctx.log("reuse_trial_finish", trial=trial["id"], result=result, core_files_changed=len(changed),
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in entries])
    lines = ["Trial %s = %s; core files changed: %d" % (trial["id"], result, len(changed))]
    lines += ["PROBLEM: " + p for p in trial_problems(ctx, trial, {"current": ctx.current_version(), "fingerprint": ctx.fingerprint(ctx.core_paths())})]
    return lines


def trial_problems(ctx: Context, trial: Optional[Dict[str, Any]], data: Dict[str, Any]) -> List[str]:
    if not trial:
        return ["no independent reuse trial yet: an Agent that did not build this Base must create a playable slice from the creator docs alone (`gre.py reuse-trial start`)"]
    if trial.get("status") != "PASS":
        return ["the latest independent reuse trial is %s%s" % (trial.get("status"), (": " + text(trial.get("notes"))) if text(trial.get("notes")) else "")]
    problems = []
    if trial.get("independence") != "independent_reviewer" or trial.get("base_contributor"):
        problems.append("trial agent %s is not independent of the Base development" % trial.get("agent"))
    if trial.get("core_files_changed"):
        problems.append("trial needed %d engine-core changes (%s); a playable slice must be possible without modifying the core" % (len(trial["core_files_changed"]), ", ".join(trial["core_files_changed"][:3])))
    missing = [k for k in TRIAL_CHECKS if not (trial.get("checks") or {}).get(k)]
    if missing:
        problems.append("trial did not demonstrate: " + ", ".join(missing))
    if not any(isinstance(e, dict) and e.get("kind") in ("recording", "runtime-capture") for e in trial.get("evidence", [])):
        problems.append("trial needs a recording of the playable slice")
    if trial.get("base_version") != data["current"] or trial.get("core_fingerprint") != data["fingerprint"]:
        problems.append("trial was run on another Base version or core; re-run it")
    return problems


def creator_candidate_problems(ctx: Context, data: Dict[str, Any]) -> List[str]:
    problems = ["Decoupling: " + p for p in decoupling_problems(ctx, data)]
    problems += ["Creator kit: " + p for p in kit_problems(ctx, data)]
    problems += ["Clean first-use: " + p for p in first_use_problems(ctx, data)]
    dirty = git_dirty(ctx, data)
    if dirty:
        problems.append("Git baseline: uncommitted changes under core/starter paths (%s); commit them so the clean checkout tests what you deliver" % ", ".join(dirty[:3]))
    return problems


def git_dirty(ctx: Context, data: Dict[str, Any]) -> List[str]:
    paths = list(data["core"]) + [p for p in data["state"].get("starter_paths", []) if isinstance(p, str)]
    if not paths:
        return []
    output = git_text(ctx.root, ["status", "--porcelain", "--"] + paths)
    if output.startswith("not available"):
        return []
    return [line[3:] for line in output.splitlines() if line.strip()]


def kit_set(ctx: Context, item: str, paths: List[str], na_reason: str = "") -> List[str]:
    if item not in KIT_ITEMS:
        raise ValueError("kit item must be one of " + ", ".join(KIT_ITEMS))
    kit = ctx.load("CREATOR_KIT.json")
    entry = {"paths": [], "na_reason": na_reason, "utc": now_utc()} if na_reason else {"paths": paths, "na_reason": "", "utc": now_utc()}
    for relative in paths:
        safe_path(ctx.root, relative)
    old = kit.setdefault("items", {}).get(item)
    if old:
        kit.setdefault("history", []).append({"item": item, "previous": old})
    kit["items"][item] = entry
    ctx.save("CREATOR_KIT.json", kit)
    ctx.log("kit", item=item, paths=paths, na_reason=na_reason)
    return ["Creator kit %s = %s" % (item, ", ".join(paths) or "N/A: " + na_reason)]


def export_handoff(ctx: Context) -> List[str]:
    """Write the creator handoff contract consumed by game-creation-polish (never overwrites earlier exports)."""
    data = snapshot(ctx)
    derived = derive_level(ctx, data)
    kit = data.get("kit") or {}
    files = []
    for key, entry in (kit.get("items") or {}).items():
        for relative in entry.get("paths", []):
            files += [dict(f, kit_item=key) for f in collect_files(ctx, [relative])] if safe_path(ctx.root, relative).exists() else []
    for relative in ("BASE_HANDOFF.md",):
        if ctx.path(relative).is_file():
            files.append({"path": rel(ctx.root, ctx.path(relative)), "sha256": digest(ctx.path(relative)), "kit_item": "base_handoff"})
    runs = (data.get("first_use") or {}).get("runs", [])
    trials = (data.get("trial") or {}).get("trials", [])
    gates = {g.get("id"): g.get("status") for g in data["gates"].get("gates", []) if isinstance(g, dict)}
    nxt = LEVELS[min(level_index(derived) + 1, len(LEVELS) - 1)]
    contract = {"schema_version": "creator-handoff-1", "producer": "game-reverse-engineering %s" % SKILL_VERSION,
                "created_utc": now_utc(), "base_id": ctx.base_id, "base_version": data["current"], "level": derived,
                "git_head": git_text(ctx.root, ["rev-parse", "HEAD"]), "core_paths": data["core"], "core_fingerprint": data["fingerprint"],
                "starter_paths": data["state"].get("starter_paths", []), "fidelity": fidelity(data),
                "rights": {"RE01": gates.get("RE01", "missing"), "RE02": gates.get("RE02", "missing"), "RE03": gates.get("RE03", "missing"),
                           "note": RESIDUAL_RISK},
                "first_use": {"passed": bool(runs and runs[-1].get("passed")), "commit": runs[-1].get("commit") if runs else ""},
                "independent_reuse": {"status": trials[-1].get("status") if trials else "NOT_RUN",
                                      "agent": trials[-1].get("agent") if trials else ""},
                "open_gaps": level_problems(ctx, nxt, data)[:20] if derived != LEVELS[-1] else [],
                "files": files}
    folder = ctx.base_dir / "handoff" / data["current"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = folder / ("%s-CREATOR_HANDOFF.json" % stamp)
    counter = 1
    while not create_new(destination, json_bytes(contract)):
        counter += 1
        destination = folder / ("%s-%d-CREATOR_HANDOFF.json" % (stamp, counter))
    ctx.log("export", level=derived, evidence=[{"path": rel(ctx.root, destination), "sha256": digest(destination)}])
    lines = ["Creator handoff written: %s (level %s)" % (rel(ctx.root, destination), derived)]
    if level_index(derived) < LEVELS.index("CREATOR_CANDIDATE"):
        lines.append("NOTE: below CREATOR_CANDIDATE; game-creation-polish will treat this Base as not ready for production.")
    return lines


def stop(ctx: Context, status: str, reason: str) -> List[str]:
    if status not in RUN_STATUSES:
        raise ValueError("status must be one of " + ", ".join(RUN_STATUSES))
    if status in ("EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED") and not text(reason):
        raise ValueError(status + " needs a truthful --reason (what blocks, what was tried, how to unblock)")
    state = ctx.load("RE_STATE.json")
    if status == "TARGET_REACHED":
        data = snapshot(ctx)
        if level_index(derive_level(ctx, data)) < level_index(state.get("target_level")):
            problems = level_problems(ctx, state.get("target_level"), data)
            raise ValueError("Target %s not reached; keep working:\n- %s" % (state.get("target_level"), "\n- ".join(problems[:8])))
    state["run"] = {"status": status, "reason": reason, "utc": now_utc()}
    ctx.save("RE_STATE.json", state)
    ctx.log("run_status", status=status, reason=reason)
    return ["Run status = %s" % status]


def base_bump(ctx: Context, version: str, summary: str) -> List[str]:
    if not VERSION_RE.fullmatch(version) or not text(summary):
        raise ValueError("base bump needs --version like 1.2.0 and --summary (what changed, breaking or not)")
    path = ctx.base_dir / "BASE.json"
    base = load_json(path)
    if any(v.get("version") == version for v in base.get("versions", [])):
        raise ValueError("version already exists: " + version)
    base.setdefault("versions", []).append({"version": version, "readiness": "NONE", "frozen": False, "summary": summary, "created_utc": now_utc()})
    base["current_version"] = version
    save_json(path, base)
    ctx.log("base_bump", version=version, summary=summary)
    return ["Base %s current version is now %s; every level must be re-verified for it" % (ctx.base_id, version)]


def base_freeze(ctx: Context) -> List[str]:
    data = snapshot(ctx)
    derived = derive_level(ctx, data)
    if level_index(derived) < LEVELS.index("CREATOR_CANDIDATE"):
        raise ValueError("only a CREATOR_CANDIDATE or CREATOR_READY version can be frozen as a production baseline (now %s)" % derived)
    path = ctx.base_dir / "BASE.json"
    base = load_json(path)
    for entry in base.get("versions", []):
        if entry.get("version") == data["current"]:
            entry.update(frozen=True, readiness=derived, frozen_utc=now_utc(), git_head=git_text(ctx.root, ["rev-parse", "HEAD"]))
    save_json(path, base)
    ctx.log("base_freeze", version=data["current"], level=derived)
    return ["Base %s@%s frozen at %s; later changes need `gre.py base bump`" % (ctx.base_id, data["current"], derived)]


# ---------------------------------------------------------------- levels

def snapshot(ctx: Context) -> Dict[str, Any]:
    state = ctx.load("RE_STATE.json")
    data = {"state": state, "parity": ctx.load("PARITY.json"), "reuse": ctx.load("REUSE.json"),
            "probes": ctx.load("PROBES.json"), "gates": ctx.load("GATES.json"), "current": ctx.current_version()}
    data["core"] = ctx.core_paths(state)
    data["fingerprint"] = ctx.fingerprint(data["core"])
    data["modules"] = reuse_index(data["reuse"])
    data["presentation"] = ctx.load("PRESENTATION.json") if ctx.path("PRESENTATION.json").is_file() else None
    for key, name in (("kit", "CREATOR_KIT.json"), ("first_use", "FIRST_USE.json"), ("trial", "REUSE_TRIAL.json")):
        data[key] = ctx.load(name) if ctx.path(name).is_file() else None
    data["_item_errors"] = {}
    return data


def cached_item_errors(ctx: Context, item: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
    cache = data.setdefault("_item_errors", {})
    key = item.get("id")
    if key not in cache:
        cache[key] = item_errors(ctx, item, data["modules"])[0]
    return cache[key]


def level_problems(ctx: Context, level: str, data: Dict[str, Any]) -> List[str]:
    target = level_index(level)
    if target == 0:
        return []
    problems = []
    current = data["current"]
    items = [i for i in data["parity"].get("items", []) if isinstance(i, dict)]
    gates = {g.get("id"): g for g in data["gates"].get("gates", []) if isinstance(g, dict)}
    re01 = gates.get("RE01")
    if not re01 or re01.get("status") != "PASS" or check_gate(re01, "RE01", ctx.root)[0]:
        problems.append("RE01 reuse/rights assessment is not PASS with evidence")
    modules = data["reuse"].get("modules", [])
    if not modules:
        problems.append("REUSE.json lists no modules; assess the reference's code and assets first")
    elif any(isinstance(m, dict) and m.get("decision") == "REVIEW" for m in modules):
        problems.append("REUSE.json still has REVIEW modules")
    problems += reuse_errors(ctx, data["reuse"], data["core"])[:3]
    problems += discovery_problems(data["parity"])
    groups = [g for g, lv in GROUP_MIN_LEVEL.items() if level_index(lv) <= target]
    for item in items:
        if DOMAIN_GROUP.get(item.get("domain")) not in groups:
            continue
        structural = cached_item_errors(ctx, item, data)
        if structural:
            problems.append(structural[0])
            continue
        if item_scope(item) != "core":
            continue
        problem = item_counts(ctx, item, current, data["core"], data.get("presentation"))
        if problem:
            problems.append("%s %s: %s" % (item.get("id"), item.get("name"), problem))
    for domain, group in DOMAIN_GROUP.items():
        if group not in groups:
            continue
        domain_items = [i for i in items if i.get("domain") == domain]
        if not domain_items:
            problems.append("domain %s has no items" % domain)
        elif domain not in OPTIONAL_DOMAINS and not any(item_counts(ctx, i, current, data["core"], data.get("presentation")) is None
                                                        and i.get("status") == "VERIFIED" for i in domain_items):
            problems.append("domain %s needs at least one VERIFIED capability (it cannot be entirely NOT_APPLICABLE or excluded)" % domain)
    if target >= LEVELS.index("PRESENTATION_READY"):
        problems += ["Presentation Reconstruction Gate: " + p for p in presentation_problems(ctx, data)]
    if target >= LEVELS.index("CREATOR_CANDIDATE"):
        probe_problems, valid = probe_errors(ctx, data["probes"], data)
        required = data["probes"].get("required_probes", 2)
        if not isinstance(required, int) or required < 2:
            problems.append("required_probes must be at least 2")
            required = 2
        if len(valid) < required or probe_problems:
            problems.append("Creator production test needs %d valid probes (two clearly different original visual configurations, a real gameplay change each, a complete short loop, all on one unchanged core; valid: %d)" % (required, len(valid)))
            problems += probe_problems[:5]
        for item in items:
            if item.get("status") == "VERIFIED" and item_scope(item) == "core" and item.get("reusable_for_new_games") is not True:
                problems.append("%s is VERIFIED but not reusable_for_new_games; a core capability must be usable by new games" % item.get("id"))
        problems += creator_candidate_problems(ctx, data)
    if target >= LEVELS.index("CREATOR_READY"):
        trials = (data.get("trial") or {}).get("trials", [])
        problems += ["Independent reuse: " + p for p in trial_problems(ctx, trials[-1] if trials else None, data)]
    return problems


def derive_level(ctx: Context, data: Optional[Dict[str, Any]] = None) -> str:
    data = data or snapshot(ctx)
    if "_derived" not in data:
        result = "NONE"
        for level in LEVELS[1:]:
            if level_problems(ctx, level, data):
                break
            result = level
        data["_derived"] = result
    return data["_derived"]


def set_level(ctx: Context, level: str, note: str = "") -> List[str]:
    if level not in LEVELS:
        raise ValueError("level must be one of " + ", ".join(LEVELS))
    data = snapshot(ctx)
    state = data["state"]
    current = data["current"]
    claimed = state.get("claimed_level") if state.get("claimed_for_version") == current else "NONE"
    if level_index(level) > level_index(claimed) or level_index(level) > level_index(derive_level(ctx, data)):
        if level_index(level) > 0:
            problems = level_problems(ctx, level, data)
            if problems:
                raise ValueError("Cannot claim %s for %s@%s:\n- %s" % (level, ctx.base_id, current, "\n- ".join(problems[:12])))
    entry = {"utc": now_utc(), "level": level, "base_version": current, "core_fingerprint": data["fingerprint"],
             "git_head": git_text(ctx.root, ["rev-parse", "--short", "HEAD"]), "skill_version": SKILL_VERSION, "note": note}
    state.setdefault("level_history", []).append(entry)
    state.update(claimed_level=level, claimed_for_version=current)
    ctx.save("RE_STATE.json", state)
    ctx.log("level", **entry)
    return ["%s@%s level = %s (rights are tracked separately)" % (ctx.base_id, current, level)]


# ---------------------------------------------------------------- record updates

def find_item(parity: Dict[str, Any], iid: str) -> Dict[str, Any]:
    for item in parity.get("items", []):
        if isinstance(item, dict) and item.get("id") == iid:
            return item
    raise ValueError("Unknown parity item: " + iid)


def new_item(iid: str, domain: str, name: str, scope: str, origin: str) -> Dict[str, Any]:
    return {"id": iid, "domain": domain, "name": name, "required_for": GROUP_LEVEL[DOMAIN_GROUP[domain]],
            "scope": scope, "scope_reason": "", "origin": origin, "capability_class": "",
            "original": {"evidence_level": "UNKNOWN", "refs": [], "dynamic_gap": ""},
            "approach": "UNDECIDED", "reuse_modules": [], "research_basis": [], "code_paths": [],
            "value": {"impact": 2, "cost": "M"}, "status": "NOT_STARTED", "base_version": "", "verification": [],
            "differences": "", "design_note": "", "reusable_for_new_games": False, "na_basis": "", "history": []}


def parity_add(ctx: Context, iid: str, domain: str, name: str, scope: str = "core", origin: str = "discovered",
               source: str = "", evidence: str = "", kind: str = "", observed: str = "", local: bool = False,
               reason: str = "") -> List[str]:
    if domain not in DOMAIN_GROUP or not ITEM_ID_RE.fullmatch(iid) or not iid.startswith(domain + "-"):
        raise ValueError("Item id must look like %s-NN and match its domain" % domain)
    if scope not in SCOPES or origin not in ORIGINS:
        raise ValueError("invalid scope or origin")
    parity = ctx.load("PARITY.json")
    if any(i.get("id") == iid for i in parity.get("items", [])):
        raise ValueError("Parity item exists: " + iid)
    item = new_item(iid, domain, name, scope, origin)
    item["scope_reason"] = reason
    added = []
    if origin == "discovered":
        if source not in DISCOVERY_SOURCES or not evidence:
            raise ValueError("A discovered capability needs --source code|runtime|assets and --evidence (where it was found)")
        entry = evidence_entry(ctx.root, evidence, kind or "static-analysis", observed or "unique mechanic found", "local_research" if local else "")
        item["discovery"] = {"source": source, "evidence": [entry], "utc": now_utc()}
        added.append(entry)
    if origin == "extension":
        item["capability_class"] = "EXTENSION"
    errors, _ = item_errors(ctx, item, reuse_index(ctx.load("REUSE.json")))
    if errors:
        raise ValueError("Item %s rejected:\n- %s" % (iid, "\n- ".join(errors)))
    parity["items"].append(item)
    ctx.save("PARITY.json", parity)
    ctx.log("parity_add", item=iid, domain=domain, name=name, scope=scope, origin=origin,
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in added],
            locations=[e.get("location", "") for e in added])
    return ["Added %s capability %s (%s, scope %s)" % (origin, iid, name, scope)]


def discover(ctx: Context, source: str, status: str, evidence: str = "", kind: str = "", observed: str = "",
             reason: str = "", findings: Optional[List[str]] = None, local: bool = False) -> List[str]:
    if source not in DISCOVERY_SOURCES or status not in DISCOVERY_STATUSES:
        raise ValueError("source must be code/runtime/assets and status PENDING/DONE/UNAVAILABLE")
    parity = ctx.load("PARITY.json")
    discovery = parity.setdefault("discovery", load_json(template("PARITY.json"))["discovery"])
    entry = discovery.setdefault("sources", {}).setdefault(source, {"status": "PENDING", "evidence": [], "reason": "", "findings": []})
    added = []
    if evidence:
        record = evidence_entry(ctx.root, evidence, kind or "review", observed or "discovery review of " + source, "local_research" if local else "")
        entry.setdefault("evidence", []).append(record)
        added.append(record)
    for iid in findings or []:
        find_item(parity, iid)
    entry["findings"] = sorted(set(entry.get("findings", [])) | set(findings or []))
    entry.update(status=status, reason=reason or entry.get("reason", ""), utc=now_utc())
    errors, _ = discovery_errors(ctx, parity)
    mine = [e for e in errors if e.startswith("DISCOVERY %s" % source)]
    if mine:
        raise ValueError("\n".join(mine))
    discovery.setdefault("reviews", []).append({"utc": now_utc(), "source": source, "status": status, "findings": findings or [],
                                                "evidence": [{"path": e["path"], "sha256": e["sha256"]} for e in added]})
    ctx.save("PARITY.json", parity)
    ctx.log("discover", source=source, status=status, findings=findings or [],
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in added], locations=[e.get("location", "") for e in added])
    return ["Discovery from %s = %s (%d findings recorded)" % (source, status, len(entry["findings"]))]


def parity_set(ctx: Context, iid: str, status: Optional[str] = None, approach: Optional[str] = None,
               evidence: Optional[str] = None, kind: str = "", observed: str = "",
               original_level: Optional[str] = None, original_ref: Optional[str] = None, ref_kind: str = "",
               ref_observed: str = "", ref_local: bool = False, gap: Optional[str] = None,
               differences: Optional[str] = None, reusable: Optional[bool] = None, modules: Optional[List[str]] = None,
               research_basis: Optional[List[str]] = None, na_basis: Optional[str] = None, note: str = "",
               capability_class: Optional[str] = None, scope: Optional[str] = None, scope_reason: Optional[str] = None,
               design_note: Optional[str] = None, code_paths: Optional[List[str]] = None,
               impact: Optional[int] = None, cost: Optional[str] = None) -> List[str]:
    parity = ctx.load("PARITY.json")
    item = find_item(parity, iid)
    before = item.get("status")
    added = []
    if original_ref:
        location = "local_research" if ref_local else ""
        entry = evidence_entry(ctx.root, original_ref, ref_kind or "static-analysis", ref_observed or "reference evidence", location)
        item.setdefault("original", {}).setdefault("refs", []).append(entry)
        added.append(entry)
    if original_level is not None:
        if original_level not in EVIDENCE_LEVELS:
            raise ValueError("original level must be one of " + ", ".join(EVIDENCE_LEVELS))
        item.setdefault("original", {})["evidence_level"] = original_level
    if gap is not None:
        item.setdefault("original", {})["dynamic_gap"] = gap
    if approach is not None:
        if approach not in APPROACHES:
            raise ValueError("approach must be one of " + ", ".join(APPROACHES))
        item["approach"] = approach
    if capability_class is not None:
        if capability_class not in CLASSES:
            raise ValueError("class must be one of " + ", ".join(CLASSES))
        item["capability_class"] = capability_class
    if scope is not None:
        if scope not in SCOPES:
            raise ValueError("scope must be one of " + ", ".join(SCOPES))
        item["scope"] = scope
    for key, value in (("reuse_modules", modules), ("research_basis", research_basis), ("differences", differences),
                       ("reusable_for_new_games", reusable), ("na_basis", na_basis), ("scope_reason", scope_reason),
                       ("design_note", design_note), ("code_paths", code_paths)):
        if value is not None:
            item[key] = value
    if impact is not None or cost is not None:
        value = item.setdefault("value", {"impact": 2, "cost": "M"})
        if impact is not None:
            if impact not in (1, 2, 3):
                raise ValueError("impact must be 1, 2 or 3")
            value["impact"] = impact
        if cost is not None:
            if cost not in COST_SCORE:
                raise ValueError("cost must be S, M or L")
            value["cost"] = cost
    if evidence:
        entry = evidence_entry(ctx.root, evidence, kind, observed)
        item.setdefault("verification", []).append(entry)
        added.append(entry)
    if status is not None:
        if status not in ITEM_STATUSES:
            raise ValueError("status must be one of " + ", ".join(ITEM_STATUSES))
        item["status"] = status
    if item.get("status") == "VERIFIED" and (status == "VERIFIED" or evidence):
        item["base_version"] = ctx.current_version()
        item["verified_fingerprint"] = ctx.fingerprint(item_paths(item, ctx.core_paths()))
        item["verified_head"] = git_text(ctx.root, ["rev-parse", "--short", "HEAD"])
        presentation = ctx.load("PRESENTATION.json") if ctx.path("PRESENTATION.json").is_file() else None
        item["study_revisions"] = {t: study_revisions(presentation).get(t, 0) for t in topics_for_item(presentation, iid)}
    reuse = ctx.load("REUSE.json")
    errors, _ = item_errors(ctx, item, reuse_index(reuse))
    if errors and (item.get("status") in ("VERIFIED", "IMPLEMENTED", "NOT_APPLICABLE") or item_scope(item) == "excluded"
                   or capability_class is not None or scope is not None):
        raise ValueError("Parity item %s rejected:\n- %s" % (iid, "\n- ".join(errors)))
    record = {"utc": now_utc(), "from": before, "to": item.get("status"), "base_version": item.get("base_version", ""),
              "fingerprint": item.get("verified_fingerprint", ""), "class": item.get("capability_class", ""),
              "evidence": [{"path": e["path"], "sha256": e["sha256"]} for e in added], "note": note}
    item.setdefault("history", []).append(record)
    ctx.save("PARITY.json", parity)
    ctx.log("parity", item=iid, **{k: v for k, v in record.items() if k != "utc"},
            locations=[e.get("location", "") for e in added])
    return ["%s: %s -> %s%s" % (iid, before, item.get("status"), (" (+%d evidence)" % len(added)) if added else "")]


def reuse_set(ctx: Context, mid: str, name: str = "", origin: str = "", source_kind: Optional[str] = None,
              license_: Optional[str] = None, decision: Optional[str] = None, base_paths: Optional[List[str]] = None,
              research_paths: Optional[List[str]] = None, evidence: Optional[str] = None, observed: str = "",
              rights_basis: Optional[str] = None, notes: str = "", execution: Optional[str] = None,
              execution_note: Optional[str] = None) -> List[str]:
    check_slug(mid, "Module")
    reuse = ctx.load("REUSE.json")
    module = reuse_index(reuse).get(mid)
    if module is None:
        module = {"id": mid, "name": name or mid, "origin": origin, "source_kind": source_kind or "own_code", "license": "",
                  "decision": "REVIEW", "base_paths": [], "research_paths": [], "license_evidence": [], "rights_basis": "",
                  "notes": "", "history": []}
        reuse["modules"].append(module)
    before = module.get("decision")
    for key, value in (("name", name), ("origin", origin), ("notes", notes)):
        if value:
            module[key] = value
    for key, value in (("source_kind", source_kind), ("license", license_), ("decision", decision),
                       ("base_paths", base_paths), ("research_paths", research_paths), ("rights_basis", rights_basis),
                       ("execution", execution), ("execution_note", execution_note)):
        if value is not None:
            module[key] = value
    added = []
    if evidence:
        entry = evidence_entry(ctx.root, evidence, "license", observed or "license or grant text")
        module.setdefault("license_evidence", []).append(entry)
        added.append(entry)
    module.setdefault("history", []).append({"utc": now_utc(), "from": before, "to": module.get("decision")})
    errors = [e for e in reuse_errors(ctx, reuse, ctx.core_paths()) if e.startswith("REUSE %s:" % mid) or e.startswith("REUSE %s " % mid)]
    if errors:
        raise ValueError("Module %s rejected:\n- %s" % (mid, "\n- ".join(errors)))
    ctx.save("REUSE.json", reuse)
    ctx.log("reuse", module=mid, decision=module.get("decision"), evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in added])
    return ["Module %s: %s -> %s" % (mid, before, module.get("decision"))]


def gate_set(ctx: Context, gid: str, status: str, criteria: str = "", reviewer: str = "", independence: str = "self_review",
             subject: str = "", evidence: Optional[str] = None, observed: str = "", role: str = "", basis: str = "") -> List[str]:
    gates = ctx.load("GATES.json")
    gate = next((g for g in gates.get("gates", []) if g.get("id") == gid), None)
    if gate is None:
        raise ValueError("Unknown gate %s (run `gre.py upgrade` for gates added by newer versions)" % gid)
    if status not in GATE_STATUSES:
        raise ValueError("status must be one of " + ", ".join(GATE_STATUSES))
    if evidence:
        gate.setdefault("evidence", []).append(evidence_entry(ctx.root, evidence, "review-record", observed or "review record"))
    gate.update(status=status)
    if criteria:
        gate["criteria"] = criteria
    if subject:
        gate["subject_revision"] = subject
    if basis:
        gate["scope_basis"] = basis
    if reviewer:
        gate["reviewer"] = {"identity": reviewer, "independence": independence, "role": role}
    errors, _ = check_gate(gate, gid, ctx.root)
    if gid in APPROVAL_ROLES and status == "PASS" and not role:
        errors.append("%s: pass --role (%s)" % (gid, "/".join(sorted(APPROVAL_ROLES[gid]))))
    if gid == "RE01" and status == "PASS":
        reuse = ctx.load("REUSE.json")
        if not reuse.get("modules"):
            errors.append("RE01: REUSE.json lists no modules")
        if any(m.get("decision") == "REVIEW" for m in reuse.get("modules", [])):
            errors.append("RE01: unresolved REVIEW modules remain")
        errors += reuse_errors(ctx, reuse, ctx.core_paths())
    if errors:
        raise ValueError("Gate %s rejected:\n- %s" % (gid, "\n- ".join(errors)))
    ctx.save("GATES.json", gates)
    ctx.log("gate", gate=gid, status=status, evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in gate.get("evidence", [])])
    return ["Gate %s = %s" % (gid, status)]


def collect_files(ctx: Context, paths: List[str]) -> List[Dict[str, str]]:
    files = []
    for relative in paths:
        target = safe_path(ctx.root, relative)
        if not target.exists():
            raise ValueError("Probe path not found: " + relative)
        for path in iter_files(target):
            files.append({"path": rel(ctx.root, path), "sha256": digest(path)})
    if paths and not files:
        raise ValueError("No files found in " + ", ".join(paths))
    return files


def load_probe(probes: Dict[str, Any], pid: str) -> Dict[str, Any]:
    probe = next((p for p in probes.get("probes", []) if p.get("id") == pid), None)
    if probe is None:
        raise ValueError("Unknown probe %s; record it first with `gre.py probe`" % pid)
    return probe


def probe_messages(ctx: Context, pid: str) -> List[str]:
    data = snapshot(ctx)
    problems, _ = probe_errors(ctx, data["probes"], data)
    return ["PROBLEM: " + p for p in problems if ("PROBE %s" % pid) in p or ("%s/" % pid) in p or ("/%s" % pid) in p]


def probe_record(ctx: Context, pid: str, title: str, configs: List[str], assets: List[str],
                 evidence: Dict[str, List[Tuple[str, str]]], license_: str = "original_test_content",
                 core_changes: Optional[List[str]] = None, shared: Optional[List[str]] = None,
                 scenes: Optional[List[str]] = None) -> List[str]:
    check_slug(pid, "Probe")
    probes = ctx.load("PROBES.json")
    replaces = {}
    for category in PROBE_CATEGORIES:
        entries = [evidence_entry(ctx.root, path, kind or "runtime-capture", "%s replaced in probe %s" % (category, pid))
                   for path, kind in evidence.get(category, [])]
        replaces[category] = {"evidence": entries}
    old = [p for p in probes.get("probes", []) if p.get("id") == pid]
    record = {"id": pid, "title": title or pid, "base_version": ctx.current_version(), "license": license_,
              "config_files": collect_files(ctx, configs), "asset_files": collect_files(ctx, assets),
              "shared_files": collect_files(ctx, shared or []), "scene_files": collect_files(ctx, scenes or []),
              "replaces": replaces, "gameplay_changes": old[0].get("gameplay_changes", []) if old else [],
              "loop": old[0].get("loop") if old else None,
              "core_fingerprint": ctx.fingerprint(ctx.core_paths()),
              "core_changes_needed": list(core_changes or []), "recorded_utc": now_utc()}
    if old:
        probes.setdefault("probes_history", []).extend(old)
    probes["probes"] = [p for p in probes.get("probes", []) if p.get("id") != pid] + [record]
    ctx.save("PROBES.json", probes)
    ctx.log("probe", probe=pid, base_version=record["base_version"], core_fingerprint=record["core_fingerprint"],
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for c in replaces.values() for e in c["evidence"]])
    return ["Recorded probe %s (%d config, %d visual asset, %d shared files)" % (
        pid, len(record["config_files"]), len(record["asset_files"]), len(record["shared_files"]))] + probe_messages(ctx, pid)


def probe_gameplay(ctx: Context, pid: str, mechanic: str, items: List[str], configs: List[str],
                   evidence: List[Tuple[str, str]]) -> List[str]:
    probes = ctx.load("PROBES.json")
    probe = load_probe(probes, pid)
    parity = ctx.load("PARITY.json")
    for iid in items:
        find_item(parity, iid)
    change = {"mechanic": mechanic, "items": items, "config_files": collect_files(ctx, configs),
              "evidence": [evidence_entry(ctx.root, p, k or "recording", "gameplay change '%s' in %s" % (mechanic, pid)) for p, k in evidence],
              "base_version": ctx.current_version(), "core_fingerprint": ctx.fingerprint(ctx.core_paths()), "utc": now_utc()}
    probe.setdefault("gameplay_changes", []).append(change)
    ctx.save("PROBES.json", probes)
    ctx.log("probe_gameplay", probe=pid, mechanic=mechanic, items=items,
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in change["evidence"]])
    return ["Probe %s gameplay change recorded: %s" % (pid, mechanic)] + probe_messages(ctx, pid)


def probe_loop(ctx: Context, pid: str, covers: List[str], input_mode: str, evidence: List[Tuple[str, str]]) -> List[str]:
    probes = ctx.load("PROBES.json")
    probe = load_probe(probes, pid)
    covers = ["end" if c in ("win", "lose") else c for c in covers]
    loop = {"covers": sorted(set(covers)), "input": input_mode,
            "evidence": [evidence_entry(ctx.root, p, k or "recording", "complete short loop in %s" % pid) for p, k in evidence],
            "base_version": ctx.current_version(), "core_fingerprint": ctx.fingerprint(ctx.core_paths()), "utc": now_utc()}
    if probe.get("loop"):
        probe.setdefault("loop_history", []).append(probe["loop"])
    probe["loop"] = loop
    ctx.save("PROBES.json", probes)
    ctx.log("probe_loop", probe=pid, covers=loop["covers"], input=input_mode,
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for e in loop["evidence"]])
    return ["Probe %s loop recorded (%s, input %s)" % (pid, ",".join(loop["covers"]), input_mode)] + probe_messages(ctx, pid)


def evidence_add(ctx: Context, source: str, name: str = "", kind: str = "", observed: str = "") -> List[str]:
    """Copy a result into re/evidence/<utc>-<name>; never overwrites earlier evidence."""
    src = Path(source)
    if not src.is_absolute():
        src = ctx.root / src
    if not src.is_file():
        raise ValueError("Source file not found: " + source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", name or src.name).strip("-") or "evidence"
    destination = ctx.path("evidence") / ("%s-%s" % (stamp, clean))
    counter = 1
    while not create_new(destination, src.read_bytes()):
        counter += 1
        destination = ctx.path("evidence") / ("%s-%d-%s" % (stamp, counter, clean))
    relative = rel(ctx.root, destination)
    sha = digest(destination)
    ctx.log("evidence", evidence=[{"path": relative, "sha256": sha}], kind=kind, observed=observed)
    return ["Stored %s sha256=%s" % (relative, sha)]


# ---------------------------------------------------------------- value-driven priorities

def research_counts(state: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    tasks = {t.get("id"): t for t in state.get("tasks", [])}
    for entry in state.get("task_log", []):
        task = tasks.get(entry.get("id"), {})
        if entry.get("kind") == "research" and (entry.get("item") or task.get("item")):
            item = entry.get("item") or task.get("item")
            counts[item] = counts.get(item, 0) + 1
    return counts


def candidates(ctx: Context, data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Unfinished capabilities ranked by value: impact, blocking the next level, reuse value, evidence and cost."""
    data = data or snapshot(ctx)
    state = data["state"]
    limits = guards(state)
    derived = derive_level(ctx, data)
    target = state.get("target_level", "CREATOR_READY")
    next_level = LEVELS[min(level_index(derived) + 1, len(LEVELS) - 1)]
    researched = research_counts(state)
    ranked = []
    for item in data["parity"].get("items", []):
        if not isinstance(item, dict) or item_scope(item) == "excluded":
            continue
        problem = item_counts(ctx, item, data["current"], data["core"], data.get("presentation"))
        if problem is None:
            continue
        scope = item_scope(item)
        group_level = GROUP_MIN_LEVEL[DOMAIN_GROUP.get(item.get("domain"), "creator")]
        value = item.get("value") if isinstance(item.get("value"), dict) else {}
        score = {"core": 4, "optional": 1, "legacy": 0}[scope]
        reasons = [scope]
        if scope == "core" and level_index(group_level) <= level_index(next_level) and level_index(group_level) <= level_index(target):
            score += 4
            reasons.append("blocks " + next_level)
        if item.get("reusable_for_new_games") or DOMAIN_GROUP.get(item.get("domain")) == "creator" or item.get("origin") == "discovered":
            score += 2
            reasons.append("production value")
        impact = value.get("impact", 2) if value.get("impact") in (1, 2, 3) else 2
        score += impact
        cost = value.get("cost", "M") if value.get("cost") in COST_SCORE else "M"
        score += COST_SCORE[cost]
        level = item.get("original", {}).get("evidence_level")
        evidence_ready = level in ("VERIFIED", "STATIC_ONLY", "PROXY") or item.get("capability_class") == "EXTENSION"
        count = researched.get(item.get("id"), 0)
        if problem.startswith("stale"):
            action = "re-verify (code changed since verification)"
        elif item.get("status") == "IMPLEMENTED":
            action = "verify with runtime/measurement evidence"
        elif evidence_ready:
            score += 2
            action = "build (evidence is sufficient)"
        elif count >= limits["research_budget_per_item"]:
            score += 1
            action = ("stop researching (%d tasks spent): adopt a mature licensed component as REPLACEMENT, "
                      "or implement an independent EXTENSION with a design note" % count)
        else:
            action = "time-boxed research (%d of %d research tasks used)" % (count, limits["research_budget_per_item"])
        ranked.append({"id": item.get("id"), "name": item.get("name"), "score": score, "action": action,
                       "reasons": reasons, "problem": problem})
    if level_index(next_level) == LEVELS.index("PRESENTATION_READY") and level_index(target) >= LEVELS.index("PRESENTATION_READY"):
        gate = presentation_problems(ctx, data)
        if gate:
            ranked.append({"id": "presentation-reconstruction", "name": "Presentation Reconstruction Gate", "score": 11,
                           "action": "study the original's scene composition and run the Base scene experiment: " + gate[0],
                           "reasons": ["blocks PRESENTATION_READY"], "problem": gate[0]})
    if level_index(next_level) == LEVELS.index("CREATOR_CANDIDATE") and level_index(target) >= LEVELS.index("CREATOR_CANDIDATE"):
        problems, valid = probe_errors(ctx, data["probes"], data)
        if len(valid) < data["probes"].get("required_probes", 2) or problems:
            ranked.append({"id": "creator-probes", "name": "Creator production test", "score": 12,
                           "action": "build two original probes with gameplay changes and a complete loop",
                           "reasons": ["blocks CREATOR_CANDIDATE"], "problem": problems[0] if problems else "missing probes"})
        gates = creator_candidate_problems(ctx, data)
        if gates:
            ranked.append({"id": "creator-gates", "name": "Decoupling, creator kit and clean first-use", "score": 12,
                           "action": "make the Base usable by a new creator: " + gates[0],
                           "reasons": ["blocks CREATOR_CANDIDATE"], "problem": gates[0]})
    if level_index(next_level) == LEVELS.index("CREATOR_READY") and level_index(target) >= LEVELS.index("CREATOR_READY"):
        trials = (data.get("trial") or {}).get("trials", [])
        problems = trial_problems(ctx, trials[-1] if trials else None, data)
        if problems:
            ranked.append({"id": "independent-reuse", "name": "Independent Agent reuse trial", "score": 12,
                           "action": "hand the creator docs to an Agent that did not build the Base: " + problems[0],
                           "reasons": ["blocks CREATOR_READY"], "problem": problems[0]})
    ranked.sort(key=lambda c: (-c["score"], c["id"]))
    return ranked


def next_report(ctx: Context, limit: int = 5) -> str:
    ranked = candidates(ctx)
    if not ranked:
        return "No open capability gaps. Verify the target with `gre.py validate --strict-target`, then report and hand off."
    lines = ["# Next tasks by value (polish and docs come after these)"]
    for entry in ranked[:limit]:
        lines.append("%2d  %-14s %s — %s [%s]" % (entry["score"], entry["id"], entry["name"], entry["action"], ", ".join(entry["reasons"])))
    return "\n".join(lines)


# ---------------------------------------------------------------- tasks, guards, checkpoints

def recent_low_value_streak(state: Dict[str, Any]) -> int:
    streak = 0
    for entry in reversed(state.get("task_log", [])):
        if entry.get("kind") in LOW_VALUE_KINDS:
            streak += 1
        else:
            break
    return streak


def task_start(ctx: Context, tid: str, kind: str, desc: str, timeout_min: int = 30, item: str = "",
               pid: str = "", command: str = "", override_reason: str = "") -> List[str]:
    if kind not in TASK_KINDS:
        raise ValueError("kind must be one of " + ", ".join(TASK_KINDS))
    if kind == "research" and not item:
        raise ValueError("Research must serve a capability gap: pass --item <parity id>")
    parity = ctx.load("PARITY.json")
    if item:
        target_item = find_item(parity, item)
    if timeout_min <= 0:
        raise ValueError("timeout must be positive minutes")
    state = ctx.load("RE_STATE.json")
    limits = guards(state)
    messages = []
    if kind == "research" and target_item.get("status") not in ("IMPLEMENTED", "VERIFIED"):
        spent = research_counts(state).get(item, 0)
        if spent >= limits["research_budget_per_item"]:
            if not text(override_reason):
                raise ValueError("RESEARCH_BUDGET: %d research tasks already spent on %s without implementing it. Build with the evidence you have, "
                                 "adopt a mature licensed component (REPLACEMENT), or design an EXTENSION; pass --override-reason only with a new, specific hypothesis." % (spent, item))
            messages.append("Research budget override recorded: " + override_reason)
    if kind in LOW_VALUE_KINDS:
        data = snapshot(ctx)
        top = candidates(ctx, data)
        if (top and top[0]["score"] >= limits["high_priority_score"]
                and recent_low_value_streak(state) + 1 >= limits["polish_streak_limit"]):
            if not text(override_reason):
                raise ValueError("POLISH_BLOCKED: %d polish/docs tasks in a row while high-value gap %s (%s, score %d) is open. Work on it next (%s), or pass --override-reason."
                                 % (recent_low_value_streak(state), top[0]["id"], top[0]["name"], top[0]["score"], top[0]["action"]))
            messages.append("Low-value task override recorded: " + override_reason)
    task = next((t for t in state.get("tasks", []) if t.get("id") == tid), None)
    if task and task.get("status") == "ACTIVE":
        raise ValueError("Task %s is already ACTIVE; finish it, record it blocked/failed, or `task recover` it if it timed out" % tid)
    if task is None:
        task = {"id": tid, "failures": 0, "attempts": 0}
        state.setdefault("tasks", []).append(task)
    task.update(kind=kind, desc=desc, item=item, status="ACTIVE", started_utc=now_utc(), timeout_min=timeout_min,
                attempts=int(task.get("attempts", 0)) + 1, pid=pid, command=command, override_reason=override_reason)
    ctx.save("RE_STATE.json", state)
    ctx.log("task_start", task=tid, kind=kind, item=item, timeout_min=timeout_min, pid=pid, command=command,
            override_reason=override_reason)
    return ["Task %s started (%s, timeout %d min)" % (tid, kind, timeout_min)] + messages


def close_task(ctx: Context, state: Dict[str, Any], task: Dict[str, Any], status: str, result: str, summary: str) -> None:
    task.update(status=status, closed_utc=now_utc(), last_result=summary)
    if result in ("failed", "timeout"):
        task["failures"] = int(task.get("failures", 0)) + 1
    state.setdefault("task_log", []).append({"id": task["id"], "kind": task.get("kind"), "item": task.get("item", ""),
                                             "result": result, "started_utc": task.get("started_utc"),
                                             "closed_utc": task["closed_utc"]})


def task_done(ctx: Context, tid: str, result: str, summary: str) -> List[str]:
    if result not in TASK_RESULTS:
        raise ValueError("result must be one of " + ", ".join(TASK_RESULTS))
    if not text(summary):
        raise ValueError("--summary is required (what happened, with evidence paths)")
    state = ctx.load("RE_STATE.json")
    task = next((t for t in state.get("tasks", []) if t.get("id") == tid), None)
    if task is None:
        raise ValueError("Unknown task " + tid)
    close_task(ctx, state, task, {"ok": "DONE", "failed": "FAILED", "blocked": "BLOCKED"}[result], result, summary)
    ctx.save("RE_STATE.json", state)
    ctx.log("task_done", task=tid, result=result, summary=summary)
    messages = ["Task %s %s" % (tid, task["status"])]
    if task.get("failures", 0) >= guards(state)["same_failure_limit"]:
        messages.append("REPEATED_FAILURE: %s failed %d times; re-investigate the root cause instead of retrying the same approach" % (tid, task["failures"]))
    return messages


def is_stalled(task: Dict[str, Any], now: datetime) -> bool:
    started = parse_utc(task.get("started_utc", ""))
    return bool(task.get("status") == "ACTIVE" and started and now - started > timedelta(minutes=int(task.get("timeout_min", 30))))


def task_recover(ctx: Context, tid: str, action: str, summary: str, timeout_min: Optional[int] = None,
                 force: bool = False) -> List[str]:
    """Close a hung/timed-out task safely, then optionally restart it as a new attempt."""
    if action not in ("abandon", "restart"):
        raise ValueError("action must be abandon or restart")
    if not text(summary):
        raise ValueError("--summary is required: what you checked (process state, partial output) and what you stopped")
    state = ctx.load("RE_STATE.json")
    task = next((t for t in state.get("tasks", []) if t.get("id") == tid), None)
    if task is None or task.get("status") != "ACTIVE":
        raise ValueError("Task %s is not ACTIVE" % tid)
    if not is_stalled(task, datetime.now(timezone.utc)) and not force:
        raise ValueError("Task %s has not passed its timeout; check its output first, or pass --force with a reason in --summary" % tid)
    close_task(ctx, state, task, "TIMED_OUT", "timeout", summary)
    ctx.save("RE_STATE.json", state)
    ctx.log("task_recover", task=tid, action=action, pid=task.get("pid", ""), summary=summary)
    messages = ["Task %s TIMED_OUT (attempt %d). Stop only the process this task started%s; do not kill unrelated services."
                % (tid, task.get("attempts", 1), (" (pid %s)" % task["pid"]) if task.get("pid") else "")]
    if task.get("failures", 0) >= guards(state)["same_failure_limit"]:
        messages.append("REPEATED_FAILURE: %s has failed or timed out %d times; change the approach before restarting" % (tid, task["failures"]))
    if action == "restart":
        messages += task_start(ctx, tid, task.get("kind", "build"), task.get("desc", ""), timeout_min or int(task.get("timeout_min", 30)),
                               task.get("item", ""), override_reason=task.get("override_reason", ""))
    return messages


def guard_warnings(ctx: Context, data: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> List[str]:
    data = data or snapshot(ctx)
    state = data["state"]
    now = now or datetime.now(timezone.utc)
    limits = guards(state)
    warnings = []
    for task in state.get("tasks", []):
        if is_stalled(task, now):
            warnings.append("STALLED: task %s has run past its %s-minute timeout; check whether the tool hung, then `gre.py task recover --id %s --action restart|abandon`" % (task["id"], task.get("timeout_min"), task["id"]))
        if task.get("status") in ("FAILED", "TIMED_OUT") and task.get("failures", 0) >= limits["same_failure_limit"]:
            warnings.append("REPEATED_FAILURE: %s failed %d times; change the hypothesis or approach" % (task["id"], task["failures"]))
    log = state.get("task_log", [])
    recent = log[-limits["research_streak_limit"]:]
    if len(recent) >= limits["research_streak_limit"] and all(t.get("kind") == "research" for t in recent):
        since = parse_utc(recent[0].get("started_utc", "")) or now
        progressed = any(e.get("event") == "parity" and e.get("to") in ("IMPLEMENTED", "VERIFIED")
                         and (parse_utc(e.get("utc", "")) or since) >= since for e in ctx.history())
        if not progressed:
            warnings.append("RESEARCH_SPIN: the last %d tasks were research with no capability implemented or verified; build the Base for the largest gap now" % limits["research_streak_limit"])
    target = state.get("target_level", "CREATOR_READY")
    derived = derive_level(ctx, data)
    ranked = candidates(ctx, data) if level_index(derived) < level_index(target) else []
    if recent_low_value_streak(state) >= limits["polish_streak_limit"] and ranked:
        warnings.append("POLISH_SPIN: %d polish/docs tasks in a row while %s is unmet; next: %s" % (recent_low_value_streak(state), target, ranked[0]["id"]))
    if ranked and ranked[0]["score"] >= limits["high_priority_score"] and ranked[0]["id"] != "creator-probes":
        recent = log[-limits["neglect_limit"]:]
        if len(recent) >= limits["neglect_limit"] and all(t.get("item") != ranked[0]["id"] for t in recent):
            warnings.append("NEGLECTED_GAP: top gap %s (score %d) was not worked on in the last %d tasks" % (ranked[0]["id"], ranked[0]["score"], limits["neglect_limit"]))
    return warnings


def checkpoint(ctx: Context, next_action: str, resume_command: str = "", note: str = "") -> List[str]:
    if not text(next_action):
        raise ValueError("--next is required: the exact next task for whoever resumes")
    state = ctx.load("RE_STATE.json")
    state["checkpoint"] = {"utc": now_utc(), "next_action": next_action, "resume_command": resume_command, "note": note,
                           "head": git_text(ctx.root, ["rev-parse", "--short", "HEAD"])}
    ctx.save("RE_STATE.json", state)
    ctx.log("checkpoint", next_action=next_action, note=note)
    return ["Checkpoint saved: " + next_action]


def assign(ctx: Context, agent: str, scope: str) -> List[str]:
    state = ctx.load("RE_STATE.json")
    previous = state.get("assignment", {}).get("agent_label", "")
    state["assignment"] = {"agent_label": agent, "scope": scope, "since_utc": now_utc()}
    ctx.save("RE_STATE.json", state)
    ctx.log("assign", agent=agent, previous=previous, scope=scope)
    return ["Assigned %s (%s)%s" % (agent, scope, (" — previous: " + previous) if previous else "")]


# ---------------------------------------------------------------- validation, status, reports

def history_errors(ctx: Context, parity: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors, warnings = [], []
    events = ctx.history()
    last = None
    counts: Dict[str, int] = {}
    for index, event in enumerate(events, 1):
        if event.get("event") == "CORRUPT":
            errors.append("HISTORY line %d is not valid JSON" % event.get("line"))
            continue
        moment = parse_utc(event.get("utc", ""))
        if moment is None or (last and moment < last):
            errors.append("HISTORY line %d is out of order; history must be append-only" % index)
        last = moment or last
        if event.get("event") == "parity":
            counts[event.get("item")] = counts.get(event.get("item"), 0) + 1
        locations = event.get("locations", [])
        for position, entry in enumerate(event.get("evidence", []) or []):
            if not isinstance(entry, dict):
                continue
            local = position < len(locations) and locations[position] == "local_research"
            try:
                path = safe_path(ctx.root, entry.get("path", ""))
                if not path.is_file():
                    (warnings if local else errors).append("HISTORY: evidence %s recorded on %s is missing%s" % (entry.get("path"), event.get("utc"), " (local research)" if local else "; earlier results must not be deleted"))
                elif digest(path) != entry.get("sha256"):
                    errors.append("HISTORY: evidence %s changed after it was recorded; keep old results and add new files instead of overwriting" % entry.get("path"))
            except ValueError as exc:
                errors.append("HISTORY: " + str(exc))
    for item in parity.get("items", []):
        if isinstance(item, dict) and len(item.get("history", [])) < counts.get(item.get("id"), 0):
            errors.append("PARITY %s: item history is shorter than the append-only log; records were removed" % item.get("id"))
    return errors, warnings


def validate(root: Path, base_id: Optional[str] = None, strict: bool = False) -> Tuple[List[str], List[str]]:
    try:
        ctx = Context(root, base_id)
        data = snapshot(ctx)
    except ValueError as exc:
        return [str(exc)], []
    errors, warnings = [], []
    state = data["state"]
    for name in ("state", "parity", "reuse", "probes", "gates"):
        if data[name].get("schema_version") != GRE_SCHEMA:
            errors.append("%s: unsupported schema_version" % name.upper())
    if state.get("target_level") not in LEVELS[1:]:
        errors.append("RE_STATE.target_level is invalid")
    for path in data["core"]:
        try:
            if not safe_path(ctx.root, path).exists():
                warnings.append("core path %s does not exist yet" % path)
        except ValueError as exc:
            errors.append("core_paths: " + str(exc))
    errors += reuse_errors(ctx, data["reuse"], data["core"])
    warnings += reuse_warnings(data["reuse"])
    e, w = parity_errors(ctx, data["parity"], data["modules"])
    errors += e
    warnings += w
    probe_problems, _ = probe_errors(ctx, data["probes"], data)
    warnings += probe_problems
    presentation = data.get("presentation")
    if presentation is None:
        warnings.append("PRESENTATION.json is missing (records from before 1.2.0); run `gre.py upgrade` to add the presentation reconstruction study")
    else:
        if presentation.get("schema_version") != GRE_SCHEMA:
            errors.append("PRESENTATION: unsupported schema_version")
        items = {i.get("id"): i for i in data["parity"].get("items", []) if isinstance(i, dict)}
        for tid in PR_TOPICS:
            topic = presentation.get("study", {}).get(tid)
            if not isinstance(topic, dict):
                warnings.append("PRESENTATION: study topic %s is missing (added in a newer version); run `gre.py upgrade`" % tid)
                continue
            e, w = study_errors(ctx, tid, topic, items, data["modules"])
            errors += e
            warnings += w
        for cid in PX_CHECKS:
            check = presentation.get("experiment", {}).get("checks", {}).get(cid)
            if not isinstance(check, dict):
                warnings.append("PRESENTATION: experiment check %s is missing (added in a newer version); run `gre.py upgrade`" % cid)
            elif check.get("status") not in ("PASS", "FAIL", "UNVERIFIED", "BLOCKED"):
                errors.append("PRESENTATION: experiment check %s has an invalid status" % cid)
            elif check.get("status") == "PASS":
                warnings += ["Presentation experiment: " + p for p in check_problems(ctx, cid, check, data)]
        errors += evidence_misuse(data) + parity_conflicts(data)
    for key, name in (("kit", "CREATOR_KIT.json"), ("first_use", "FIRST_USE.json"), ("trial", "REUSE_TRIAL.json")):
        if data.get(key) is None:
            warnings.append("%s is missing (added in 2.0.0); run `gre.py upgrade`" % name)
    errors += device_path_errors(ctx)
    ids = []
    for gate in data["gates"].get("gates", []):
        if isinstance(gate, dict):
            ids.append(gate.get("id"))
            e, w = check_gate(gate, str(gate.get("id")), ctx.root)
            errors += e
            warnings += w
    if set(ids) - set(GATE_IDS) or len(ids) != len(set(ids)) or not {"RE01", "RE02"} <= set(ids):
        errors.append("GATES must contain RE01, RE02 (and RE03) exactly once")
    elif "RE03" not in ids:
        warnings.append("GATES has no RE03 (original assets and expression rights; added in 1.1.0); run `gre.py upgrade`")
    e, w = history_errors(ctx, data["parity"])
    errors += e
    warnings += w
    derived = derive_level(ctx, data) if not errors else "NONE"
    claimed = state.get("claimed_level", "NONE")
    history = state.get("level_history", [])
    claim_version = history[-1].get("skill_version", "1.0.0") if history else SKILL_VERSION
    if claimed not in LEVELS:
        errors.append("RE_STATE.claimed_level is invalid")
    elif state.get("claimed_for_version") and state.get("claimed_for_version") != data["current"] and claimed != "NONE":
        warnings.append("Level %s was claimed for base %s; current version %s needs re-verification" % (claimed, state.get("claimed_for_version"), data["current"]))
    elif level_index(claimed) > level_index(derived):
        problems = level_problems(ctx, claimed, data)
        message = "Claimed %s but evidence supports %s: %s" % (claimed, derived, problems[0] if problems else "")
        if version_tuple(claim_version) < version_tuple(SKILL_VERSION):
            warnings.append(message + " (claim made under gre %s rules; re-verify under %s)" % (claim_version, SKILL_VERSION))
        else:
            errors.append(message)
    if strict and level_index(derived) < level_index(state.get("target_level")):
        problems = level_problems(ctx, state.get("target_level"), data)
        errors.append("Strict target: %s not reached (%s): %s" % (state.get("target_level"), derived, "; ".join(problems[:3])))
    warnings += guard_warnings(ctx, data)
    warnings.append("Rights are separate from levels: " + rights_summary(ctx, data))
    warnings.append("This tool checks records, bytes, fingerprints and claims; it cannot judge gameplay, art quality or legal clearance.")
    return errors, warnings


def device_path_errors(ctx: Context) -> List[str]:
    """Shared records must use project-relative paths; device paths belong in ignored .production/local/."""
    errors = []
    for path in sorted(ctx.re_dir.glob("*.json")) + sorted(ctx.re_dir.glob("*.md")):
        match = ABS_PATH_RE.search(path.read_text(encoding="utf-8", errors="ignore"))
        if match:
            errors.append("%s contains a device-specific absolute path (%s); use project-relative paths" % (rel(ctx.root, path), match.group(0)[:40]))
    return errors


def rights_summary(ctx: Context, data: Dict[str, Any]) -> str:
    gates = {g.get("id"): g.get("status") for g in data["gates"].get("gates", []) if isinstance(g, dict)}
    re03 = gates.get("RE03", "missing")
    cleared = (gates.get("RE01") == "PASS" and re03 in ("PASS", "NOT_APPLICABLE") and gates.get("RE02") == "PASS")
    return ("code and component sources/licenses (RE01)=%s, original assets/expression rights (RE03)=%s, "
            "user publication approval (RE02)=%s; release rights record %s. %s"
            % (gates.get("RE01", "missing"), re03, gates.get("RE02", "missing"),
               "complete" if cleared else "INCOMPLETE", RESIDUAL_RISK))


def class_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {c: 0 for c in CLASSES}
    for item in items:
        if item.get("status") in ("IMPLEMENTED", "VERIFIED"):
            counts[item_class(item)[0]] += 1
    return counts


def status_report(ctx: Context) -> str:
    data = snapshot(ctx)
    state = data["state"]
    derived = derive_level(ctx, data)
    items = [i for i in data["parity"].get("items", []) if isinstance(i, dict)]
    counts: Dict[str, int] = {}
    for item in items:
        counts[str(item.get("status"))] = counts.get(str(item.get("status")), 0) + 1
    static = [i["id"] for i in items if i.get("original", {}).get("evidence_level") in ("STATIC_ONLY", "INFERRED", "PROXY")]
    discovered = [i["id"] for i in items if i.get("origin") == "discovered"]
    scopes = {s: sum(1 for i in items if item_scope(i) == s) for s in SCOPES}
    stale = [i["id"] for i in items if (item_counts(ctx, i, data["current"], data["core"], data.get("presentation")) or "").startswith("stale")]
    probe_problems, valid = probe_errors(ctx, data["probes"], data)
    visual_only = [p.get("id") for p in data["probes"].get("probes", []) if isinstance(p, dict) and not p.get("gameplay_changes")]
    gate = presentation_problems(ctx, data)
    lines = ["# Base %s@%s — reverse engineering (skill %s)" % (ctx.base_id, data["current"], SKILL_VERSION),
             "Target: %s | evidence supports: %s | claimed: %s (for %s)" % (state.get("target_level"), derived,
                                                                         state.get("claimed_level"), state.get("claimed_for_version") or "-"),
             "Rights (separate from levels): " + rights_summary(ctx, data),
             "Parity items: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())),
             "Scopes: " + ", ".join("%s=%d" % (k, v) for k, v in scopes.items()) + " | discovered (game-specific): %d %s" % (len(discovered), ", ".join(discovered[:6])),
             "Classes of built items: " + ", ".join("%s=%d" % (k, v) for k, v in class_counts(items).items()),
             "Static-only/inferred/proxy originals: %d %s" % (len(static), ", ".join(static[:8])),
             "Stale verifications (code changed): %d %s" % (len(stale), ", ".join(stale[:8])),
             "Discovery: " + ", ".join("%s=%s" % (s, ((data["parity"].get("discovery") or {}).get("sources", {}).get(s) or {}).get("status", "PENDING")) for s in DISCOVERY_SOURCES),
             "Creator probes: valid %d %s%s" % (len(valid), ", ".join(valid), (" | visual-only (not production evidence): " + ", ".join(visual_only)) if visual_only else ""),
             "Presentation Reconstruction Gate: " + ("PASS" if not gate else "FAIL (%d open: %s)" % (len(gate), gate[0])),
             "Presentation equivalence with the original: " + presentation_equivalence(data),
             "Mechanism fidelity: " + fidelity(data)["mechanism"],
             "Visual fidelity: " + fidelity(data)["visual"],
             "Creator gates (decoupling, kit, clean first-use): " + ("PASS" if not creator_candidate_problems(ctx, data) else "FAIL — " + creator_candidate_problems(ctx, data)[0]),
             "Independent reuse: " + ((data.get("trial") or {}).get("trials", [{}]) or [{}])[-1].get("status", "NOT_RUN"),
             "Run status: %s %s" % (state.get("run", {}).get("status", "RUNNING"), state.get("run", {}).get("reason", "")),
             "Core paths: %s (fingerprint %s)" % (", ".join(data["core"]) or "-", data["fingerprint"][:12] or "-"),
             "Assignment: %s" % (state.get("assignment", {}).get("agent_label") or "-"),
             "Checkpoint: %s — next: %s" % (state.get("checkpoint", {}).get("utc") or "-", state.get("checkpoint", {}).get("next_action"))]
    for task in state.get("tasks", []):
        if task.get("status") in ("ACTIVE", "BLOCKED", "FAILED", "TIMED_OUT"):
            lines.append("Task %s %s (%s): %s" % (task["id"], task["status"], task.get("kind"), task.get("desc")))
    if derived != LEVELS[-1]:
        nxt = LEVELS[level_index(derived) + 1]
        lines.append("To reach %s:" % nxt)
        lines += ["  - " + p for p in level_problems(ctx, nxt, data)[:8]]
    lines.append(next_report(ctx, 3))
    lines += ["WARNING: " + w for w in guard_warnings(ctx, data)]
    return "\n".join(lines)


def resume_report(ctx: Context) -> str:
    return "\n".join(["# Resume — read files, not old chats", status_report(ctx),
                      "Git HEAD: " + git_text(ctx.root, ["rev-parse", "--short", "HEAD"]),
                      "Working tree:\n" + (git_text(ctx.root, ["status", "--short"]) or "clean"),
                      "Steps: 1) for STALLED tasks check the recorded process, then `task recover`; 2) `gre.py env` on a new device;",
                      "3) run the Base build/tests (BASE.json known_commands); 4) continue with the checkpoint or `gre.py next`."])


def handoff_check(ctx: Context) -> List[str]:
    problems = []
    handoff = ctx.path("BASE_HANDOFF.md")
    content = handoff.read_text(encoding="utf-8", errors="replace") if handoff.is_file() else ""
    if not content or UNFILLED_MARKER in content:
        problems.append("BASE_HANDOFF.md is missing or still the blank template")
    for prompt in CREATOR_GUIDE:
        answer = next((line.split(prompt, 1)[1].strip() for line in content.splitlines() if line.strip().startswith("- " + prompt)), "")
        if not answer:
            problems.append("BASE_HANDOFF.md creator guide must answer: " + prompt.rstrip("："))
    state = ctx.load("RE_STATE.json")
    if not text(state.get("checkpoint", {}).get("next_action")) or not text(state.get("checkpoint", {}).get("utc")):
        problems.append("no checkpoint with a next action (`gre.py checkpoint --next ...`)")
    for task in state.get("tasks", []):
        if task.get("status") == "ACTIVE":
            problems.append("task %s is still ACTIVE; finish it, record it blocked/failed, or `task recover` it" % task["id"])
    errors, _ = validate(ctx.root, ctx.base_id)
    problems += errors
    return problems


def write_report(ctx: Context) -> List[str]:
    data = snapshot(ctx)
    derived = derive_level(ctx, data)
    names = {d["id"]: d["name"] for d in data["parity"].get("domains", []) if isinstance(d, dict)}
    items = [i for i in data["parity"].get("items", []) if isinstance(i, dict)]
    counts = class_counts(items)
    lines = ["# 能力等价矩阵报告 — %s@%s" % (ctx.base_id, data["current"]), "",
             "- 生成时间：%s；生成工具：gre.py %s" % (now_utc(), SKILL_VERSION),
             "- 证据支持的等级：**%s**（目标 %s）" % (derived, data["state"].get("target_level")),
             "- 已实现能力的来源：PARITY（有原版证据的等价能力）%d，REPLACEMENT（不同的合规实现）%d，EXTENSION（原创扩展，不是逆向成果）%d"
             % (counts["PARITY"], counts["REPLACEMENT"], counts["EXTENSION"]),
             "- 权利（与技术等级分开）：" + rights_summary(ctx, data),
             "- 核心指纹：%s" % (data["fingerprint"] or "（未设置核心路径）"), ""]
    for group, title in (("logic", "Logic"), ("presentation", "Presentation"), ("creator", "Creator")):
        lines += ["## %s" % title, "",
                  "| 条目 | 能力 | 范围 | 来源 | 原版证据 | 类别 | 方式 | 状态 | 验证证据 | 重要差异 | 可供新游戏 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for item in items:
            if DOMAIN_GROUP.get(item.get("domain")) != group:
                continue
            kinds = sorted({v.get("kind") for v in item.get("verification", []) if isinstance(v, dict)})
            problem = item_counts(ctx, item, data["current"], data["core"], data.get("presentation"))
            status = str(item.get("status")) + (" (过期)" if (problem or "").startswith("stale") else "")
            lines.append("| %s | %s / %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                item["id"], names.get(item["domain"], item["domain"]), item.get("name"), item_scope(item),
                item.get("origin", "template"), item.get("original", {}).get("evidence_level"), item_class(item)[0],
                item.get("approach"), status, ", ".join(kinds) or "—",
                (item.get("differences") or item.get("scope_reason") or "—").replace("|", "/"),
                "是" if item.get("reusable_for_new_games") else "否"))
        lines.append("")
    gate = presentation_problems(ctx, data)
    lines += ["## 表现系统重建（Presentation Reconstruction Gate）", "",
              "- 门禁：%s" % ("通过" if not gate else "未通过（%d 项未完成）" % len(gate)),
              "- 与原版的动态对照：" + presentation_equivalence(data),
              "- 机制保真（画面怎样组合出来）：" + fidelity(data)["mechanism"],
              "- 视觉保真（真实原版像素）：" + fidelity(data)["visual"], ""]
    presentation = data.get("presentation") or {}
    lines += ["| 调查项 | 内容 | 证据等级 | 证据数 | 可复用实现方式 |", "|---|---|---|---|---|"]
    for tid in PR_TOPICS:
        topic = presentation.get("study", {}).get(tid, {})
        lines.append("| %s | %s | %s | %d | %s |" % (tid, topic.get("name", ""), topic.get("evidence_level", "—"),
                     len(topic.get("refs", [])), (topic.get("reuse") or topic.get("na_basis") or "—").replace("|", "/")))
    lines += ["", "| 实验 | 内容 | 状态 |", "|---|---|---|"]
    for cid in PX_CHECKS:
        check = presentation.get("experiment", {}).get("checks", {}).get(cid, {})
        open_ = check_problems(ctx, cid, check, data) if check else ["missing"]
        lines.append("| %s | %s | %s |" % (cid, check.get("name", ""), "PASS" if not open_ else (open_[0].split(": ", 1)[-1]).replace("|", "/")))
    lines.append("")
    lines += ["## Creator 生产能力测试", ""]
    problems, valid = probe_errors(ctx, data["probes"], data)
    for probe in data["probes"].get("probes", []):
        lines.append("- %s「%s」：视觉资产 %d、共用资源 %d、玩法改动 %d、完整循环 %s —— %s" % (
            probe.get("id"), probe.get("title"), len(probe.get("asset_files", [])), len(probe.get("shared_files", []) or []),
            len(probe.get("gameplay_changes", []) or []), "有" if probe.get("loop") else "无",
            "有效" if probe.get("id") in valid else "无效"))
    lines += ["", "## 下一步（按价值排序）", "", "```text", next_report(ctx), "```"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = ctx.path("reports") / ("%s-capability-parity.md" % stamp)
    counter = 1
    while not create_new(destination, ("\n".join(lines) + "\n").encode("utf-8")):
        counter += 1
        destination = ctx.path("reports") / ("%s-%d-capability-parity.md" % (stamp, counter))
    relative = rel(ctx.root, destination)
    ctx.log("report", evidence=[{"path": relative, "sha256": digest(destination)}], level=derived)
    return ["Report written: " + relative,
            "Deliver to game production with `gre.py export` (creator handoff read by game-creation-polish)."]


def set_paths(ctx: Context, core: Optional[List[str]], starters: Optional[List[str]], terms: Optional[List[str]]) -> List[str]:
    state = ctx.load("RE_STATE.json")
    for value in (core or []) + (starters or []):
        safe_path(ctx.root, value)
    if core is not None:
        state["core_paths"] = core
    if starters is not None:
        state["starter_paths"] = starters
    if terms is not None:
        state["content_terms"] = terms
    ctx.save("RE_STATE.json", state)
    ctx.log("paths", core_paths=state.get("core_paths"), starter_paths=state.get("starter_paths", []))
    return ["core_paths=%s starter_paths=%s content_terms=%d" % (state.get("core_paths"), state.get("starter_paths", []), len(state.get("content_terms", [])))]


# ---------------------------------------------------------------- CLI

def split(value: Optional[str]) -> Optional[List[str]]:
    return None if value is None else [v.strip() for v in value.split(",") if v.strip()]


def bool_arg(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    raise ValueError("expected true/false: " + value)


def evidence_specs(values: List[str]) -> List[Tuple[str, str]]:
    return [strip_kind(v) for v in values]


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, help_text):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--base-id")
        return command

    p = add("init", "Start or adopt reverse engineering for a Base (empty folder, existing project or existing workspace)")
    p.add_argument("--base-version", default="0.1.0")
    p.add_argument("--code-path", default="")
    p.add_argument("--core-path", action="append", default=None)
    p.add_argument("--reference", action="append", default=[])
    p.add_argument("--name", default="")
    p.add_argument("--target", choices=LEVELS[1:], default="CREATOR_READY")
    p.add_argument("--basis", default="")
    p.add_argument("--agent", default="")
    p.add_argument("--starter-path", action="append", default=[])
    p = add("parity", "Add or update a capability parity item (history is appended)")
    p.add_argument("action", choices=("add", "set"))
    p.add_argument("--item", required=True)
    p.add_argument("--domain")
    p.add_argument("--name", default="")
    p.add_argument("--scope", choices=SCOPES)
    p.add_argument("--importance", choices=("core", "important", "minor"), help="deprecated alias of --scope")
    p.add_argument("--origin", choices=ORIGINS, default="discovered")
    p.add_argument("--source", choices=DISCOVERY_SOURCES, help="where a discovered capability was found")
    p.add_argument("--scope-reason")
    p.add_argument("--class", dest="capability_class", choices=CLASSES)
    p.add_argument("--design-note")
    p.add_argument("--code-paths")
    p.add_argument("--impact", type=int, choices=(1, 2, 3))
    p.add_argument("--cost", choices=tuple(COST_SCORE))
    p.add_argument("--status", choices=ITEM_STATUSES)
    p.add_argument("--approach", choices=APPROACHES)
    p.add_argument("--evidence")
    p.add_argument("--kind", default="")
    p.add_argument("--observed", default="")
    p.add_argument("--original-level", choices=EVIDENCE_LEVELS)
    p.add_argument("--original-ref")
    p.add_argument("--ref-kind", default="")
    p.add_argument("--ref-observed", default="")
    p.add_argument("--ref-local", action="store_true", help="reference lives in ignored research-private/")
    p.add_argument("--gap")
    p.add_argument("--differences")
    p.add_argument("--reusable")
    p.add_argument("--modules")
    p.add_argument("--research-basis")
    p.add_argument("--na-basis")
    p.add_argument("--note", default="")
    p = add("discover", "Record the game-specific capability discovery review for code, runtime or assets")
    p.add_argument("--source", required=True, choices=DISCOVERY_SOURCES)
    p.add_argument("--status", required=True, choices=DISCOVERY_STATUSES)
    p.add_argument("--evidence", default="")
    p.add_argument("--kind", default="")
    p.add_argument("--observed", default="")
    p.add_argument("--reason", default="")
    p.add_argument("--findings", default="")
    p.add_argument("--local", action="store_true")
    p = add("reuse", "Record a module's reuse decision")
    p.add_argument("--module", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--origin", default="")
    p.add_argument("--source-kind", choices=SOURCE_KINDS)
    p.add_argument("--license")
    p.add_argument("--decision", choices=REUSE_DECISIONS)
    p.add_argument("--base-paths")
    p.add_argument("--research-paths")
    p.add_argument("--evidence")
    p.add_argument("--observed", default="")
    p.add_argument("--rights-basis")
    p.add_argument("--execution", choices=EXECUTION_POLICIES)
    p.add_argument("--execution-note")
    p.add_argument("--notes", default="")
    p = add("gate", "Set RE01 (reuse/licenses), RE02 (user publication approval) or RE03 (original assets/expression rights)")
    p.add_argument("--id", required=True, choices=GATE_IDS)
    p.add_argument("--status", required=True, choices=GATE_STATUSES)
    p.add_argument("--criteria", default="")
    p.add_argument("--reviewer", default="")
    p.add_argument("--independence", default="self_review", choices=REVIEW_MODES)
    p.add_argument("--role", default="", help="user (RE02) / rights_holder or rights_holder_counsel (RE03)")
    p.add_argument("--subject", default="")
    p.add_argument("--basis", default="", help="scope basis for NOT_APPLICABLE")
    p.add_argument("--evidence")
    p.add_argument("--observed", default="")
    p = add("probe", "Record a Creator production probe (hashes files, fingerprints the core)")
    p.add_argument("--id", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--config", action="append", required=True)
    p.add_argument("--assets", action="append", required=True, help="probe-specific visual assets")
    p.add_argument("--shared", action="append", default=[], help="common fonts/tools/base resources that may be shared")
    p.add_argument("--evidence", action="append", default=[], help="category=path[:kind], categories: " + ",".join(PROBE_CATEGORIES))
    p.add_argument("--license", default="original_test_content")
    p.add_argument("--core-change", action="append", default=[])
    p.add_argument("--scene", action="append", default=[], help="scene configuration files this probe assembles (PX01 schema)")
    p = add("present", "Presentation reconstruction: reference inventory, study PR01-PR13 (Original Pipeline First), frame study, experiment PX01-PX09, comparison")
    p.add_argument("action", choices=("reference", "study", "frame", "check", "compare"))
    p.add_argument("--id", default="", help="PR01..PR13 for study, PX01..PX09 for check")
    p.add_argument("--decision", choices=tuple(DECISIONS))
    p.add_argument("--relation", choices=BASE_RELATIONS)
    p.add_argument("--original-method")
    p.add_argument("--base-method")
    p.add_argument("--difference")
    p.add_argument("--deviation-reason")
    p.add_argument("--deviation-impact")
    p.add_argument("--modules")
    p.add_argument("--correct", help="corrected fact; marks downstream verification stale")
    p.add_argument("--affects", help="downstream implementations that relied on the old conclusion")
    p.add_argument("--runtime", choices=REFERENCE_RUNTIME)
    p.add_argument("--assets", choices=REFERENCE_ASSETS)
    p.add_argument("--scene-types")
    p.add_argument("--scene", default="")
    p.add_argument("--mode", choices=("runtime", "source"))
    p.add_argument("--trace", default="")
    p.add_argument("--formula", default="")
    p.add_argument("--layer", action="append", default=[])
    p.add_argument("--walkthrough", default="")
    p.add_argument("--asset-source", default="")
    p.add_argument("--level", choices=EVIDENCE_LEVELS)
    p.add_argument("--status", default="")
    p.add_argument("--evidence", action="append", default=[], help="path[:kind] (repeatable)")
    p.add_argument("--observed", default="")
    p.add_argument("--local", action="store_true")
    p.add_argument("--gap")
    p.add_argument("--items")
    p.add_argument("--na-basis")
    for field in STUDY_FIELDS:
        p.add_argument("--" + field.replace("_", "-"))
    p.add_argument("--bind", action="append", default=[], help="scene/layout/anchor files this check depends on")
    p.add_argument("--resolution", action="append", default=[])
    p.add_argument("--before", action="append", default=[])
    p.add_argument("--after", action="append", default=[])
    p.add_argument("--ui-before", action="append", default=[])
    p.add_argument("--ui-after", action="append", default=[])
    p.add_argument("--reason", default="")
    p.add_argument("--note", default="")
    p = add("kit", "Record a creator kit item (paths, or --na with a reason)")
    p.add_argument("--item", required=True, choices=tuple(KIT_ITEMS))
    p.add_argument("--path", action="append", default=[])
    p.add_argument("--na", default="")
    p = add("first-use", "Check the clean first-use spec, or run it in a clean checkout of HEAD")
    p.add_argument("action", choices=("check", "run"))
    p = add("reuse-trial", "Independent Agent reuse trial (start records the core; finish records results)")
    p.add_argument("action", choices=("start", "finish"))
    p.add_argument("--agent", default="")
    p.add_argument("--independence", default="independent_reviewer", choices=REVIEW_MODES[:3])
    p.add_argument("--docs", default="")
    p.add_argument("--result", choices=("PASS", "FAIL", "BLOCKED"))
    p.add_argument("--passed-checks", default="", help="comma list of " + ",".join(TRIAL_CHECKS))
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--assets", type=int, default=0)
    p.add_argument("--steps", type=int, default=0)
    p.add_argument("--manual", action="append", default=[])
    p.add_argument("--minutes", type=float)
    p.add_argument("--unverified", action="append", default=[])
    p.add_argument("--notes", default="")
    p = add("paths", "Update core, starter and content-term settings used by the decoupling gate")
    p.add_argument("--core-path", action="append")
    p.add_argument("--starter-path", action="append")
    p.add_argument("--content-term", action="append")
    p = add("stop", "Record a truthful run status (TARGET_REACHED is refused until evidence supports it)")
    p.add_argument("--status", required=True, choices=RUN_STATUSES)
    p.add_argument("--reason", default="")
    p = add("base", "Base versioning: bump to a new version or freeze the current one as a production baseline")
    p.add_argument("action", choices=("bump", "freeze"))
    p.add_argument("--version", default="")
    p.add_argument("--summary", default="")
    p = add("probe-gameplay", "Record a meaningful gameplay change made through configuration or extension interfaces")
    p.add_argument("--id", required=True)
    p.add_argument("--mechanic", required=True)
    p.add_argument("--items", required=True, help="parity items exercised (L1-L5 or C1)")
    p.add_argument("--config", action="append", required=True)
    p.add_argument("--evidence", action="append", required=True, help="path[:kind]")
    p = add("probe-loop", "Record a complete short game loop played with normal input")
    p.add_argument("--id", required=True)
    p.add_argument("--covers", required=True, help="start,play,win|lose,result,restart")
    p.add_argument("--input", default="normal", choices=("normal", "scripted-normal", "debug"))
    p.add_argument("--evidence", action="append", required=True, help="path[:kind]")
    p = add("level", "Claim a delivery level; refused unless the evidence supports it")
    p.add_argument("--set", required=True, choices=LEVELS)
    p.add_argument("--note", default="")
    p = add("evidence", "Store a result file as new, never-overwritten evidence")
    p.add_argument("--file", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--kind", default="")
    p.add_argument("--observed", default="")
    p = add("task", "Start, finish or recover a task (timeouts, budgets and loop guards)")
    p.add_argument("action", choices=("start", "done", "recover"))
    p.add_argument("--id", required=True)
    p.add_argument("--kind", choices=TASK_KINDS)
    p.add_argument("--desc", default="")
    p.add_argument("--timeout-min", type=int)
    p.add_argument("--item", default="")
    p.add_argument("--pid", default="", help="process this task started (for safe recovery)")
    p.add_argument("--command", dest="task_command", default="")
    p.add_argument("--override-reason", default="")
    p.add_argument("--result", choices=TASK_RESULTS)
    p.add_argument("--summary", default="")
    p.add_argument("--recover-action", choices=("abandon", "restart"), default="restart")
    p.add_argument("--force", action="store_true")
    p = add("checkpoint", "Save the exact resume point")
    p.add_argument("--next", required=True)
    p.add_argument("--resume-command", default="")
    p.add_argument("--note", default="")
    p = add("assign", "Record which Agent works on this Base")
    p.add_argument("--agent", required=True)
    p.add_argument("--scope", default="")
    for name, help_text in (("status", "Read-only status"), ("resume", "Read-only resume briefing"),
                            ("next", "Value-ranked next tasks"), ("report", "Write a timestamped capability parity report"),
                            ("export", "Write the creator handoff contract for game-creation-polish"),
                            ("handoff", "Check handoff completeness"), ("env", "Re-probe this device (local file only)"),
                            ("upgrade", "Add fields of this Skill version to existing records (non-destructive)")):
        add(name, help_text)
    p = add("validate", "Validate records, evidence, fingerprints, history and level claims")
    p.add_argument("--strict-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            output = init(args.project, args.base_id or "core", args.base_version, args.code_path, args.core_path,
                          args.reference, args.name, args.target, args.basis, args.agent, args.starter_path)
        elif args.command == "validate":
            errors, warnings = validate(args.project, args.base_id, args.strict_target)
            for line in warnings:
                print("NOTE: " + line)
            for line in errors:
                print("ERROR: " + line)
            print("RECORD_CHECK_FAILED" if errors else "RECORD_CHECK_PASSED - not a gameplay/art/legal verdict")
            return 1 if errors else 0
        elif args.command == "env":
            ctx = Context(args.project, args.base_id)
            env = probe_environment(ctx.root)
            output = ["Device facts refreshed (local only): %s, python %s" % (env["os"], env["tools"]["python"]),
                      "Shared records unchanged. Re-run the Base build/tests before continuing."]
        else:
            ctx = Context(args.project, args.base_id)
            if args.command == "parity":
                scope = args.scope or {"core": "core", "important": "core", "minor": "optional", None: None}[args.importance]
                if args.action == "add":
                    if not args.domain or not args.name:
                        raise ValueError("parity add needs --domain and --name")
                    output = parity_add(ctx, args.item, args.domain, args.name, scope or "core", args.origin, args.source or "",
                                        args.evidence or "", args.kind, args.observed, args.ref_local, args.scope_reason or "")
                else:
                    output = parity_set(ctx, args.item, args.status, args.approach, args.evidence, args.kind, args.observed,
                                        args.original_level, args.original_ref, args.ref_kind, args.ref_observed, args.ref_local,
                                        args.gap, args.differences, bool_arg(args.reusable), split(args.modules),
                                        split(args.research_basis), args.na_basis, args.note, args.capability_class, scope,
                                        args.scope_reason, args.design_note, split(args.code_paths), args.impact, args.cost)
            elif args.command == "discover":
                output = discover(ctx, args.source, args.status, args.evidence, args.kind, args.observed, args.reason,
                                  split(args.findings), args.local)
            elif args.command == "reuse":
                output = reuse_set(ctx, args.module, args.name, args.origin, args.source_kind, args.license, args.decision,
                                   split(args.base_paths), split(args.research_paths), args.evidence, args.observed,
                                   args.rights_basis, args.notes, args.execution, args.execution_note)
            elif args.command == "gate":
                output = gate_set(ctx, args.id, args.status, args.criteria, args.reviewer, args.independence, args.subject,
                                  args.evidence, args.observed, args.role, args.basis)
            elif args.command == "probe":
                evidence: Dict[str, List[Tuple[str, str]]] = {}
                for spec in args.evidence:
                    category, _, rest = spec.partition("=")
                    path, kind = strip_kind(rest)
                    if category not in PROBE_CATEGORIES or not path:
                        raise ValueError("--evidence must be category=path[:kind] with category in " + ",".join(PROBE_CATEGORIES))
                    evidence.setdefault(category, []).append((path, kind))
                output = probe_record(ctx, args.id, args.title, args.config, args.assets, evidence, args.license,
                                      args.core_change, args.shared, args.scene)
            elif args.command == "present":
                specs = evidence_specs(args.evidence)
                if args.action == "study":
                    if len(specs) > 1:
                        raise ValueError("present study takes one --evidence per call (history keeps every call)")
                    path, kind = specs[0] if specs else (None, "")
                    output = present_study(ctx, args.id, args.level, path, kind, args.observed, args.local, args.gap,
                                           split(args.items), args.na_basis, args.decision, args.relation, split(args.modules),
                                           {"difference": args.difference, "reason": args.deviation_reason, "impact": args.deviation_impact},
                                           args.correct, split(args.affects),
                                           original_method=args.original_method, base_method=args.base_method,
                                           **{f: getattr(args, f) for f in STUDY_FIELDS})
                elif args.action == "reference":
                    output = present_reference(ctx, args.runtime or "UNKNOWN", args.assets or "UNKNOWN", split(args.scene_types), specs, args.note)
                elif args.action == "frame":
                    output = present_frame(ctx, args.scene, args.mode or "", args.trace, args.formula, args.layer, args.walkthrough,
                                           args.asset_source or "placeholder")
                elif args.action == "check":
                    swap = None
                    if args.before or args.after or args.ui_before or args.ui_after:
                        swap = {"before": args.before, "after": args.after, "ui_before": args.ui_before, "ui_after": args.ui_after}
                    output = present_check(ctx, args.id, args.status or "PASS", specs, args.bind, args.note,
                                           args.resolution or None, swap)
                else:
                    output = present_compare(ctx, args.status, specs, args.reason, args.asset_source)
            elif args.command == "kit":
                output = kit_set(ctx, args.item, args.path, args.na)
            elif args.command == "first-use":
                output = first_use_run(ctx) if args.action == "run" else (["First-use spec OK"] if not first_use_spec_problems(ctx, ctx.load("FIRST_USE.json")) else ["PROBLEM: " + p for p in first_use_spec_problems(ctx, ctx.load("FIRST_USE.json"))])
            elif args.command == "reuse-trial":
                if args.action == "start":
                    output = trial_start(ctx, args.agent, args.independence, split(args.docs) or [])
                else:
                    passed = set(split(args.passed_checks) or [])
                    output = trial_finish(ctx, args.result or "", {k: k in passed for k in TRIAL_CHECKS}, evidence_specs(args.evidence),
                                          args.assets, args.steps, args.manual, args.minutes, args.unverified, args.notes)
            elif args.command == "paths":
                output = set_paths(ctx, args.core_path, args.starter_path, args.content_term)
            elif args.command == "stop":
                output = stop(ctx, args.status, args.reason)
            elif args.command == "base":
                output = base_bump(ctx, args.version, args.summary) if args.action == "bump" else base_freeze(ctx)
            elif args.command == "probe-gameplay":
                output = probe_gameplay(ctx, args.id, args.mechanic, split(args.items) or [], args.config, evidence_specs(args.evidence))
            elif args.command == "probe-loop":
                output = probe_loop(ctx, args.id, split(args.covers) or [], args.input, evidence_specs(args.evidence))
            elif args.command == "level":
                output = set_level(ctx, args.set, args.note)
            elif args.command == "evidence":
                output = evidence_add(ctx, args.file, args.name, args.kind, args.observed)
            elif args.command == "task":
                if args.action == "start":
                    if not args.kind:
                        raise ValueError("task start needs --kind")
                    output = task_start(ctx, args.id, args.kind, args.desc, args.timeout_min or 30, args.item, args.pid,
                                        args.task_command, args.override_reason)
                elif args.action == "done":
                    if not args.result:
                        raise ValueError("task done needs --result")
                    output = task_done(ctx, args.id, args.result, args.summary)
                else:
                    output = task_recover(ctx, args.id, args.recover_action, args.summary, args.timeout_min, args.force)
            elif args.command == "checkpoint":
                output = checkpoint(ctx, args.next, args.resume_command, args.note)
            elif args.command == "assign":
                output = assign(ctx, args.agent, args.scope)
            elif args.command == "status":
                output = [status_report(ctx)]
            elif args.command == "resume":
                output = [resume_report(ctx)]
            elif args.command == "next":
                output = [next_report(ctx, 8)]
            elif args.command == "report":
                output = write_report(ctx)
            elif args.command == "export":
                output = export_handoff(ctx)
            elif args.command == "upgrade":
                output = upgrade(ctx)
            else:
                problems = handoff_check(ctx)
                print(status_report(ctx))
                print("Handoff check: " + ("COMPLETE" if not problems else "INCOMPLETE\n- " + "\n- ".join(problems)))
                return 1 if problems else 0
        for line in output:
            print(line)
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
