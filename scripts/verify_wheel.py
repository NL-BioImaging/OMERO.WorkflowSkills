"""Verify that a built wheel contains the complete public library."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REQUIRED = {
    "biomero_workflow_skills/__init__.py",
    "biomero_workflow_skills/catalog.py",
    "biomero_workflow_skills/config.py",
    "biomero_workflow_skills/github.py",
    "biomero_workflow_skills/models.py",
    "biomero_workflow_skills/validation.py",
}


def verify(wheel: Path) -> bool:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    if not wheel.name.startswith("biomero_workflow_skills-"):
        print(f"{wheel.name} is not a recognized workflow-skills distribution")
        return False
    missing = sorted(REQUIRED - names)
    if missing:
        print(f"{wheel.name} is incomplete: {', '.join(missing)}")
        return False
    unexpected = sorted(
        name
        for name in names
        if name.endswith(".py") and not name.startswith("biomero_workflow_skills/")
    )
    if unexpected:
        print(f"{wheel.name} contains unexpected modules: {', '.join(unexpected)}")
        return False
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
        print(f"{wheel.name} does not contain LICENSE")
        return False

    print(f"{wheel.name}: verified {len(names)} archive members")
    return True


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: verify_wheel.py path/to/wheel [path/to/wheel ...]")
        return 2
    return 0 if all(verify(Path(argument)) for argument in sys.argv[1:]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
