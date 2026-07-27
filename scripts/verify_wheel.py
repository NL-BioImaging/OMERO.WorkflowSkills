"""Verify that a built wheel contains the complete public library."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REQUIRED = {
    "omero_workflow_skills/__init__.py",
    "omero_workflow_skills/catalog.py",
    "omero_workflow_skills/config.py",
    "omero_workflow_skills/github.py",
    "omero_workflow_skills/models.py",
    "omero_workflow_skills/validation.py",
}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: verify_wheel.py path/to/wheel")
        return 2
    wheel = Path(sys.argv[1])
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = sorted(REQUIRED - names)
    if missing:
        print(f"{wheel.name} is incomplete: {', '.join(missing)}")
        return 1
    if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
        print(f"{wheel.name} does not contain LICENSE")
        return 1
    print(f"{wheel.name}: verified {len(names)} archive members")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
