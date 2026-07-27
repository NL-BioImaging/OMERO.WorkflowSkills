from __future__ import annotations

import json

import pytest

from omero_workflow_skills import (
    CatalogError,
    SkillNotFoundError,
    WorkflowSkillCatalog,
)

from .conftest import FakeGitHub


def test_builds_consumer_filtered_catalog(config_file, tmp_path):
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
        package_url=lambda workflow, skill: f"/api/{workflow}/{skill}/",
    )
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.schema == "nl.bioimaging.omero-workflow-skills.v1"
    assert len(result.workflows) == 1
    workflow = result.workflows[0]
    assert workflow.status == "ready"
    assert workflow.source.ui_modes == ("plate", "zarr")
    assert workflow.skills[0].package_url.startswith("/api/example/")
    package = catalog.get_package(
        "example",
        "analyze-example-measurements",
    )
    assert package.source.configured_ref == "v1.2.3"
    assert package.files[0].path == "SKILL.md"


def test_package_requires_catalog_or_explicit_consumer(config_file, tmp_path):
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
    )
    with pytest.raises(CatalogError, match="Call get_catalog"):
        catalog.get_package("example", "analyze-example-measurements")

    package = catalog.get_package(
        "example",
        "analyze-example-measurements",
        consumer="omero-analysis-chat",
    )
    assert package.skill.name == "analyze-example-measurements"


def test_unknown_consumer_cannot_load_package(config_file, tmp_path):
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
    )
    result = catalog.get_catalog("another-consumer")
    assert result.workflows[0].skills == ()
    with pytest.raises(SkillNotFoundError):
        catalog.get_package(
            "example", "analyze-example-measurements", "another-consumer"
        )


def test_missing_skill_folder_is_not_an_error(config_file, tmp_path):
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(no_skills=True),
    )
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows[0].status == "no-skills"
    assert result.diagnostics == ()


def test_same_source_uses_stale_cache_after_failure(config_file, tmp_path):
    fake = FakeGitHub()
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=fake,
    )
    catalog.get_catalog("omero-analysis-chat")
    cache_file = next((tmp_path / "cache" / "workflows").glob("*.json"))
    cached = json.loads(cache_file.read_text(encoding="utf-8"))
    cached["source"]["ref_kind"] = "branch"
    cached["packages"][0]["source"]["ref_kind"] = "branch"
    cached["checked_at"] = "2000-01-01T00:00:00Z"
    cache_file.write_text(json.dumps(cached), encoding="utf-8")
    fake.fail = True
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows[0].status == "stale"
    assert result.workflows[0].skills[0].name == "analyze-example-measurements"
    assert result.diagnostics[0].code == "stale-cache"


def test_changed_revision_does_not_reuse_old_cache(config_file, tmp_path):
    fake = FakeGitHub()
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=fake,
    )
    catalog.get_catalog("omero-analysis-chat")
    config_file.write_text(
        config_file.read_text().replace("v1.2.3", "v2.0.0"),
        encoding="utf-8",
    )
    fake.fail = True
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows[0].status == "error"
    assert result.workflows[0].skills == ()


def test_changed_ui_classification_does_not_reuse_old_cache(config_file, tmp_path):
    fake = FakeGitHub()
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=fake,
    )
    catalog.get_catalog("omero-analysis-chat")
    config_file.write_text(
        config_file.read_text().replace(
            'plate_workflows = ["example"]', "plate_workflows = []"
        ),
        encoding="utf-8",
    )
    fake.fail = True
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows[0].status == "error"
    assert result.workflows[0].source.ui_modes == ("zarr",)


def test_refresh_removes_cached_packages(config_file, tmp_path):
    fake = FakeGitHub()
    catalog = WorkflowSkillCatalog(
        config_path=config_file,
        cache_dir=tmp_path / "cache",
        github=fake,
    )
    catalog.get_catalog("omero-analysis-chat")
    assert list((tmp_path / "cache" / "workflows").glob("*.json"))
    catalog.refresh()
    assert not list((tmp_path / "cache" / "workflows").glob("*.json"))


def test_builds_application_catalog_and_loads_package(tmp_path):
    config = tmp_path / "slurm-config.ini"
    config.write_text(
        """
[APPLICATIONS]
omero-zarr-viewer_repo = https://github.com/example/viewer/tree/v0.3.0
""".strip(),
        encoding="utf-8",
    )
    catalog = WorkflowSkillCatalog(
        config_path=config,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
    )
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows == ()
    assert len(result.applications) == 1
    application = result.applications[0]
    assert application.source.source_kind == "application"
    assert application.source.source_key == "omero-zarr-viewer"
    assert application.skills[0].source_kind == "application"
    package = catalog.get_package(
        "omero-zarr-viewer", "analyze-example-measurements"
    )
    assert package.source.configured_ref == "v0.3.0"


def test_duplicate_names_across_workflow_and_application_are_hidden(tmp_path):
    config = tmp_path / "slurm-config.ini"
    config.write_text(
        """
[WORKFLOWS]
example_repo = https://github.com/example/workflow/tree/v1.2.3

[APPLICATIONS]
viewer_repo = https://github.com/example/viewer/tree/v0.3.0
""".strip(),
        encoding="utf-8",
    )
    catalog = WorkflowSkillCatalog(
        config_path=config,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
    )
    result = catalog.get_catalog("omero-analysis-chat")
    assert result.workflows[0].skills == ()
    assert result.applications[0].skills == ()
    assert any(item.code == "duplicate-skill-name" for item in result.diagnostics)


def test_identical_skill_from_workflow_aliases_remains_available(tmp_path):
    config = tmp_path / "slurm-config.ini"
    config.write_text(
        """
[WORKFLOWS]
cisegmentation_repo = https://github.com/example/workflow/tree/v1.2.3
rt_cisegmentation_repo = https://github.com/example/workflow/tree/v1.2.3
""".strip(),
        encoding="utf-8",
    )
    catalog = WorkflowSkillCatalog(
        config_path=config,
        cache_dir=tmp_path / "cache",
        github=FakeGitHub(),
    )

    result = catalog.get_catalog("omero-analysis-chat")

    assert [entry.skills[0].name for entry in result.workflows] == [
        "analyze-example-measurements",
        "analyze-example-measurements",
    ]
    assert not any(
        item.code == "duplicate-skill-name" for item in result.diagnostics
    )
    assert (
        catalog.get_package(
            "cisegmentation", "analyze-example-measurements"
        ).skill.name
        == "analyze-example-measurements"
    )
    assert (
        catalog.get_package(
            "rt_cisegmentation", "analyze-example-measurements"
        ).skill.name
        == "analyze-example-measurements"
    )
