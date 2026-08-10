"""Serializable catalog data structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

CatalogStatus = Literal["ready", "no-skills", "stale", "error"]
DiagnosticLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class SkillMatchRules:
    extensions: tuple[str, ...] = ()
    filename_globs: tuple[str, ...] = ()
    required_tables: tuple[str, ...] = ()
    auto_activate: bool = False


@dataclass(frozen=True)
class WorkflowSource:
    workflow_key: str
    repository_url: str
    owner: str
    repository: str
    configured_ref: str
    resolved_commit: str
    skills_path: str
    descriptor_path: str = ""
    ref_kind: str = "commit"
    ui_modes: tuple[str, ...] = ()
    source_kind: Literal["workflow", "application"] = "workflow"
    source_key: str = ""
    plugin_identity: str = ""
    plugin_version: str = ""
    plugin_path: str = ""
    plugin_sha256: str = ""
    format: Literal["agent-plugin-v1", "legacy-agent-skills"] = "legacy-agent-skills"


@dataclass(frozen=True)
class SkillFile:
    path: str
    media_type: str
    size: int
    sha256: str
    content: str


@dataclass(frozen=True)
class WorkflowSkillSummary:
    workflow_key: str
    name: str
    description: str
    purpose: str
    consumers: tuple[str, ...]
    version: str
    sha256: str
    package_url: str
    match: SkillMatchRules = field(default_factory=SkillMatchRules)
    required_resources: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    preferred_capabilities: tuple[str, ...] = ()
    source_kind: Literal["workflow", "application"] = "workflow"
    source_key: str = ""


@dataclass(frozen=True)
class WorkflowSkillPackage:
    source: WorkflowSource
    skill: WorkflowSkillSummary
    files: tuple[SkillFile, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CatalogDiagnostic:
    level: DiagnosticLevel
    code: str
    message: str
    workflow_key: str = ""
    skill_name: str = ""


@dataclass(frozen=True)
class WorkflowCatalogEntry:
    source: WorkflowSource
    status: CatalogStatus
    checked_at: str
    skills: tuple[WorkflowSkillSummary, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class WorkflowSkillCatalogV1:
    schema: str
    generated_at: str
    consumer: str
    config_hash: str
    workflows: tuple[WorkflowCatalogEntry, ...]
    applications: tuple[WorkflowCatalogEntry, ...] = ()
    diagnostics: tuple[CatalogDiagnostic, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowSkillCatalogV2(WorkflowSkillCatalogV1):
    """Agent Plugin-aware catalog; V1 fields remain source compatible."""
