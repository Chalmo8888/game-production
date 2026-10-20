#!/usr/bin/env python3
"""Repository checks for the two-skill layout. Python 3.9+, standard library only.

  python tools/repo_check.py                    # check, exit 1 on problems
  python tools/repo_check.py --write-manifests  # regenerate skills/*/SHA256SUMS.txt, then check

Checks: exactly two Skill entries; no retired single-skill files at the root; each
skill's SHA256SUMS lists exactly its files with matching hashes; relative Markdown
links resolve; no machine paths or secrets; shared workspace templates are identical;
no references to retired entry points outside the history files.
"""
import argparse
import hashlib
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ("game-reverse-engineering", "game-creation-polish")
RETIRED_ROOT = ("SKILL.md", "SHA256SUMS.txt", "prompts", "references", "templates", "scripts", "tests/test_project.py")
SHARED_TEMPLATES = ("workspace/HANDOFF.md", "workspace/RIGHTS_LEDGER.md", "workspace/ENVIRONMENT.local.json")
HISTORY_FILES = {"CHANGELOG.md", "QA_REPORT.md"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
RETIRED_TERMS = re.compile(r"scripts/project\.py|\bproject\.py\b|game-production v4|GAME_PRODUCTION_V4|START_RESEARCH|"
                           r"START_FULL_PIPELINE|MIGRATION_V[123]|V4_INTEGRATION|templates/v4|skills/game-production\b|"
                           r"\.agents/skills/game-production\b")
MACHINE_PATH = re.compile(r"(?<![A-Za-z0-9%])[A-Za-z]:\\[A-Za-z0-9_.-]{2,}|/(?:Users|home)/[a-z][a-z0-9_-]+/")
SECRET = re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|\bsk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
                    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:(?:password|secret|token)\s*[:=]\s*['\"][^'\"]{6,})")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def listed_files(root: Path) -> List[str]:
    """Files in the Git index (what gets committed); falls back to a directory walk without Git."""
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=20)
        is_repo_root = top.returncode == 0 and Path(top.stdout.strip()).resolve() == root.resolve()
        out = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "-z"],
                             capture_output=True, timeout=20)
        if is_repo_root and out.returncode == 0:
            names = [n for n in out.stdout.decode("utf-8").split("\0") if n]
            return sorted(n for n in names if (root / n).is_file())
    except (OSError, subprocess.SubprocessError):
        pass
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*")
                  if p.is_file() and not (set(p.relative_to(root).parts) & SKIP_DIRS))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def skill_files(root: Path, skill: str) -> List[str]:
    prefix = "skills/%s/" % skill
    return [n[len(prefix):] for n in listed_files(root) if n.startswith(prefix) and n[len(prefix):] != "SHA256SUMS.txt"
            and not (set(n.split("/")) & SKIP_DIRS) and not n.endswith((".pyc", ".pyo"))]


def write_manifests(root: Path) -> None:
    for skill in SKILLS:
        folder = root / "skills" / skill
        lines = ["%s  %s" % (lf_sha(folder / name), name) for name in sorted(skill_files(root, skill))]
        (folder / "SHA256SUMS.txt").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def check(root: Path = ROOT) -> List[str]:
    root = root.resolve()
    problems = []
    files = listed_files(root)
    entries = sorted(n for n in files if n.endswith("/SKILL.md") or n == "SKILL.md")
    expected = sorted("skills/%s/SKILL.md" % s for s in SKILLS)
    if entries != expected:
        problems.append("Skill entries must be exactly %s, found %s" % (expected, entries))
    for name in RETIRED_ROOT:
        if any(n == name or n.startswith(name + "/") for n in files):
            problems.append("retired single-skill file or folder still present at the root: " + name)
    for skill in SKILLS:
        folder = root / "skills" / skill
        sums = folder / "SHA256SUMS.txt"
        if not sums.is_file():
            problems.append("%s has no SHA256SUMS.txt" % skill)
            continue
        listed = {}
        for line in sums.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line.strip())
            if not match:
                problems.append("%s: malformed manifest line %r" % (skill, line))
                continue
            listed[match.group(2)] = match.group(1)
        actual = set(skill_files(root, skill))
        for name in sorted(actual - set(listed)):
            problems.append("%s: file missing from manifest: %s" % (skill, name))
        for name in sorted(set(listed) - actual):
            problems.append("%s: manifest lists a missing file: %s" % (skill, name))
        for name in sorted(actual & set(listed)):
            if lf_sha(folder / name) != listed[name]:
                problems.append("%s: manifest hash mismatch: %s" % (skill, name))
    for name in SHARED_TEMPLATES:
        a, b = (root / "skills" / s / "templates" / name for s in SKILLS)
        if not a.is_file() or not b.is_file() or lf_sha(a) != lf_sha(b):
            problems.append("shared workspace template differs between the skills: " + name)
    for name in files:
        path = root / name
        if path.suffix not in (".md", ".py", ".json", ".txt", ".gitignore", ".gitattributes") and path.name not in (".gitignore", ".gitattributes"):
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        is_test = "/tests/" in "/" + name or name.startswith("tests/")
        if name != "tools/repo_check.py":
            if not is_test:
                match = MACHINE_PATH.search(content)
                if match:
                    problems.append("%s contains a machine-specific path or user name: %r" % (name, match.group(0)[:40]))
            match = SECRET.search(content)
            if match:
                problems.append("%s looks like it contains a secret: %r" % (name, match.group(0)[:12] + "..."))
            if Path(name).name not in HISTORY_FILES and not is_test:
                for line in content.splitlines():
                    if RETIRED_TERMS.search(line):
                        problems.append("%s references a retired entry point: %s" % (name, line.strip()[:100]))
                        break
        if path.suffix == ".md":
            for target in LINK.findall(content):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                relative = target.split("#")[0]
                if relative and not (path.parent / relative).resolve().exists():
                    problems.append("%s has a broken link: %s" % (name, target))
        if path.suffix == ".py":
            try:
                py_compile.compile(str(path), doraise=True, cfile=str(Path(tempfile.gettempdir()) / "repo_check.pyc"))
            except py_compile.PyCompileError as exc:
                problems.append("%s does not compile: %s" % (name, exc.msg[:120]))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-manifests", action="store_true")
    args = parser.parse_args(argv)
    if args.write_manifests:
        write_manifests(ROOT)
        print("Manifests written for: " + ", ".join(SKILLS))
    problems = check(ROOT)
    for line in problems:
        print("PROBLEM: " + line)
    print("REPO_CHECK_FAILED" if problems else "REPO_CHECK_PASSED")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
