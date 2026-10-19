#!/usr/bin/env python3
"""Local workflow records for Game Production. Python 3.9+, no dependencies.

Never runs a game/build, installs packages, launches agents, commits, pushes or deploys.
Validation checks records/evidence bytes, not gameplay quality or legal clearance.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, Tuple

KIT_ROOT = Path(__file__).resolve().parent.parent
KIT_VERSION = "3.0.0"
SCHEMA_VERSION = "2.0"
SKILL_PATH = ".agents/skills/game-production"
LEGACY_SKILL_PATH = ".agents/skills/totop-game-production"
LEGACY_AGENTS_MARKERS = ("TOTOP_GAME_PRODUCTION_V2_BEGIN", "TOTOP_GAME_PRODUCTION_V1_BEGIN")
STAGES = {"S" + str(i) for i in range(7)}
TARGETS = {"release_candidate", "mechanics_handoff", "research_handoff", "creator_base"}
RUN_MODES = {"auto", "stage", "review"}
RUN_STATUSES = {"NEW", "RUNNING", "TARGET_REACHED", "HANDOFF_READY", "EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED"}
GATE_STATUSES = {"PASS", "FAIL", "UNVERIFIED", "BLOCKED", "NOT_APPLICABLE"}
PUB_STATUSES = {"NOT_AUTHORIZED", "REVIEW_PENDING", "AUTHORIZED_NOT_PUBLISHED", "PUBLISHED"}
REVIEW_MODES = {"self_review", "separate_context_same_environment", "independent_reviewer"}
IGNORE_BLOCK = "# GAME_PRODUCTION_V3_LOCAL\n.production/local/\n"


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
        raise ValueError("path escapes project (possibly symlink): " + relative) from exc
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


def create_new(path: Path, data: bytes) -> bool:
    """Exclusive create; do not overwrite a pre-existing project file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as out:
            out.write(data)
        return True
    except FileExistsError:
        return False


def install_sources() -> List[Path]:
    return sorted(p for p in KIT_ROOT.rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix != ".pyc"
                  and not p.is_symlink())


def init_project(root: Path, name: Optional[str] = None,
                 target: str = "release_candidate") -> List[str]:
    root = root.resolve()
    if target not in TARGETS:
        raise ValueError("Unknown target: " + target)
    if root == KIT_ROOT or KIT_ROOT in root.parents:
        raise ValueError("Select the game root, not the Skill folder or its child.")
    if root.exists() and not root.is_dir():
        raise ValueError("Project is not a directory: " + str(root))
    # Do not silently run two active generations of the workflow in a project.
    # Migration requires reviewing the existing project's rules and preserving facts.
    legacy = root / LEGACY_SKILL_PATH
    if legacy.exists():
        raise ValueError("Legacy workflow detected at " + str(legacy) + "; use references/MIGRATION_V2.md before installing v3.")
    agents_file = root / "AGENTS.md"
    if agents_file.exists():
        agents_content = agents_file.read_text(encoding="utf-8-sig")
        if any(marker in agents_content for marker in LEGACY_AGENTS_MARKERS):
            raise ValueError("Legacy AGENTS workflow block detected; migrate v2 rules first using references/MIGRATION_V2.md.")
    # Preflight every planned destination before writes. Existing Skill variants
    # require manual merge; never silently upgrade or discard local rules.
    planned: List[Tuple[Path, bytes]] = []
    for source in install_sources():
        relative = source.relative_to(KIT_ROOT).as_posix()
        destination = safe_path(root, SKILL_PATH + "/" + relative)
        data = source.read_bytes()
        if destination.exists():
            if not destination.is_file() or destination.read_bytes() != data:
                raise ValueError("Existing Skill differs; merge via MIGRATION_V1.md before installing: " + str(destination))
        planned.append((destination, data))
    defaults: Dict[str, bytes] = {}
    project = load_json(KIT_ROOT / "templates/PROJECT.json")
    project["project_id"] = "game-" + uuid.uuid4().hex[:12]
    project["name"] = name or root.name
    project["delivery_target"] = target
    gates = load_json(KIT_ROOT / "templates/GATES.json")
    needed = {
        "release_candidate": {"G%02d" % i for i in range(1, 10)},
        "creator_base": {"G%02d" % i for i in range(1, 10)},
        "mechanics_handoff": {"G01", "G02", "G03", "G04", "G06", "G07", "G08", "G09"},
        "research_handoff": {"G01", "G02", "G04"},
    }[target]
    for gate in gates["gates"]:
        gate["required_for_target"] = gate["id"] in needed
        # Unrequired is not an automatic PASS or N/A. It still remains unverified.
    defaults[".production/PROJECT.json"] = json_bytes(project)
    defaults[".production/GATES.json"] = json_bytes(gates)
    for filename in ("STATE.json", "BACKLOG.md", "HANDOFF.md", "RIGHTS_LEDGER.md"):
        defaults[".production/" + filename] = (KIT_ROOT / "templates" / filename).read_bytes()
    env = load_json(KIT_ROOT / "templates/ENVIRONMENT.local.json")
    env["project_root"] = str(root)
    defaults[".production/local/ENVIRONMENT.json"] = json_bytes(env)
    for path in defaults:
        destination = safe_path(root, path)
        if destination.exists() and not destination.is_file():
            raise ValueError("Record path is not a file: " + str(destination))
    for path in ("AGENTS.md", ".gitignore"):
        destination = safe_path(root, path)
        if destination.exists() and not destination.is_file():
            raise ValueError("Expected text file: " + str(destination))
        if destination.exists():
            destination.read_text(encoding="utf-8-sig")
    root.mkdir(parents=True, exist_ok=True)
    messages: List[str] = []
    added = 0
    for path, data in planned:
        if create_new(path, data):
            added += 1
    messages.append("Skill files added: %d (existing identical files retained)" % added)
    for relative, data in defaults.items():
        created = create_new(safe_path(root, relative), data)
        messages.append(("Created " if created else "Kept existing ") + relative)
    agents = safe_path(root, "AGENTS.md")
    existing = agents.read_text(encoding="utf-8-sig") if agents.exists() else ""
    if "GAME_PRODUCTION_V3_BEGIN" not in existing:
        block = (KIT_ROOT / "templates/AGENTS.block.md").read_text(encoding="utf-8")
        with agents.open("a", encoding="utf-8") as out:
            out.write(("\n\n" if existing else "") + block)
        messages.append("Appended AGENTS guide; existing instructions retained. Review any conflicts.")
    else:
        messages.append("Kept existing AGENTS guide; not overwritten.")
    ignores = safe_path(root, ".gitignore")
    existing = ignores.read_text(encoding="utf-8-sig") if ignores.exists() else ""
    if "# GAME_PRODUCTION_V3_LOCAL" not in existing:
        with ignores.open("a", encoding="utf-8") as out:
            out.write(("\n" if existing else "") + IGNORE_BLOCK)
    messages.append("Records initialized only. Inspect existing game and define acceptance contract; no test or quality pass granted.")
    messages.append("Ignored local settings are not an access-control system. Already tracked files stay tracked.")
    return messages


def validate_project(root: Path, strict: bool = False) -> Tuple[List[str], List[str]]:
    root = root.resolve()
    errors: List[str] = []
    warnings: List[str] = []
    objects: Dict[str, Dict[str, Any]] = {}
    for name in ("PROJECT", "STATE", "GATES"):
        try:
            obj = load_json(safe_path(root, ".production/" + name + ".json"))
            objects[name] = obj
            if obj.get("schema_version") != SCHEMA_VERSION:
                errors.append(name + ": unsupported schema_version")
        except ValueError as exc:
            errors.append(str(exc))
    if len(objects) != 3:
        return errors, warnings
    project, state, gates_obj = objects["PROJECT"], objects["STATE"], objects["GATES"]
    if not isinstance(project.get("delivery_target"), str) or project.get("delivery_target") not in TARGETS:
        errors.append("PROJECT.delivery_target is invalid")
    if project.get("kit_version") != KIT_VERSION or state.get("kit_version") != KIT_VERSION:
        warnings.append("Kit version mismatch; review migration before changing records.")
    contract = project.get("acceptance_contract")
    if not isinstance(contract, dict):
        errors.append("PROJECT.acceptance_contract must be an object")
    elif strict and contract.get("defined") is not True:
        errors.append("Acceptance contract is not yet defined from the actual project.")
    run = state.get("run")
    if not isinstance(run, dict):
        errors.append("STATE.run must be an object")
    else:
        if not isinstance(run.get("mode"), str) or run.get("mode") not in RUN_MODES:
            errors.append("STATE.run.mode is invalid")
        if not isinstance(run.get("status"), str) or run.get("status") not in RUN_STATUSES:
            errors.append("STATE.run.status is invalid")
        if not isinstance(run.get("current_stage"), str) or run.get("current_stage") not in STAGES:
            errors.append("STATE.run.current_stage is invalid")
        allowed = run.get("allowed_stages")
        if (not isinstance(allowed, list) or not allowed or
                any(not isinstance(s, str) or s not in STAGES for s in allowed)):
            errors.append("STATE.run.allowed_stages must be a nonempty list of stages S0..S6")
        elif len(allowed) != len(set(allowed)):
            errors.append("STATE.run.allowed_stages has duplicates")
        if isinstance(run.get("status"), str) and run.get("status") in {"EXTERNAL_BLOCKED", "RUNTIME_LIMIT", "USER_PAUSED"} and not str(run.get("stop_reason", "")).strip():
            errors.append("Stopping state requires a truthful stop_reason")
    if not isinstance(state.get("publication_status"), str) or state.get("publication_status") not in PUB_STATUSES:
        errors.append("STATE.publication_status is invalid")
    gates = gates_obj.get("gates")
    if not isinstance(gates, list):
        errors.append("GATES.gates must be a list")
        return errors, warnings
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
        status = gate.get("status")
        if not isinstance(status, str) or status not in GATE_STATUSES:
            errors.append(gid + ": invalid status")
        required = gate.get("required_for_target")
        if type(required) is not bool:
            errors.append(gid + ": required_for_target must be boolean")
        if required is True:
            required_count += 1
        if status == "NOT_APPLICABLE" and not str(gate.get("scope_basis", "")).strip():
            errors.append(gid + ": NOT_APPLICABLE requires a scope basis, not missing tools")
        if status == "PASS":
            if not str(gate.get("criteria", "")).strip():
                errors.append(gid + ": PASS requires concrete criteria")
            if not str(gate.get("subject_revision", "")).strip():
                errors.append(gid + ": PASS requires tested code/assets/build identity")
            reviewer = gate.get("reviewer")
            if (not isinstance(reviewer, dict) or not reviewer.get("identity") or
                    not isinstance(reviewer.get("independence"), str) or
                    reviewer.get("independence") not in REVIEW_MODES):
                errors.append(gid + ": PASS requires reviewer identity and actual independence")
            evidence = gate.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(gid + ": PASS requires evidence files, not only a claim")
            else:
                for index, item in enumerate(evidence):
                    label = gid + ": evidence[%d] " % index
                    if not isinstance(item, dict):
                        errors.append(label + "must be an object")
                        continue
                    if not item.get("kind") or not item.get("observed"):
                        errors.append(label + "requires kind and observed result")
                    sha = item.get("sha256", "")
                    if not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
                        errors.append(label + "requires SHA-256")
                        continue
                    try:
                        path = safe_path(root, item.get("path", ""))
                        if not path.is_file():
                            errors.append(label + "file missing: " + str(path))
                        elif digest(path) != sha.lower():
                            errors.append(label + "SHA-256 mismatch: " + str(path))
                    except (ValueError, OSError) as exc:
                        errors.append(label + str(exc))
        if strict and required is True and status not in ("PASS", "NOT_APPLICABLE"):
            errors.append(gid + ": required target gate is " + str(status))
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
        try:
            if not safe_path(root, ".production/" + name).is_file():
                errors.append("Missing project record: " + name)
        except ValueError as exc:
            errors.append(str(exc))
    if state.get("publication_status") != "PUBLISHED":
        warnings.append("No publication claim verified here; target validation is not release authorization.")
    if not strict:
        warnings.append("Structure check permits UNVERIFIED/FAIL/BLOCKED states; it is not target acceptance.")
    warnings.append("This tool verifies records and bytes only; it cannot judge gameplay, subjective quality or legal clearance.")
    return errors, warnings


def git_text(root: Path, args: List[str]) -> str:
    try:
        result = subprocess.run(["git", "-C", str(root)] + args,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8)
        return result.stdout.strip() if result.returncode == 0 else "not available (not a repository or command failed)"
    except (OSError, subprocess.SubprocessError):
        return "not available (Git missing or timed out)"


def handoff_summary(root: Path) -> str:
    project = load_json(safe_path(root, ".production/PROJECT.json"))
    state = load_json(safe_path(root, ".production/STATE.json"))
    gates = load_json(safe_path(root, ".production/GATES.json"))
    run = state.get("run", {})
    lines = ["# Generated record summary — verify before handoff",
             "Project: " + str(project.get("name")),
             "Target: " + str(project.get("delivery_target")),
             "Mode / stage / status: %s / %s / %s" % (run.get("mode"), run.get("current_stage"), run.get("status")),
             "Actual HEAD: " + git_text(root, ["rev-parse", "HEAD"]),
             "Actual working tree:\n" + (git_text(root, ["status", "--short"]) or "clean"),
             "Next recorded action: " + str(state.get("next_action", "")),
             "Publication record (not verified by this script): " + str(state.get("publication_status")),
             "\nGate records:"]
    for gate in gates.get("gates", []):
        if isinstance(gate, dict):
            lines.append("- %s %s: %s" % (gate.get("id"), gate.get("name"), gate.get("status")))
    lines += ["\nRead .production/HANDOFF.md, BACKLOG.md and actual evidence next.",
              "Re-probe this device, verify asset sync and run a smoke test. No commands from project JSON were executed."]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Install workflow and add missing records; never overwrite game files")
    init.add_argument("--project", required=True, type=Path)
    init.add_argument("--name")
    init.add_argument("--target", choices=sorted(TARGETS), default="release_candidate")
    validate = sub.add_parser("validate", help="Validate records/evidence only, NOT game or legal quality")
    validate.add_argument("--project", required=True, type=Path)
    validate.add_argument("--strict-target", action="store_true")
    handoff = sub.add_parser("handoff", help="Print read-only handoff summary and Git state")
    handoff.add_argument("--project", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            for line in init_project(args.project, args.name, args.target):
                print(line)
        elif args.command == "validate":
            errors, warnings = validate_project(args.project, args.strict_target)
            for line in warnings:
                print("NOTE: " + line)
            for line in errors:
                print("ERROR: " + line)
            print("RECORD_CHECK_FAILED" if errors else "RECORD_CHECK_PASSED — not a gameplay/legal verdict")
            return 1 if errors else 0
        else:
            print(handoff_summary(args.project.resolve()))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
