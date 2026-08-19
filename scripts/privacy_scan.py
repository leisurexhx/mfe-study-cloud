"""Fail when publishable files or Git history contain likely private material."""

from __future__ import annotations

import argparse
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = "scripts/privacy_scan.py"
PATTERNS = {
    "OpenAI-style secret": re.compile(r"\b" + "sk-" + r"[A-Za-z0-9_-]{20,}\b"),
    "GitHub token": re.compile(r"\b" + "gh" + r"[opsu]_[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bA" + r"KIA[0-9A-Z]{16}\b"),
    "private key": re.compile("-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "personal home path": re.compile(
        r"(?i)(?:[A-Z]:\\(?:Users|Documents|Desktop)\\|/(?:Users|home)/)[^\s/\\]+"
    ),
    "private source name": re.compile("mfe-study-" + "assistant", re.IGNORECASE),
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT, stderr=subprocess.DEVNULL)


def current_files() -> Iterable[tuple[str, bytes]]:
    listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    for raw_name in listed.split(b"\0"):
        if not raw_name:
            continue
        name = raw_name.decode("utf-8", errors="surrogateescape")
        if name == SELF:
            continue
        path = ROOT / name
        if path.is_file():
            yield name, path.read_bytes()


def history_files() -> Iterable[tuple[str, bytes]]:
    for commit in git("rev-list", "--all").decode().splitlines():
        names = git("ls-tree", "-r", "-z", "--name-only", commit)
        for raw_name in names.split(b"\0"):
            if not raw_name:
                continue
            name = raw_name.decode("utf-8", errors="surrogateescape")
            if name == SELF:
                continue
            try:
                content = git("show", f"{commit}:{name}")
            except subprocess.CalledProcessError:
                continue
            yield f"{commit[:12]}:{name}", content


def findings(files: Iterable[tuple[str, bytes]]) -> list[str]:
    found: list[str] = []
    for name, content in files:
        if b"\0" in content[:8192]:
            continue
        text = content.decode("utf-8", errors="replace")
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                found.append(f"{name}:{line}: {label}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args()
    found = findings(current_files())
    if args.history:
        found.extend(findings(history_files()))
    if found:
        print("Privacy scan failed:")
        print("\n".join(sorted(set(found))))
        return 1
    print("Privacy scan passed: no configured private-material patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
