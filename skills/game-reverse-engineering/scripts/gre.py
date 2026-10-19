#!/usr/bin/env python3
"""Game Reverse Engineering Skill tool. Python 3.9+, standard library only.

Keeps the reverse-engineering and Base-building records of a Game Production v4
compatible workspace: capability parity matrix, reuse assessment, creator probes,
delivery levels (LOGIC_READY / PRESENTATION_READY / CREATOR_READY), tasks,
checkpoints and an append-only history. Never runs games, decompilers or builds;
never commits, pushes or deploys. Validation checks records, evidence bytes and
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
from typing import Any, Dict, List, Optional, Tuple

KIT_ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = "game-reverse-engineering"
SKILL_VERSION = "1.0.0"
GRE_SCHEMA = "gre-1.0"
V4_SCHEMA = "3.0"
V4_KIT_VERSION = "4.1.0"
SKILL_PATH = ".agents/skills/" + SKILL_NAME
WORKSPACE_FILE = ".production/WORKSPACE.json"
RE_DIRNAME = "re"
AGENTS_MARKERS = ("<!-- GAME_REVERSE_ENGINEERING_V1_BEGIN -->", "<!-- GAME_REVERSE_ENGINEERING_V1_END -->")
IGNORE_MARKER = "# GAME_REVERSE_ENGINEERING_LOCAL"
IGNORE_BLOCK = IGNORE_MARKER + "\n.production/local/\nresearch-private/\n"
UNFILLED_MARKER = "TEMPLATE_UNFILLED"

LEVELS = ["NONE", "LOGIC_READY", "PRESENTATION_READY", "CREATOR_READY"]
GROUP_LEVEL = {"logic": "LOGIC_READY", "presentation": "PRESENTATION_READY", "creator": "CREATOR_READY"}
DOMAIN_GROUP = {d: "logic" for d in ("L1", "L2", "L3", "L4", "L5", "L6")}
DOMAIN_GROUP.update({d: "presentation" for d in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8")})
DOMAIN_GROUP["C1"] = "creator"
OPTIONAL_DOMAINS = {"L3", "L4"}
ITEM_STATUSES = ["NOT_STARTED", "RESEARCHING", "INTERFACE_ONLY", "DOCUMENTED", "IMPLEMENTED", "VERIFIED", "NOT_APPLICABLE"]
NON_COUNTING = {"INTERFACE_ONLY", "DOCUMENTED"}
APPROACHES = ["UNDECIDED", "REUSE", "ADAPT", "REIMPLEMENT", "IMPROVE", "OMIT"]
EVIDENCE_LEVELS = ["VERIFIED", "STATIC_ONLY", "INFERRED", "PROXY", "UNKNOWN"]
DYNAMIC_KINDS = {"runtime-capture", "trace", "comparison", "measurement", "recording"}
VERIFY_KINDS = {"test", "runtime-capture", "measurement", "trace", "benchmark", "comparison", "recording"}
VISUAL_KINDS = {"runtime-capture", "measurement", "recording", "comparison"}
REUSE_DECISIONS = ["KEEP", "ADAPT", "REPLACE", "QUARANTINE", "REVIEW"]
SOURCE_KINDS = ["original_decompiled", "original_source", "open_source", "own_code", "third_party_library", "generated"]
TASK_KINDS = ["research", "build", "verify", "fix", "polish", "docs"]
TASK_RESULTS = ["ok", "failed", "blocked"]
REVIEW_MODES = ("self_review", "separate_context_same_environment", "independent_reviewer", "external_approval")
GATE_STATUSES = ("PASS", "FAIL", "UNVERIFIED", "BLOCKED", "NOT_APPLICABLE")
PROBE_CATEGORIES = ["character", "animation", "unit", "map", "visual_style"]
EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".cache", ".venv"}
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
ITEM_ID_RE = re.compile(r"(L[1-6]|P[1-8]|C1)-\d{2,}")


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
    env = load_json(path) if path.is_file() else load_json(template("v4/ENVIRONMENT.local.json"))
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


def check_gate(gate: Dict[str, Any], label: str, root: Path, approval: bool) -> List[str]:
    errors = []
    status = gate.get("status")
    if status not in GATE_STATUSES:
        return [label + ": invalid status"]
    if status == "NOT_APPLICABLE" and not text(gate.get("scope_basis")):
        errors.append(label + ": NOT_APPLICABLE requires a scope basis")
    if status != "PASS":
        return errors
    if not text(gate.get("criteria")):
        errors.append(label + ": PASS requires concrete criteria")
    if not text(gate.get("subject_revision")):
        errors.append(label + ": PASS requires subject_revision")
    reviewer = gate.get("reviewer") if isinstance(gate.get("reviewer"), dict) else {}
    independence = reviewer.get("independence")
    if not text(reviewer.get("identity")) or independence not in REVIEW_MODES:
        errors.append(label + ": PASS requires reviewer identity and actual independence")
    elif approval and independence != "external_approval":
        errors.append(label + ": commercial permission must come from the user/rights holder (external_approval); technical tests and Agent self-review cannot grant it")
    elif not approval and independence == "external_approval":
        errors.append(label + ": external_approval is reserved for the commercial permission gate")
    evidence = gate.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append(label + ": PASS requires evidence files, not only a claim")
    else:
        errors += check_evidence(evidence, root, label)[0]
    return errors


# ---------------------------------------------------------------- context

class Context:
    """One Base's GRE records inside a v4-compatible workspace."""

    def __init__(self, root: Path, base_id: Optional[str] = None):
        self.root = root.resolve()
        ws_path = self.root / WORKSPACE_FILE
        if not ws_path.is_file():
            if (self.root / ".production/PROJECT.json").is_file():
                raise ValueError("v3 single-game records found. Upgrade with game-production `project.py migrate` first, then run `gre.py init`.")
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


def core_fingerprint(root: Path, core_paths: List[str]) -> str:
    """Hash of every core file (path + content). Equal fingerprints mean the engine core is unchanged."""
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


# ---------------------------------------------------------------- init / adopt

def init(root: Path, base_id: str = "core", version: str = "0.1.0", code_path: str = "",
         core_paths: Optional[List[str]] = None, references: Optional[List[str]] = None,
         name: str = "", target: str = "CREATOR_READY", basis: str = "", agent: str = "") -> List[str]:
    root = root.resolve()
    if root == KIT_ROOT or KIT_ROOT in root.parents:
        raise ValueError("Select the workspace root, not the Skill folder.")
    if root.exists() and not root.is_dir():
        raise ValueError("Project is not a directory: " + str(root))
    if (root / ".production/PROJECT.json").is_file() and not (root / WORKSPACE_FILE).is_file():
        raise ValueError("v3 single-game records found. Upgrade with game-production `project.py migrate` first (references/MIGRATION_V3.md in the game-production Skill).")
    if target not in LEVELS[1:]:
        raise ValueError("target must be one of " + ", ".join(LEVELS[1:]))
    check_slug(base_id, "Base")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Version must look like 0.1.0")
    planned = install_plan(root)
    for destination, data in planned:
        if destination.exists() and (not destination.is_file() or not same_text_bytes(destination.read_bytes(), data)):
            raise ValueError("Installed Skill differs; review and merge manually: " + str(destination))
    messages = []
    root.mkdir(parents=True, exist_ok=True)
    added = sum(1 for destination, data in planned if create_new(destination, data))
    messages.append("Skill files added: %d (identical existing files kept)" % added)

    ws_path = root / WORKSPACE_FILE
    if ws_path.is_file():
        workspace = load_json(ws_path)
        if workspace.get("schema_version") != V4_SCHEMA:
            raise ValueError("WORKSPACE.json schema %s is not supported (expected %s)" % (workspace.get("schema_version"), V4_SCHEMA))
        messages.append("Using existing v4 workspace; its records are kept.")
        ws_changed = False
    else:
        workspace = load_json(template("v4/WORKSPACE.json"))
        existing_code = bool(code_path) and code_path != "." and safe_path(root, code_path).is_dir() and any(safe_path(root, code_path).iterdir())
        existing_code = existing_code or (code_path == "." and any(p.name not in (".agents", ".production") for p in root.iterdir()))
        workspace.update(workspace_id="ws-" + uuid.uuid4().hex[:12], name=name or root.name)
        workspace["intake"].update(status="IN_PROGRESS", route="adopt_existing" if existing_code else "new_research")
        workspace["run"]["scope"] = {"target": "base", "required_readiness": "RELEASE_CANDIDATE", "game_quota": 0, "games": [],
                                     "basis": basis or "Reverse engineering and Base building only (game-reverse-engineering); no games."}
        workspace["run"]["allowed_stages"] = ["R0", "R1", "R2"]
        for relative, source in ((".production/BACKLOG.md", "v4/BACKLOG.md"), (".production/HANDOFF.md", "v4/HANDOFF.md"),
                                 (".production/RIGHTS_LEDGER.md", "v4/RIGHTS_LEDGER.md")):
            create_new(safe_path(root, relative), template(source).read_bytes())
        ws_changed = True
        messages.append("Created v4-compatible workspace (scope: base only, no games).")
    if references and not workspace.get("research"):
        workspace["research"] = [{"id": "research-01", "sources": list(references), "records": ".production/research/research-01"}]
        workspace["focus"]["research"] = "research-01"
        create_new(safe_path(root, ".production/research/research-01/MECHANICS_MATRIX.md"), template("v4/MECHANICS_MATRIX.md").read_bytes())
        ws_changed = True

    entry = next((b for b in workspace.get("bases", []) if isinstance(b, dict) and b.get("id") == base_id), None)
    if entry is None:
        if not code_path:
            raise ValueError("Registering a new Base needs --code-path (where the Base engine lives or will live).")
        code_root = root if code_path == "." else safe_path(root, code_path)
        records = workspace.get("layout", {}).get("base_records_dir", ".production/bases") + "/" + base_id
        folder = safe_path(root, records)
        base = load_json(template("v4/base/BASE.json"))
        base.update(base_id=base_id, name=name or base_id, code_path=code_path, current_version=version,
                    research_ids=[r["id"] for r in workspace.get("research", []) if isinstance(r, dict)])
        base["versions"] = [{"version": version, "readiness": "NONE", "frozen": False,
                             "summary": "registered by game-reverse-engineering", "created_utc": now_utc()}]
        create_new(folder / "BASE.json", json_bytes(base))
        create_new(folder / "GATES.json", template("v4/base/GATES.json").read_bytes())
        create_new(folder / "CAPABILITIES.md", template("v4/base/CAPABILITIES.md").read_bytes())
        create_new(folder / "RIGHTS_LEDGER.md", template("v4/RIGHTS_LEDGER.md").read_bytes())
        workspace.setdefault("bases", []).append({"id": base_id, "records": records})
        workspace["focus"]["base"] = workspace["focus"].get("base") or base_id
        ws_changed = True
        messages.append("Registered Base %s@%s at %s (code: %s)%s" % (base_id, version, records, code_path,
                        "" if code_root.exists() else " — code path does not exist yet"))
        default_core = [code_path] if code_path != "." else []
    else:
        folder = safe_path(root, entry["records"])
        base = load_json(folder / "BASE.json")
        messages.append("Adopting existing Base %s@%s; v4 Base records are not modified." % (base_id, base.get("current_version")))
        default_core = [base.get("code_path")] if base.get("code_path") not in ("", ".") else []
    if ws_changed:
        save_json(ws_path, workspace)

    re_dir = folder / RE_DIRNAME
    state_path = re_dir / "RE_STATE.json"
    if state_path.exists():
        messages.append("Kept existing reverse-engineering records.")
    else:
        cores = list(core_paths or default_core)
        for path in cores:
            safe_path(root, path)
        state = load_json(template("RE_STATE.json"))
        state.update(base_id=base_id, target_level=target, core_paths=cores)
        if agent:
            state["assignment"] = {"agent_label": agent, "scope": "E0-E7", "since_utc": now_utc()}
        for name_, source in (("PARITY.json", "PARITY.json"), ("REUSE.json", "REUSE.json"), ("PROBES.json", "PROBES.json"),
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
            messages.append("NOTE: set core_paths (engine core only, not sample content) before Creator verification.")
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
    messages.append("Next: E0 technical survey (re/TECH_SURVEY.md) and E1 reuse assessment (re/REUSE.json). No quality or legal pass granted.")
    return messages


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
            for path in research_paths:
                pure = PurePosixPath(path)
                for core_path in core_pure:
                    if inside(pure, core_path) or inside(core_path, pure):
                        errors.append(label + ": quarantined material %s overlaps Base core path %s" % (path, core_path))
    return errors


def reuse_index(reuse: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {m["id"]: m for m in reuse.get("modules", []) if isinstance(m, dict) and isinstance(m.get("id"), str)}


# ---------------------------------------------------------------- parity matrix

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
    if level == "UNKNOWN" and status in ("IMPLEMENTED", "VERIFIED"):
        if approach != "IMPROVE" or not text(original.get("dynamic_gap")):
            errors.append(label + ": original behavior is UNKNOWN; research it, or mark approach IMPROVE with a dynamic_gap design note")
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
    if not isinstance(item.get("history"), list):
        errors.append(label + ": history must be a list")
    return errors, warnings


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
    return errors, warnings


def item_counts(item: Dict[str, Any], current: str) -> Optional[str]:
    status = item.get("status")
    if status == "NOT_APPLICABLE":
        return None if text(item.get("na_basis")) else "NOT_APPLICABLE without na_basis"
    if status in NON_COUNTING:
        return "is %s (an interface or document is not a finished capability)" % status
    if status != "VERIFIED":
        return "is " + str(status)
    if text(item.get("base_version")) != current:
        return "verified against base %s, not current %s" % (item.get("base_version") or "(none)", current)
    return None


# ---------------------------------------------------------------- creator probes

def probe_errors(ctx: Context, probes: Dict[str, Any], current: str, fingerprint: str, core: List[str]) -> Tuple[List[str], List[str]]:
    errors = []
    if probes.get("schema_version") != GRE_SCHEMA:
        errors.append("PROBES: unsupported schema_version")
    valid = []
    core_pure = [PurePosixPath(p) for p in core]
    entries = probes.get("probes") if isinstance(probes.get("probes"), list) else []
    seen = set()
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
        if text(probe.get("base_version")) != current:
            own.append(label + ": recorded for base %s, current is %s; re-run" % (probe.get("base_version"), current))
        if not text(probe.get("license")):
            own.append(label + ": license required (original test content)")
        for field in ("config_files", "asset_files"):
            files = probe.get(field)
            if not isinstance(files, list) or not files:
                own.append(label + ": %s must list files with SHA-256" % field)
                continue
            for entry in files:
                try:
                    path = safe_path(ctx.root, entry.get("path", ""))
                    pure = PurePosixPath(rel(ctx.root, path))
                    if any(inside(pure, c) for c in core_pure):
                        own.append(label + ": %s %s is inside the engine core; probe content must live outside core_paths" % (field, entry.get("path")))
                    if not path.is_file() or digest(path) != str(entry.get("sha256", "")).lower():
                        own.append(label + ": %s missing or changed: %s" % (field, entry.get("path")))
                except (ValueError, AttributeError) as exc:
                    own.append(label + ": " + str(exc))
        replaces = probe.get("replaces") if isinstance(probe.get("replaces"), dict) else {}
        for category in PROBE_CATEGORIES:
            evidence = (replaces.get(category) or {}).get("evidence") if isinstance(replaces.get(category), dict) else None
            if not isinstance(evidence, list) or not evidence:
                own.append(label + ": no runtime evidence that %s was replaced" % category)
                continue
            own += check_evidence(evidence, ctx.root, label + " " + category)[0]
            if not any(isinstance(e, dict) and e.get("kind") in VISUAL_KINDS | {"test"} for e in evidence):
                own.append(label + ": %s evidence needs a runtime capture, measurement or test" % category)
        if probe.get("core_changes_needed"):
            own.append(label + ": needed engine-core changes; move them into the Base, bump the version and re-run both probes")
        if not fingerprint:
            own.append(label + ": core_paths are empty or missing; cannot prove the core stayed unchanged")
        elif probe.get("core_fingerprint") != fingerprint:
            own.append(label + ": core fingerprint differs from the current core (the core changed or the probe used another core); re-run")
        errors += own
        if not own:
            valid.append(probe)
    for index, first in enumerate(valid):
        for second in valid[index + 1:]:
            pair = "PROBES %s/%s" % (first["id"], second["id"])
            for field in ("config_files", "asset_files"):
                shared = {f["sha256"] for f in first[field]} & {f["sha256"] for f in second[field]}
                if shared:
                    errors.append(pair + ": share %d identical %s; the two configurations must be clearly different" % (len(shared), field))
            for category in PROBE_CATEGORIES:
                a = {e["sha256"] for e in first["replaces"][category]["evidence"]}
                b = {e["sha256"] for e in second["replaces"][category]["evidence"]}
                if a & b:
                    errors.append(pair + ": identical %s evidence; each probe needs its own runtime proof" % category)
    return errors, [p["id"] for p in valid]


# ---------------------------------------------------------------- levels

def snapshot(ctx: Context) -> Dict[str, Any]:
    state = ctx.load("RE_STATE.json")
    data = {"state": state, "parity": ctx.load("PARITY.json"), "reuse": ctx.load("REUSE.json"),
            "probes": ctx.load("PROBES.json"), "gates": ctx.load("GATES.json"), "current": ctx.current_version()}
    data["core"] = ctx.core_paths(state)
    data["fingerprint"] = core_fingerprint(ctx.root, data["core"])
    data["modules"] = reuse_index(data["reuse"])
    return data


def level_problems(ctx: Context, level: str, data: Dict[str, Any]) -> List[str]:
    target = level_index(level)
    if target == 0:
        return []
    problems = []
    current = data["current"]
    items = [i for i in data["parity"].get("items", []) if isinstance(i, dict)]
    gates = {g.get("id"): g for g in data["gates"].get("gates", []) if isinstance(g, dict)}
    re01 = gates.get("RE01")
    if not re01 or re01.get("status") != "PASS" or check_gate(re01, "RE01", ctx.root, False):
        problems.append("RE01 reuse/rights assessment is not PASS with evidence")
    modules = data["reuse"].get("modules", [])
    if not modules:
        problems.append("REUSE.json lists no modules; assess the reference's code and assets first")
    elif any(isinstance(m, dict) and m.get("decision") == "REVIEW" for m in modules):
        problems.append("REUSE.json still has REVIEW modules")
    problems += reuse_errors(ctx, data["reuse"], data["core"])[:3]
    groups = [g for g, lv in GROUP_LEVEL.items() if level_index(lv) <= target]
    for item in items:
        if DOMAIN_GROUP.get(item.get("domain")) not in groups:
            continue
        structural, _ = item_errors(ctx, item, data["modules"])
        if structural:
            problems.append(structural[0])
            continue
        problem = item_counts(item, current)
        if problem:
            problems.append("%s %s: %s" % (item.get("id"), item.get("name"), problem))
    for domain, group in DOMAIN_GROUP.items():
        if group not in groups:
            continue
        domain_items = [i for i in items if i.get("domain") == domain]
        if not domain_items:
            problems.append("domain %s has no items" % domain)
        elif domain not in OPTIONAL_DOMAINS and not any(i.get("status") == "VERIFIED" for i in domain_items):
            problems.append("domain %s needs at least one VERIFIED capability (it cannot be entirely NOT_APPLICABLE)" % domain)
    if target >= LEVELS.index("CREATOR_READY"):
        probe_problems, valid = probe_errors(ctx, data["probes"], current, data["fingerprint"], data["core"])
        required = data["probes"].get("required_probes", 2)
        if not isinstance(required, int) or required < 2:
            problems.append("required_probes must be at least 2")
            required = 2
        if len(valid) < required or probe_problems:
            problems.append("Creator verification needs %d valid, clearly different probes on an unchanged core (valid: %d)" % (required, len(valid)))
            problems += probe_problems[:4]
        for item in items:
            if item.get("status") == "VERIFIED" and item.get("importance") == "core" and item.get("reusable_for_new_games") is not True:
                problems.append("%s is VERIFIED but not reusable_for_new_games; a core capability must be usable by new games" % item.get("id"))
    return problems


def derive_level(ctx: Context, data: Optional[Dict[str, Any]] = None) -> str:
    data = data or snapshot(ctx)
    result = "NONE"
    for level in LEVELS[1:]:
        if level_problems(ctx, level, data):
            break
        result = level
    return result


def set_level(ctx: Context, level: str, note: str = "") -> List[str]:
    if level not in LEVELS:
        raise ValueError("level must be one of " + ", ".join(LEVELS))
    data = snapshot(ctx)
    state = data["state"]
    current = data["current"]
    claimed = state.get("claimed_level") if state.get("claimed_for_version") == current else "NONE"
    if level_index(level) > level_index(claimed):
        problems = level_problems(ctx, level, data)
        if problems:
            raise ValueError("Cannot claim %s for %s@%s:\n- %s" % (level, ctx.base_id, current, "\n- ".join(problems[:12])))
    entry = {"utc": now_utc(), "level": level, "base_version": current, "core_fingerprint": data["fingerprint"], "note": note}
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


def parity_add(ctx: Context, iid: str, domain: str, name: str, importance: str = "core") -> List[str]:
    if domain not in DOMAIN_GROUP or not ITEM_ID_RE.fullmatch(iid) or not iid.startswith(domain + "-"):
        raise ValueError("Item id must look like %s-NN and match its domain" % domain)
    parity = ctx.load("PARITY.json")
    if any(i.get("id") == iid for i in parity.get("items", [])):
        raise ValueError("Parity item exists: " + iid)
    parity["items"].append({"id": iid, "domain": domain, "name": name, "required_for": GROUP_LEVEL[DOMAIN_GROUP[domain]],
                            "importance": importance, "original": {"evidence_level": "UNKNOWN", "refs": [], "dynamic_gap": ""},
                            "approach": "UNDECIDED", "reuse_modules": [], "research_basis": [], "status": "NOT_STARTED",
                            "base_version": "", "verification": [], "differences": "", "reusable_for_new_games": False,
                            "na_basis": "", "history": []})
    ctx.save("PARITY.json", parity)
    ctx.log("parity_add", item=iid, domain=domain, name=name)
    return ["Added parity item " + iid]


def parity_set(ctx: Context, iid: str, status: Optional[str] = None, approach: Optional[str] = None,
               evidence: Optional[str] = None, kind: str = "", observed: str = "",
               original_level: Optional[str] = None, original_ref: Optional[str] = None, ref_kind: str = "",
               ref_observed: str = "", ref_local: bool = False, gap: Optional[str] = None,
               differences: Optional[str] = None, reusable: Optional[bool] = None, modules: Optional[List[str]] = None,
               research_basis: Optional[List[str]] = None, na_basis: Optional[str] = None, note: str = "") -> List[str]:
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
    if modules is not None:
        item["reuse_modules"] = modules
    if research_basis is not None:
        item["research_basis"] = research_basis
    if differences is not None:
        item["differences"] = differences
    if reusable is not None:
        item["reusable_for_new_games"] = reusable
    if na_basis is not None:
        item["na_basis"] = na_basis
    if evidence:
        entry = evidence_entry(ctx.root, evidence, kind, observed)
        item.setdefault("verification", []).append(entry)
        added.append(entry)
    if status is not None:
        if status not in ITEM_STATUSES:
            raise ValueError("status must be one of " + ", ".join(ITEM_STATUSES))
        item["status"] = status
        if status == "VERIFIED":
            item["base_version"] = ctx.current_version()
    reuse = ctx.load("REUSE.json")
    errors, _ = item_errors(ctx, item, reuse_index(reuse))
    if errors and item.get("status") in ("VERIFIED", "IMPLEMENTED", "NOT_APPLICABLE"):
        raise ValueError("Parity item %s rejected:\n- %s" % (iid, "\n- ".join(errors)))
    record = {"utc": now_utc(), "from": before, "to": item.get("status"), "base_version": item.get("base_version", ""),
              "evidence": [{"path": e["path"], "sha256": e["sha256"]} for e in added], "note": note}
    item.setdefault("history", []).append(record)
    ctx.save("PARITY.json", parity)
    ctx.log("parity", item=iid, **{k: v for k, v in record.items() if k != "utc"},
            locations=[e.get("location", "") for e in added])
    return ["%s: %s -> %s%s" % (iid, before, item.get("status"), (" (+%d evidence)" % len(added)) if added else "")]


def reuse_set(ctx: Context, mid: str, name: str = "", origin: str = "", source_kind: Optional[str] = None,
              license_: Optional[str] = None, decision: Optional[str] = None, base_paths: Optional[List[str]] = None,
              research_paths: Optional[List[str]] = None, evidence: Optional[str] = None, observed: str = "",
              rights_basis: Optional[str] = None, notes: str = "") -> List[str]:
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
                       ("base_paths", base_paths), ("research_paths", research_paths), ("rights_basis", rights_basis)):
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
             subject: str = "", evidence: Optional[str] = None, observed: str = "") -> List[str]:
    gates = ctx.load("GATES.json")
    gate = next((g for g in gates.get("gates", []) if g.get("id") == gid), None)
    if gate is None:
        raise ValueError("Unknown gate " + gid)
    if status not in GATE_STATUSES:
        raise ValueError("status must be one of " + ", ".join(GATE_STATUSES))
    if evidence:
        gate.setdefault("evidence", []).append(evidence_entry(ctx.root, evidence, "review-record", observed or "review record"))
    gate.update(status=status)
    if criteria:
        gate["criteria"] = criteria
    if subject:
        gate["subject_revision"] = subject
    if reviewer:
        gate["reviewer"] = {"identity": reviewer, "independence": independence}
    errors = check_gate(gate, gid, ctx.root, gid == "RE02")
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
    if not files:
        raise ValueError("No files found in " + ", ".join(paths))
    return files


def probe_record(ctx: Context, pid: str, title: str, configs: List[str], assets: List[str],
                 evidence: Dict[str, List[Tuple[str, str]]], license_: str = "original_test_content",
                 core_changes: Optional[List[str]] = None) -> List[str]:
    check_slug(pid, "Probe")
    probes = ctx.load("PROBES.json")
    replaces = {}
    for category in PROBE_CATEGORIES:
        entries = []
        for path, kind in evidence.get(category, []):
            entries.append(evidence_entry(ctx.root, path, kind or "runtime-capture", "%s replaced in probe %s" % (category, pid)))
        replaces[category] = {"evidence": entries}
    record = {"id": pid, "title": title or pid, "base_version": ctx.current_version(), "license": license_,
              "config_files": collect_files(ctx, configs), "asset_files": collect_files(ctx, assets),
              "replaces": replaces, "core_fingerprint": core_fingerprint(ctx.root, ctx.core_paths()),
              "core_changes_needed": list(core_changes or []), "recorded_utc": now_utc()}
    old = [p for p in probes.get("probes", []) if p.get("id") == pid]
    if old:
        probes.setdefault("probes_history", []).extend(old)
    probes["probes"] = [p for p in probes.get("probes", []) if p.get("id") != pid] + [record]
    ctx.save("PROBES.json", probes)
    ctx.log("probe", probe=pid, base_version=record["base_version"], core_fingerprint=record["core_fingerprint"],
            evidence=[{"path": e["path"], "sha256": e["sha256"]} for c in replaces.values() for e in c["evidence"]])
    data = snapshot(ctx)
    problems, valid = probe_errors(ctx, data["probes"], data["current"], data["fingerprint"], data["core"])
    mine = [p for p in problems if ("PROBE %s" % pid) in p or ("%s/" % pid) in p or ("/%s" % pid) in p]
    return ["Recorded probe %s (%d config, %d asset files)" % (pid, len(record["config_files"]), len(record["asset_files"]))] + \
           ["PROBLEM: " + p for p in mine]


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


# ---------------------------------------------------------------- tasks, guards, checkpoints

def task_start(ctx: Context, tid: str, kind: str, desc: str, timeout_min: int = 30, item: str = "") -> List[str]:
    if kind not in TASK_KINDS:
        raise ValueError("kind must be one of " + ", ".join(TASK_KINDS))
    if kind == "research" and not item:
        raise ValueError("Research must serve a capability gap: pass --item <parity id>")
    if item:
        find_item(ctx.load("PARITY.json"), item)
    if timeout_min <= 0:
        raise ValueError("timeout must be positive minutes")
    state = ctx.load("RE_STATE.json")
    task = next((t for t in state.get("tasks", []) if t.get("id") == tid), None)
    if task and task.get("status") == "ACTIVE":
        raise ValueError("Task %s is already ACTIVE; finish it or record it as blocked/failed first" % tid)
    if task is None:
        task = {"id": tid, "failures": 0, "attempts": 0}
        state.setdefault("tasks", []).append(task)
    task.update(kind=kind, desc=desc, item=item, status="ACTIVE", started_utc=now_utc(), timeout_min=timeout_min,
                attempts=int(task.get("attempts", 0)) + 1)
    ctx.save("RE_STATE.json", state)
    ctx.log("task_start", task=tid, kind=kind, item=item, timeout_min=timeout_min)
    return ["Task %s started (%s, timeout %d min)" % (tid, kind, timeout_min)]


def task_done(ctx: Context, tid: str, result: str, summary: str) -> List[str]:
    if result not in TASK_RESULTS:
        raise ValueError("result must be one of " + ", ".join(TASK_RESULTS))
    if not text(summary):
        raise ValueError("--summary is required (what happened, with evidence paths)")
    state = ctx.load("RE_STATE.json")
    task = next((t for t in state.get("tasks", []) if t.get("id") == tid), None)
    if task is None:
        raise ValueError("Unknown task " + tid)
    task.update(status={"ok": "DONE", "failed": "FAILED", "blocked": "BLOCKED"}[result], closed_utc=now_utc(), last_result=summary)
    if result == "failed":
        task["failures"] = int(task.get("failures", 0)) + 1
    state.setdefault("task_log", []).append({"id": tid, "kind": task.get("kind"), "result": result,
                                             "started_utc": task.get("started_utc"), "closed_utc": task["closed_utc"]})
    ctx.save("RE_STATE.json", state)
    ctx.log("task_done", task=tid, result=result, summary=summary)
    messages = ["Task %s %s" % (tid, task["status"])]
    limit = state.get("guards", {}).get("same_failure_limit", 3)
    if task.get("failures", 0) >= limit:
        messages.append("REPEATED_FAILURE: %s failed %d times; re-investigate the root cause instead of retrying the same approach" % (tid, task["failures"]))
    return messages


def guard_warnings(ctx: Context, data: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> List[str]:
    data = data or snapshot(ctx)
    state = data["state"]
    now = now or datetime.now(timezone.utc)
    guards = state.get("guards", {})
    warnings = []
    for task in state.get("tasks", []):
        if task.get("status") == "ACTIVE":
            started = parse_utc(task.get("started_utc", ""))
            if started and now - started > timedelta(minutes=int(task.get("timeout_min", 30))):
                warnings.append("STALLED: task %s has run past its %s-minute timeout; check whether the tool hung, stop only processes this task started, and restart with a smaller step" % (task["id"], task.get("timeout_min")))
        if task.get("status") == "FAILED" and task.get("failures", 0) >= guards.get("same_failure_limit", 3):
            warnings.append("REPEATED_FAILURE: %s failed %d times; change the hypothesis or approach" % (task["id"], task["failures"]))
    log = state.get("task_log", [])
    limit = guards.get("research_streak_limit", 6)
    recent = log[-limit:]
    if len(recent) >= limit and all(t.get("kind") == "research" for t in recent):
        since = parse_utc(recent[0].get("started_utc", "")) or now
        progressed = any(e.get("event") == "parity" and e.get("to") in ("IMPLEMENTED", "VERIFIED")
                         and (parse_utc(e.get("utc", "")) or since) >= since for e in ctx.history())
        if not progressed:
            warnings.append("RESEARCH_SPIN: the last %d tasks were research with no capability implemented or verified; build the Base for the largest gap now" % limit)
    limit = guards.get("polish_streak_limit", 5)
    recent = log[-limit:]
    target = state.get("target_level", "CREATOR_READY")
    derived = derive_level(ctx, data)
    if len(recent) >= limit and all(t.get("kind") in ("polish", "docs") for t in recent) and level_index(derived) < level_index(target):
        blockers = level_problems(ctx, LEVELS[level_index(derived) + 1], data)
        warnings.append("POLISH_SPIN: the last %d tasks were polish/docs while %s is unmet; return to: %s" % (limit, target, blockers[0] if blockers else "the largest gap"))
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
    e, w = parity_errors(ctx, data["parity"], data["modules"])
    errors += e
    warnings += w
    probe_problems, _ = probe_errors(ctx, data["probes"], data["current"], data["fingerprint"], data["core"])
    warnings += probe_problems
    for gate in data["gates"].get("gates", []):
        if isinstance(gate, dict):
            errors += check_gate(gate, str(gate.get("id")), ctx.root, gate.get("id") == "RE02")
    if {g.get("id") for g in data["gates"].get("gates", []) if isinstance(g, dict)} != {"RE01", "RE02"}:
        errors.append("GATES must contain exactly RE01 and RE02")
    e, w = history_errors(ctx, data["parity"])
    errors += e
    warnings += w
    derived = derive_level(ctx, data) if not errors else "NONE"
    claimed = state.get("claimed_level", "NONE")
    if claimed not in LEVELS:
        errors.append("RE_STATE.claimed_level is invalid")
    elif state.get("claimed_for_version") and state.get("claimed_for_version") != data["current"] and claimed != "NONE":
        warnings.append("Level %s was claimed for base %s; current version %s needs re-verification" % (claimed, state.get("claimed_for_version"), data["current"]))
    elif level_index(claimed) > level_index(derived):
        problems = level_problems(ctx, claimed, data)
        errors.append("Claimed %s but evidence supports %s: %s" % (claimed, derived, problems[0] if problems else ""))
    if strict and level_index(derived) < level_index(state.get("target_level")):
        problems = level_problems(ctx, state.get("target_level"), data)
        errors.append("Strict target: %s not reached (%s): %s" % (state.get("target_level"), derived, "; ".join(problems[:3])))
    warnings += guard_warnings(ctx, data)
    warnings.append("Rights are separate: source review = v4 Base gate B02, commercial permission = RE02 (external approval only).")
    warnings.append("This tool checks records, bytes and claims; it cannot judge gameplay, art quality or legal clearance.")
    return errors, warnings


def rights_summary(ctx: Context, data: Dict[str, Any]) -> str:
    try:
        b02 = next((g.get("status") for g in load_json(ctx.base_dir / "GATES.json").get("gates", []) if g.get("id") == "B02"), "missing")
    except ValueError:
        b02 = "unreadable"
    re02 = next((g.get("status") for g in data["gates"].get("gates", []) if g.get("id") == "RE02"), "missing")
    return "source review (v4 B02)=%s, commercial permission (RE02)=%s" % (b02, re02)


def status_report(ctx: Context) -> str:
    data = snapshot(ctx)
    state = data["state"]
    derived = derive_level(ctx, data)
    items = [i for i in data["parity"].get("items", []) if isinstance(i, dict)]
    counts: Dict[str, int] = {}
    for item in items:
        counts[str(item.get("status"))] = counts.get(str(item.get("status")), 0) + 1
    static = [i["id"] for i in items if i.get("original", {}).get("evidence_level") in ("STATIC_ONLY", "INFERRED", "PROXY")]
    lines = ["# Base %s@%s — reverse engineering (skill %s)" % (ctx.base_id, data["current"], SKILL_VERSION),
             "Target: %s | evidence supports: %s | claimed: %s (for %s)" % (state.get("target_level"), derived,
                                                                         state.get("claimed_level"), state.get("claimed_for_version") or "-"),
             "Rights (separate from levels): " + rights_summary(ctx, data),
             "Parity items: " + ", ".join("%s=%d" % (k, v) for k, v in sorted(counts.items())),
             "Static-only/inferred/proxy originals: %d %s" % (len(static), ", ".join(static[:8])),
             "Core paths: %s (fingerprint %s)" % (", ".join(data["core"]) or "-", data["fingerprint"][:12] or "-"),
             "Assignment: %s" % (state.get("assignment", {}).get("agent_label") or "-"),
             "Checkpoint: %s — next: %s" % (state.get("checkpoint", {}).get("utc") or "-", state.get("checkpoint", {}).get("next_action"))]
    for task in state.get("tasks", []):
        if task.get("status") in ("ACTIVE", "BLOCKED", "FAILED"):
            lines.append("Task %s %s (%s): %s" % (task["id"], task["status"], task.get("kind"), task.get("desc")))
    if derived != LEVELS[-1]:
        nxt = LEVELS[level_index(derived) + 1]
        lines.append("To reach %s:" % nxt)
        lines += ["  - " + p for p in level_problems(ctx, nxt, data)[:8]]
    lines += ["WARNING: " + w for w in guard_warnings(ctx, data)]
    return "\n".join(lines)


def resume_report(ctx: Context) -> str:
    return "\n".join(["# Resume — read files, not old chats", status_report(ctx),
                      "Git HEAD: " + git_text(ctx.root, ["rev-parse", "--short", "HEAD"]),
                      "Working tree:\n" + (git_text(ctx.root, ["status", "--short"]) or "clean"),
                      "Steps: 1) close or re-run STALLED/ACTIVE tasks after checking processes; 2) `gre.py env` on a new device;",
                      "3) run the Base build/tests (BASE.json known_commands); 4) continue with the checkpoint's next action or the first blocker above."])


def handoff_check(ctx: Context) -> List[str]:
    problems = []
    handoff = ctx.path("BASE_HANDOFF.md")
    if not handoff.is_file() or UNFILLED_MARKER in handoff.read_text(encoding="utf-8", errors="replace"):
        problems.append("BASE_HANDOFF.md is missing or still the blank template")
    state = ctx.load("RE_STATE.json")
    if not text(state.get("checkpoint", {}).get("next_action")) or not text(state.get("checkpoint", {}).get("utc")):
        problems.append("no checkpoint with a next action (`gre.py checkpoint --next ...`)")
    for task in state.get("tasks", []):
        if task.get("status") == "ACTIVE":
            problems.append("task %s is still ACTIVE; finish it or record it blocked/failed with a summary" % task["id"])
    errors, _ = validate(ctx.root, ctx.base_id)
    problems += errors
    return problems


def write_report(ctx: Context) -> List[str]:
    data = snapshot(ctx)
    derived = derive_level(ctx, data)
    names = {d["id"]: d["name"] for d in data["parity"].get("domains", []) if isinstance(d, dict)}
    lines = ["# 能力等价矩阵报告 — %s@%s" % (ctx.base_id, data["current"]), "",
             "- 生成时间：%s；生成工具：gre.py %s" % (now_utc(), SKILL_VERSION),
             "- 证据支持的等级：**%s**（目标 %s）" % (derived, data["state"].get("target_level")),
             "- 权利（与技术等级分开）：" + rights_summary(ctx, data),
             "- 核心指纹：%s" % (data["fingerprint"] or "（未设置核心路径）"), ""]
    for group, title in (("logic", "Logic"), ("presentation", "Presentation"), ("creator", "Creator")):
        lines += ["## %s" % title, "", "| 条目 | 能力 | 原版证据 | 方式 | 状态 | 验证证据 | 重要差异 | 可供新游戏 |", "|---|---|---|---|---|---|---|---|"]
        for item in data["parity"].get("items", []):
            if DOMAIN_GROUP.get(item.get("domain")) != group:
                continue
            kinds = sorted({v.get("kind") for v in item.get("verification", []) if isinstance(v, dict)})
            lines.append("| %s | %s / %s | %s | %s | %s | %s | %s | %s |" % (
                item["id"], names.get(item["domain"], item["domain"]), item.get("name"),
                item.get("original", {}).get("evidence_level"), item.get("approach"), item.get("status"),
                ", ".join(kinds) or "—", (item.get("differences") or "—").replace("|", "/"),
                "是" if item.get("reusable_for_new_games") else "否"))
        lines.append("")
    lines += ["## Creator 验证", ""]
    _, valid = probe_errors(ctx, data["probes"], data["current"], data["fingerprint"], data["core"])
    for probe in data["probes"].get("probes", []):
        lines.append("- %s「%s」：配置 %d 个文件、资产 %d 个文件，%s" % (probe.get("id"), probe.get("title"), len(probe.get("config_files", [])),
                     len(probe.get("asset_files", [])), "有效" if probe.get("id") in valid else "无效"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destination = ctx.path("reports") / ("%s-capability-parity.md" % stamp)
    counter = 1
    while not create_new(destination, ("\n".join(lines) + "\n").encode("utf-8")):
        counter += 1
        destination = ctx.path("reports") / ("%s-%d-capability-parity.md" % (stamp, counter))
    relative = rel(ctx.root, destination)
    ctx.log("report", evidence=[{"path": relative, "sha256": digest(destination)}], level=derived)
    return ["Report written: " + relative,
            "v4 mapping: LOGIC_READY items -> B03; P6 + asset items -> B05; C1 + probes -> B04/B07; build/test evidence -> B06;",
            "dependent-game regression -> B08; research matrix -> B01. Rights stay with B02/RE02. Update v4 gates with project.py if you claim BASE_READY."]


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

    p = add("init", "Start or adopt reverse engineering for a Base (empty folder, existing project or v4 workspace)")
    p.add_argument("--base-version", default="0.1.0")
    p.add_argument("--code-path", default="")
    p.add_argument("--core-path", action="append", default=None)
    p.add_argument("--reference", action="append", default=[])
    p.add_argument("--name", default="")
    p.add_argument("--target", choices=LEVELS[1:], default="CREATOR_READY")
    p.add_argument("--basis", default="")
    p.add_argument("--agent", default="")
    p = add("parity", "Add or update a capability parity item (history is appended)")
    p.add_argument("action", choices=("add", "set"))
    p.add_argument("--item", required=True)
    p.add_argument("--domain")
    p.add_argument("--name", default="")
    p.add_argument("--importance", default="core", choices=("core", "important", "minor"))
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
    p.add_argument("--notes", default="")
    p = add("gate", "Set RE01 (reuse assessment) or RE02 (commercial permission, external approval only)")
    p.add_argument("--id", required=True, choices=("RE01", "RE02"))
    p.add_argument("--status", required=True, choices=GATE_STATUSES)
    p.add_argument("--criteria", default="")
    p.add_argument("--reviewer", default="")
    p.add_argument("--independence", default="self_review", choices=REVIEW_MODES)
    p.add_argument("--subject", default="")
    p.add_argument("--evidence")
    p.add_argument("--observed", default="")
    p = add("probe", "Record a Creator verification probe (hashes files, fingerprints the core)")
    p.add_argument("--id", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--config", action="append", required=True)
    p.add_argument("--assets", action="append", required=True)
    p.add_argument("--evidence", action="append", default=[], help="category=path[:kind], categories: " + ",".join(PROBE_CATEGORIES))
    p.add_argument("--license", default="original_test_content")
    p.add_argument("--core-change", action="append", default=[])
    p = add("level", "Claim a delivery level; refused unless the evidence supports it")
    p.add_argument("--set", required=True, choices=LEVELS)
    p.add_argument("--note", default="")
    p = add("evidence", "Store a result file as new, never-overwritten evidence")
    p.add_argument("--file", required=True)
    p.add_argument("--name", default="")
    p.add_argument("--kind", default="")
    p.add_argument("--observed", default="")
    p = add("task", "Start or finish a task (timeouts and loop guards)")
    p.add_argument("action", choices=("start", "done"))
    p.add_argument("--id", required=True)
    p.add_argument("--kind", choices=TASK_KINDS)
    p.add_argument("--desc", default="")
    p.add_argument("--timeout-min", type=int, default=30)
    p.add_argument("--item", default="")
    p.add_argument("--result", choices=TASK_RESULTS)
    p.add_argument("--summary", default="")
    p = add("checkpoint", "Save the exact resume point")
    p.add_argument("--next", required=True)
    p.add_argument("--resume-command", default="")
    p.add_argument("--note", default="")
    p = add("assign", "Record which Agent works on this Base")
    p.add_argument("--agent", required=True)
    p.add_argument("--scope", default="")
    for name, help_text in (("status", "Read-only status"), ("resume", "Read-only resume briefing"),
                            ("report", "Write a timestamped capability parity report"),
                            ("handoff", "Check handoff completeness"), ("env", "Re-probe this device (local file only)")):
        add(name, help_text)
    p = add("validate", "Validate records, evidence, history and level claims")
    p.add_argument("--strict-target", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            output = init(args.project, args.base_id or "core", args.base_version, args.code_path, args.core_path,
                          args.reference, args.name, args.target, args.basis, args.agent)
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
                if args.action == "add":
                    if not args.domain or not args.name:
                        raise ValueError("parity add needs --domain and --name")
                    output = parity_add(ctx, args.item, args.domain, args.name, args.importance)
                else:
                    output = parity_set(ctx, args.item, args.status, args.approach, args.evidence, args.kind, args.observed,
                                        args.original_level, args.original_ref, args.ref_kind, args.ref_observed, args.ref_local,
                                        args.gap, args.differences, bool_arg(args.reusable), split(args.modules),
                                        split(args.research_basis), args.na_basis, args.note)
            elif args.command == "reuse":
                output = reuse_set(ctx, args.module, args.name, args.origin, args.source_kind, args.license, args.decision,
                                   split(args.base_paths), split(args.research_paths), args.evidence, args.observed,
                                   args.rights_basis, args.notes)
            elif args.command == "gate":
                output = gate_set(ctx, args.id, args.status, args.criteria, args.reviewer, args.independence, args.subject,
                                  args.evidence, args.observed)
            elif args.command == "probe":
                evidence: Dict[str, List[Tuple[str, str]]] = {}
                for spec in args.evidence:
                    category, _, rest = spec.partition("=")
                    path, _, kind = rest.partition(":") if not re.match(r"^[A-Za-z]:[\\/]", rest) else (rest, "", "")
                    if category not in PROBE_CATEGORIES or not path:
                        raise ValueError("--evidence must be category=path[:kind] with category in " + ",".join(PROBE_CATEGORIES))
                    evidence.setdefault(category, []).append((path, kind))
                output = probe_record(ctx, args.id, args.title, args.config, args.assets, evidence, args.license, args.core_change)
            elif args.command == "level":
                output = set_level(ctx, args.set, args.note)
            elif args.command == "evidence":
                output = evidence_add(ctx, args.file, args.name, args.kind, args.observed)
            elif args.command == "task":
                if args.action == "start":
                    if not args.kind:
                        raise ValueError("task start needs --kind")
                    output = task_start(ctx, args.id, args.kind, args.desc, args.timeout_min, args.item)
                else:
                    if not args.result:
                        raise ValueError("task done needs --result")
                    output = task_done(ctx, args.id, args.result, args.summary)
            elif args.command == "checkpoint":
                output = checkpoint(ctx, args.next, args.resume_command, args.note)
            elif args.command == "assign":
                output = assign(ctx, args.agent, args.scope)
            elif args.command == "status":
                output = [status_report(ctx)]
            elif args.command == "resume":
                output = [resume_report(ctx)]
            elif args.command == "report":
                output = write_report(ctx)
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
