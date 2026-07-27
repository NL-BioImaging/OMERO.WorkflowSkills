from __future__ import annotations

from omero_workflow_skills.config import load_configuration


def test_merges_models_then_workflows(tmp_path):
    path = tmp_path / "slurm-config.ini"
    path.write_text(
        """
[MODELS]
old_repo = https://github.com/example/old/tree/v1
same_repo = https://github.com/example/legacy/tree/v1

[WORKFLOWS]
same_repo = https://github.com/example/current/tree/v2
new_repo = https://github.com/example/new/tree/v3
new_skills_path = ai/skills

[UI]
plate_workflows = ["same"]
zarr_workflows = ["same", "new"]
""".strip(),
        encoding="utf-8",
    )
    result = load_configuration(path)
    by_key = {workflow.key: workflow for workflow in result.workflows}
    assert set(by_key) == {"new", "old", "same"}
    assert by_key["same"].repository_url.endswith("/current/tree/v2")
    assert by_key["same"].ui_modes == ("plate", "zarr")
    assert by_key["new"].skills_path == "ai/skills"
    assert by_key["old"].ui_modes == ("standard",)


def test_environment_override(monkeypatch, tmp_path):
    path = tmp_path / "custom.ini"
    path.write_text(
        "[WORKFLOWS]\na_repo=https://github.com/x/y/tree/main\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OMERO_WORKFLOW_SKILLS_CONFIG", str(path))
    result = load_configuration()
    assert result.paths == (str(path.resolve()),)
    assert result.workflows[0].key == "a"


def test_reads_application_skill_sources(tmp_path):
    path = tmp_path / "slurm-config.ini"
    path.write_text(
        """
[APPLICATIONS]
omero-zarr-viewer_repo = https://github.com/NL-BioImaging/BIOMERO.ZarrViewer/tree/v0.3.0
omero-zarr-viewer_skills_path = _agents/skills
""".strip(),
        encoding="utf-8",
    )
    result = load_configuration(path)
    assert result.workflows == ()
    assert len(result.applications) == 1
    application = result.applications[0]
    assert application.key == "omero-zarr-viewer"
    assert application.skills_path == "_agents/skills"
    assert application.ui_modes == ()


def test_missing_configuration_is_an_empty_authoritative_snapshot(tmp_path):
    result = load_configuration(tmp_path / "missing.ini")
    assert result.paths == ()
    assert result.workflows == ()
    assert result.applications == ()
    assert len(result.content_hash) == 64


def test_content_changes_change_hash(config_file):
    first = load_configuration(config_file)
    config_file.write_text(config_file.read_text() + "\n# changed\n", encoding="utf-8")
    second = load_configuration(config_file)
    assert first.content_hash != second.content_hash
