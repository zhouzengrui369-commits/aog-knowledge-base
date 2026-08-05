#!/usr/bin/env python3
"""Validate a ChatGPT Parent PM project installation using only stdlib."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = [
    "AGENTS.md",
    "PROJECT_STATUS.md",
    ".github/skills/chatgpt-parent-pm/SKILL.md",
    ".github/skills/chatgpt-parent-pm/PROJECT_PROFILE.yaml",
    ".github/skills/chatgpt-parent-pm/GOVERNANCE_LOCK.json",
]

PROFILE_KEYS = [
    "project_id:",
    "project_type:",
    "repository:",
    "default_branch:",
    "roles:",
    "commands:",
    "policies:",
    "owner_only_actions:",
]

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def validate(root: Path, allow_placeholder_lock: bool = False) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing required file: {rel}")

    profile = root / ".github/skills/chatgpt-parent-pm/PROJECT_PROFILE.yaml"
    if profile.is_file():
        text = profile.read_text(encoding="utf-8")
        for key in PROFILE_KEYS:
            if key not in text:
                errors.append(f"project profile missing key: {key}")
        for unsafe in (
            "direct_main_write: true",
            "automatic_merge: true",
            "automatic_release: true",
        ):
            if unsafe in text:
                errors.append(f"unsafe project policy: {unsafe}")

    lock_path = root / ".github/skills/chatgpt-parent-pm/GOVERNANCE_LOCK.json"
    if lock_path.is_file():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid governance lock JSON: {exc}")
        else:
            if lock.get("framework") != "chatgpt-parent-pm":
                errors.append("governance lock framework must be chatgpt-parent-pm")
            commit = lock.get("core_commit", "")
            if not SHA40.fullmatch(commit):
                errors.append("governance lock core_commit must be a lowercase 40-hex SHA")
            elif commit == "0" * 40 and not allow_placeholder_lock:
                errors.append("governance lock still uses the placeholder core_commit")
            policies = lock.get("policies", {})
            for key in ("direct_main_write", "automatic_merge", "automatic_release"):
                if policies.get(key) is not False:
                    errors.append(f"governance lock policy {key} must be false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--allow-placeholder-lock", action="store_true")
    args = parser.parse_args()

    errors = validate(Path(args.root).resolve(), args.allow_placeholder_lock)
    if errors:
        print("GOVERNANCE_INSTALL: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("GOVERNANCE_INSTALL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
