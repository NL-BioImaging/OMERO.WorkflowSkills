"""Workflow skill catalog orchestration."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from .cache import CatalogCache
from .config import ConfiguredWorkflow, load_configuration
from .errors import (
    CatalogError,
    GitHubError,
    SkillNotFoundError,
    TransientGitHubError,
    ValidationError,
)
from .github import GitHubClient, ResolvedRepository
from .models import (
    CatalogDiagnostic,
    CatalogStatus,
    SkillFile,
    SkillMatchRules,
    WorkflowCatalogEntry,
    WorkflowSkillCatalogV1,
    WorkflowSkillPackage,
    WorkflowSkillSummary,
    WorkflowSource,
)
from .validation import MAX_SKILLS_PER_WORKFLOW, validate_skill

CATALOG_SCHEMA = "nl.bioimaging.omero-workflow-skills.v1"


class WorkflowSkillCatalog:
    def __init__(
        self,
        config_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
        github: GitHubClient | None = None,
        package_url: Callable[[str, str], str] | None = None,
    ) -> None:
        self.config_path = config_path
        self.cache = CatalogCache(cache_dir)
        self.github = github or GitHubClient()
        self.package_url = package_url or (
            lambda workflow, skill: f"workflow-skills/{workflow}/{skill}/"
        )
        self._last_catalog: WorkflowSkillCatalogV1 | None = None
        self._packages: dict[tuple[str, str], WorkflowSkillPackage] = {}

    def get_catalog(self, consumer: str) -> WorkflowSkillCatalogV1:
        consumer = _consumer(consumer)
        configuration = load_configuration(self.config_path)
        workflow_entries: list[WorkflowCatalogEntry] = []
        application_entries: list[WorkflowCatalogEntry] = []
        diagnostics: list[CatalogDiagnostic] = []
        packages: dict[tuple[str, str], WorkflowSkillPackage] = {}
        with self.cache.locked():
            for workflow in configuration.workflows:
                entry, found_packages, found_diagnostics = self._source(
                    workflow, consumer, source_kind="workflow"
                )
                workflow_entries.append(entry)
                packages.update(found_packages)
                diagnostics.extend(found_diagnostics)
            for application in configuration.applications:
                entry, found_packages, found_diagnostics = self._source(
                    application, consumer, source_kind="application"
                )
                application_entries.append(entry)
                packages.update(found_packages)
                diagnostics.extend(found_diagnostics)

        duplicates: dict[str, list[str]] = {}
        for entry in (*workflow_entries, *application_entries):
            for skill in entry.skills:
                duplicates.setdefault(skill.name, []).append(_source_key(entry.source))
        conflicts = {name: keys for name, keys in duplicates.items() if len(keys) > 1}
        if conflicts:
            def without_conflicts(
                entries: list[WorkflowCatalogEntry],
            ) -> list[WorkflowCatalogEntry]:
                filtered: list[WorkflowCatalogEntry] = []
                for entry in entries:
                    skills = tuple(
                        skill for skill in entry.skills if skill.name not in conflicts
                    )
                    filtered.append(
                        WorkflowCatalogEntry(
                            source=entry.source,
                            status=entry.status,
                            checked_at=entry.checked_at,
                            skills=skills,
                            error=entry.error,
                        )
                    )
                return filtered

            workflow_entries = without_conflicts(workflow_entries)
            application_entries = without_conflicts(application_entries)
            for name, keys in sorted(conflicts.items()):
                diagnostics.append(
                    CatalogDiagnostic(
                        level="error",
                        code="duplicate-skill-name",
                        message=f"Skill {name!r} is defined by: {', '.join(sorted(keys))}",
                        skill_name=name,
                    )
                )
                for key in list(packages):
                    if key[1] == name:
                        packages.pop(key)

        catalog = WorkflowSkillCatalogV1(
            schema=CATALOG_SCHEMA,
            generated_at=_now(),
            consumer=consumer,
            config_hash=configuration.content_hash,
            workflows=tuple(workflow_entries),
            applications=tuple(application_entries),
            diagnostics=tuple(diagnostics),
        )
        self._last_catalog = catalog
        self._packages = packages
        return catalog

    def get_package(
        self, workflow_key: str, skill_name: str, consumer: str | None = None
    ) -> WorkflowSkillPackage:
        if consumer is not None:
            catalog = self.get_catalog(consumer)
        elif self._last_catalog is None:
            raise CatalogError(
                "Call get_catalog(consumer) before get_package(), or pass consumer="
            )
        else:
            catalog = self._last_catalog
        allowed = {
            (_source_key(entry.source), skill.name)
            for entry in (*catalog.workflows, *catalog.applications)
            for skill in entry.skills
        }
        key = (workflow_key, skill_name)
        if key not in allowed or key not in self._packages:
            raise SkillNotFoundError(
                f"Skill {workflow_key}/{skill_name} is unavailable to {catalog.consumer}"
            )
        return self._packages[key]

    def refresh(self) -> None:
        with self.cache.locked():
            state = self.cache.read_json("state") or {}
            for key in state.get("workflow_cache_keys", []):
                if isinstance(key, str):
                    self.cache.delete(f"workflows/{key}")
            self.cache.delete("state")
        self._last_catalog = None
        self._packages = {}

    def status(self) -> dict[str, Any]:
        configuration = load_configuration(self.config_path)
        return {
            "schema": CATALOG_SCHEMA,
            "version": "0.2.0",
            "config_paths": list(configuration.paths),
            "config_hash": configuration.content_hash,
            "workflow_count": len(configuration.workflows),
            "application_count": len(configuration.applications),
            "cache_dir": str(self.cache.root),
            "last_catalog": self._last_catalog.to_dict() if self._last_catalog else None,
        }

    def _source(
        self,
        workflow: ConfiguredWorkflow,
        consumer: str,
        *,
        source_kind: Literal["workflow", "application"],
    ) -> tuple[
        WorkflowCatalogEntry,
        dict[tuple[str, str], WorkflowSkillPackage],
        list[CatalogDiagnostic],
    ]:
        source_signature = "\0".join(
            (
                source_kind,
                workflow.key,
                workflow.repository_url,
                workflow.skills_path,
                ",".join(workflow.ui_modes),
            )
        )
        cache_key = hashlib.sha256(
            source_signature.encode()
        ).hexdigest()
        cached = self.cache.read_json(f"workflows/{cache_key}")
        restored = _cached_packages(cached)
        cached_source = _cached_source(cached, restored)
        if cached_source and _cache_is_current(cached, cached_source):
            filtered = {
                key: package
                for key, package in restored.items()
                if consumer in package.skill.consumers
            }
            cached_status: CatalogStatus = "ready" if restored else "no-skills"
            return (
                WorkflowCatalogEntry(
                    source=cached_source,
                    status=cached_status,
                    checked_at=str((cached or {}).get("checked_at", "")),
                    skills=tuple(package.skill for package in filtered.values()),
                ),
                filtered,
                [],
            )
        try:
            resolved = self.github.resolve_repository(workflow.repository_url)
            packages, diagnostics = self._download(
                workflow, resolved, source_kind=source_kind
            )
            checked_at = _now()
            payload = {
                "source_signature": source_signature,
                "checked_at": checked_at,
                "source": asdict(
                    _workflow_source(workflow, resolved, source_kind=source_kind)
                ),
                "packages": [_package_dict(package) for package in packages.values()],
                "diagnostics": [asdict(item) for item in diagnostics],
            }
            self.cache.write_json(f"workflows/{cache_key}", payload)
            self._remember_key(cache_key)
            status: CatalogStatus = "ready" if packages else "no-skills"
            filtered = {
                key: package
                for key, package in packages.items()
                if consumer in package.skill.consumers
            }
            return (
                WorkflowCatalogEntry(
                    source=_workflow_source(
                        workflow, resolved, source_kind=source_kind
                    ),
                    status=status,
                    checked_at=checked_at,
                    skills=tuple(package.skill for package in filtered.values()),
                ),
                filtered,
                diagnostics,
            )
        except TransientGitHubError as exc:
            if cached_source:
                filtered = {
                    key: package
                    for key, package in restored.items()
                    if consumer in package.skill.consumers
                }
                diagnostic = CatalogDiagnostic(
                    level="warning",
                    code="stale-cache",
                    message=str(exc),
                    workflow_key=workflow.key,
                )
                return (
                    WorkflowCatalogEntry(
                        source=cached_source,
                        status="stale",
                        checked_at=str((cached or {}).get("checked_at", "")),
                        skills=tuple(package.skill for package in filtered.values()),
                        error=str(exc),
                    ),
                    filtered,
                    [diagnostic],
                )
            return self._error_entry(workflow, exc, source_kind=source_kind)
        except (CatalogError, OSError) as exc:
            return self._error_entry(workflow, exc, source_kind=source_kind)

    def _error_entry(
        self,
        workflow: ConfiguredWorkflow,
        exc: Exception,
        *,
        source_kind: Literal["workflow", "application"],
    ) -> tuple[
        WorkflowCatalogEntry,
        dict[tuple[str, str], WorkflowSkillPackage],
        list[CatalogDiagnostic],
    ]:
        empty = WorkflowSource(
            workflow_key=workflow.key,
            repository_url=workflow.repository_url,
            owner="",
            repository="",
            configured_ref="",
            resolved_commit="",
            skills_path=workflow.skills_path,
            ui_modes=workflow.ui_modes,
            source_kind=source_kind,
            source_key=workflow.key,
        )
        return (
            WorkflowCatalogEntry(
                source=empty,
                status="error",
                checked_at=_now(),
                error=str(exc),
            ),
            {},
            [
                CatalogDiagnostic(
                    level="error",
                    code=f"{source_kind}-fetch-failed",
                    message=str(exc),
                    workflow_key=workflow.key,
                )
            ],
        )

    def _download(
        self,
        workflow: ConfiguredWorkflow,
        resolved: ResolvedRepository,
        *,
        source_kind: Literal["workflow", "application"],
    ) -> tuple[
        dict[tuple[str, str], WorkflowSkillPackage],
        list[CatalogDiagnostic],
    ]:
        try:
            entries = self.github.list_directory(resolved, workflow.skills_path)
        except GitHubError as exc:
            if "not found" in str(exc).lower():
                return {}, []
            raise
        skill_directories = [item for item in entries if item.get("type") == "dir"]
        if len(skill_directories) > MAX_SKILLS_PER_WORKFLOW:
            raise ValidationError(
                f"{workflow.key}: more than {MAX_SKILLS_PER_WORKFLOW} skills"
            )
        source = _workflow_source(workflow, resolved, source_kind=source_kind)
        packages: dict[tuple[str, str], WorkflowSkillPackage] = {}
        diagnostics: list[CatalogDiagnostic] = []
        for directory in skill_directories:
            name = str(directory.get("name", ""))
            root = f"{workflow.skills_path.rstrip('/')}/{name}"
            try:
                files = self._skill_files(resolved, root)
                summary, validated = validate_skill(
                    workflow.key,
                    name,
                    files,
                    self.package_url(workflow.key, name),
                    source_kind=source_kind,
                )
                packages[(workflow.key, name)] = WorkflowSkillPackage(
                    source=source,
                    skill=summary,
                    files=validated,
                )
            except (CatalogError, UnicodeError, ValueError) as exc:
                diagnostics.append(
                    CatalogDiagnostic(
                        level="error",
                        code="invalid-skill",
                        message=str(exc),
                        workflow_key=workflow.key,
                        skill_name=name,
                    )
                )
        return packages, diagnostics

    def _skill_files(
        self, resolved: ResolvedRepository, root: str
    ) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        for item in self.github.list_directory(resolved, root):
            item_type = item.get("type")
            name = str(item.get("name", ""))
            if item_type == "file" and name == "SKILL.md":
                files["SKILL.md"] = self.github.read_file(resolved, f"{root}/SKILL.md")
            elif item_type == "dir" and name == "references":
                reference_root = f"{root}/references"
                for reference in self.github.list_directory(resolved, reference_root):
                    if reference.get("type") != "file":
                        raise ValidationError(
                            f"{root}: references must contain regular files"
                        )
                    reference_name = str(reference.get("name", ""))
                    files[f"references/{reference_name}"] = self.github.read_file(
                        resolved, f"{reference_root}/{reference_name}"
                    )
            elif name not in {"agents"}:
                raise ValidationError(f"{root}: unsupported skill entry {name}")
        return files

    def _remember_key(self, cache_key: str) -> None:
        state = self.cache.read_json("state") or {"workflow_cache_keys": []}
        keys = {
            item for item in state.get("workflow_cache_keys", []) if isinstance(item, str)
        }
        keys.add(cache_key)
        self.cache.write_json("state", {"workflow_cache_keys": sorted(keys)})


def _consumer(value: str) -> str:
    normalized = value.strip().lower()
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
    if not normalized or any(character not in allowed for character in normalized):
        raise ValueError("consumer must contain lowercase letters, digits, or hyphens")
    return normalized


def _workflow_source(
    workflow: ConfiguredWorkflow,
    resolved: ResolvedRepository,
    *,
    source_kind: Literal["workflow", "application"],
) -> WorkflowSource:
    location = resolved.location
    return WorkflowSource(
        workflow_key=workflow.key,
        repository_url=workflow.repository_url,
        owner=location.owner,
        repository=location.repository,
        configured_ref=location.configured_ref,
        resolved_commit=resolved.commit_sha,
        skills_path=workflow.skills_path,
        descriptor_path=location.descriptor_path,
        ref_kind=resolved.ref_kind,
        ui_modes=workflow.ui_modes,
        source_kind=source_kind,
        source_key=workflow.key,
    )


def _source_key(source: WorkflowSource) -> str:
    return source.source_key or source.workflow_key


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _package_dict(package: WorkflowSkillPackage) -> dict[str, Any]:
    return package.to_dict()


def _cached_packages(
    value: dict[str, Any] | None,
) -> dict[tuple[str, str], WorkflowSkillPackage]:
    if not value or not isinstance(value.get("packages"), list):
        return {}
    packages: dict[tuple[str, str], WorkflowSkillPackage] = {}
    try:
        for raw in value["packages"]:
            source_raw = raw["source"]
            skill_raw = raw["skill"]
            match_raw = skill_raw.get("match", {})
            source = WorkflowSource(
                **{
                    **source_raw,
                    "ui_modes": tuple(source_raw.get("ui_modes", ())),
                }
            )
            skill = WorkflowSkillSummary(
                **{
                    **skill_raw,
                    "consumers": tuple(skill_raw.get("consumers", ())),
                    "match": SkillMatchRules(
                        extensions=tuple(match_raw.get("extensions", ())),
                        filename_globs=tuple(match_raw.get("filename_globs", ())),
                        required_tables=tuple(match_raw.get("required_tables", ())),
                        auto_activate=bool(match_raw.get("auto_activate", False)),
                    ),
                }
            )
            files = tuple(SkillFile(**item) for item in raw["files"])
            package = WorkflowSkillPackage(source=source, skill=skill, files=files)
            packages[(_source_key(source), skill.name)] = package
    except (KeyError, TypeError, ValueError):
        return {}
    return packages


def _cache_is_current(
    cached: dict[str, Any] | None,
    source: WorkflowSource,
) -> bool:
    if not cached:
        return False
    if source.ref_kind in {"tag", "commit"}:
        return True
    checked_at = cached.get("checked_at")
    if not isinstance(checked_at, str):
        return False
    try:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(timezone.utc) - checked < timedelta(hours=1)


def _cached_source(
    cached: dict[str, Any] | None,
    packages: dict[tuple[str, str], WorkflowSkillPackage],
) -> WorkflowSource | None:
    if cached and isinstance(cached.get("source"), dict):
        try:
            raw = cached["source"]
            return WorkflowSource(
                **{
                    **raw,
                    "ui_modes": tuple(raw.get("ui_modes", ())),
                }
            )
        except (TypeError, ValueError):
            return None
    if packages:
        return next(iter(packages.values())).source
    return None
