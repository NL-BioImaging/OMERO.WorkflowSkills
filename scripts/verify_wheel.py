"""Verify that a built wheel contains the complete public library."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

CANONICAL_REQUIRED = {
    "biomero_workflow_skills/__init__.py",
    "biomero_workflow_skills/catalog.py",
    "biomero_workflow_skills/config.py",
    "biomero_workflow_skills/github.py",
    "biomero_workflow_skills/models.py",
    "biomero_workflow_skills/validation.py",
    "omero_workflow_skills/__init__.py",
    "omero_workflow_skills/__main__.py",
}


def verify(wheel: Path) -> bool:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")),
            None,
        )
        metadata = archive.read(metadata_name).decode("utf-8") if metadata_name else ""

    if wheel.name.startswith("biomero_workflow_skills-"):
        missing = sorted(CANONICAL_REQUIRED - names)
        if missing:
            print(f"{wheel.name} is incomplete: {', '.join(missing)}")
            return False
        if not any(name.endswith(".dist-info/licenses/LICENSE") for name in names):
            print(f"{wheel.name} does not contain LICENSE")
            return False
    elif wheel.name.startswith("omero_workflow_skills-"):
        requirement = "Requires-Dist: biomero-workflow-skills==0.3.0"
        if requirement not in metadata:
            print(f"{wheel.name} does not depend on biomero-workflow-skills 0.3.0")
            return False
    else:
        print(f"{wheel.name} is not a recognized workflow-skills distribution")
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
