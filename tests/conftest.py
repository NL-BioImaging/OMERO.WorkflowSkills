from __future__ import annotations

from dataclasses import dataclass

import pytest

from omero_workflow_skills.github import RepositoryLocation, ResolvedRepository

SKILL = """---
name: analyze-example-measurements
description: Analyze Example measurement databases in DuckDB or SQLite.
metadata:
  version: "2"
  biomero-purpose: attachment-analysis
  biomero-consumers: "omero-analysis-chat,omero-jupyterlite"
  biomero-auto-activate: "true"
  biomero-file-extensions: ".duckdb,.sqlite"
  biomero-filename-globs: "*measurements*.duckdb"
  biomero-required-tables: "schema_info,measurement_runs"
---

# Instructions

Read [the schema](references/REFERENCE.md) before writing substantive queries.
"""


@dataclass
class FakeGitHub:
    fail: bool = False
    duplicate: bool = False
    no_skills: bool = False

    def resolve_repository(self, repository_url: str) -> ResolvedRepository:
        if self.fail:
            from omero_workflow_skills import TransientGitHubError

            raise TransientGitHubError("temporary GitHub outage")
        ref = repository_url.split("/tree/", 1)[1] if "/tree/" in repository_url else "main"
        return ResolvedRepository(
            RepositoryLocation("example", "workflow", ref, ""),
            "a" * 40,
            "tag" if ref.startswith("v") else "branch",
        )

    def list_directory(
        self, source: ResolvedRepository, path: str
    ) -> list[dict[str, object]]:
        if self.no_skills and path == "_agents/skills":
            from omero_workflow_skills import GitHubError

            raise GitHubError("GitHub resource was not found")
        if path == "_agents/skills":
            name = "analyze-example-measurements"
            return [{"name": name, "type": "dir"}]
        if path.endswith("analyze-example-measurements"):
            return [
                {"name": "SKILL.md", "type": "file"},
                {"name": "references", "type": "dir"},
            ]
        if path.endswith("references"):
            return [{"name": "REFERENCE.md", "type": "file"}]
        return []

    def read_file(self, source: ResolvedRepository, path: str) -> bytes:
        if path.endswith("SKILL.md"):
            return SKILL.encode()
        return b"# Reference\n\nDatabase schema reference."


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "slurm-config.ini"
    path.write_text(
        """
[WORKFLOWS]
example = example
example_repo = https://github.com/example/workflow/tree/v1.2.3

[UI]
plate_workflows = ["example"]
zarr_workflows = ["example"]
""".strip(),
        encoding="utf-8",
    )
    return path
