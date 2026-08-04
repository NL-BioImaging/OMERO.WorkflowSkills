from __future__ import annotations

import pytest

from biomero_workflow_skills import ValidationError
from biomero_workflow_skills.validation import validate_skill

from .conftest import SKILL


def test_validates_metadata_and_matching_rules():
    summary, files = validate_skill(
        "example",
        "analyze-example-measurements",
        {
            "SKILL.md": SKILL.encode(),
            "references/REFERENCE.md": b"# Reference",
        },
        "/package/",
    )
    assert summary.consumers == ("omero-analysis",)
    assert summary.match.auto_activate is True
    assert summary.match.required_tables == ("schema_info", "measurement_runs")
    assert summary.required_resources == ("references/REFERENCE.md",)
    assert summary.required_capabilities == ("zarr-render-v2", "zarr-gallery-v1")
    assert len(summary.sha256) == 64
    assert [item.path for item in files] == ["SKILL.md", "references/REFERENCE.md"]


@pytest.mark.parametrize(
    ("name", "files"),
    [
        ("different-name", {"SKILL.md": SKILL.encode()}),
        (
            "analyze-example-measurements",
            {"SKILL.md": SKILL.encode(), "../secret.md": b"secret"},
        ),
        (
            "analyze-example-measurements",
            {"SKILL.md": SKILL.encode(), "scripts/run.py": b"print('no')"},
        ),
        (
            "analyze-example-measurements",
            {"SKILL.md": SKILL.encode(), "references/image.png": b"\x00PNG"},
        ),
    ],
)
def test_rejects_invalid_packages(name, files):
    with pytest.raises(ValidationError):
        validate_skill("example", name, files, "/package/")


def test_requires_string_metadata_values():
    invalid = SKILL.replace('version: "2"', "version: 2")
    with pytest.raises(ValidationError, match="metadata values"):
        validate_skill(
            "example",
            "analyze-example-measurements",
            {"SKILL.md": invalid.encode()},
            "/package/",
        )


def test_rejects_missing_required_resource():
    with pytest.raises(ValidationError, match="required resource"):
        validate_skill(
            "example",
            "analyze-example-measurements",
            {"SKILL.md": SKILL.encode()},
            "/package/",
        )


def test_rejects_invalid_required_capability():
    invalid = SKILL.replace(
        "zarr-render-v2,zarr-gallery-v1",
        "zarr-render-v2,Invalid Capability",
    )
    with pytest.raises(ValidationError, match="required capability"):
        validate_skill(
            "example",
            "analyze-example-measurements",
            {
                "SKILL.md": invalid.encode(),
                "references/REFERENCE.md": b"# Reference",
            },
            "/package/",
        )
