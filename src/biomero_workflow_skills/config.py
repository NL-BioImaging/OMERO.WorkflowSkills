"""Read-only BIOMERO workflow configuration discovery."""

from __future__ import annotations

import configparser
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError

DEFAULT_CONFIG_PATHS = (
    Path("/etc/slurm-config.ini"),
    Path("/OMERO/slurm-config.ini"),
    Path("~/slurm-config.ini"),
)


@dataclass(frozen=True)
class ConfiguredWorkflow:
    key: str
    repository_url: str
    skills_path: str
    ui_modes: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowConfiguration:
    paths: tuple[str, ...]
    content_hash: str
    workflows: tuple[ConfiguredWorkflow, ...]


def _list_setting(parser: configparser.ConfigParser, key: str) -> set[str]:
    if not parser.has_section("UI"):
        return set()
    raw = parser.get("UI", key, fallback="").strip()
    if not raw:
        return set()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        value = [item.strip() for item in raw.split(",")]
    if not isinstance(value, list):
        return set()
    return {str(item).strip().lower() for item in value if str(item).strip()}


def _candidate_paths(explicit: str | os.PathLike[str] | None) -> tuple[Path, ...]:
    if explicit is not None:
        return (Path(explicit).expanduser(),)
    environment = os.environ.get("BIOMERO_WORKFLOW_SKILLS_CONFIG", "").strip()
    if environment:
        return (Path(environment).expanduser(),)
    return tuple(path.expanduser() for path in DEFAULT_CONFIG_PATHS)


def load_configuration(
    config_path: str | os.PathLike[str] | None = None,
) -> WorkflowConfiguration:
    candidates = _candidate_paths(config_path)
    existing = tuple(path.resolve() for path in candidates if path.is_file())
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    if existing:
        parser.read([str(path) for path in existing], encoding="utf-8")

    merged: dict[str, str] = {}
    if parser.has_section("MODELS"):
        merged.update(dict(parser.items("MODELS")))
    if parser.has_section("WORKFLOWS"):
        merged.update(dict(parser.items("WORKFLOWS")))

    plate = _list_setting(parser, "plate_workflows")
    zarr = _list_setting(parser, "zarr_workflows")
    workflows: list[ConfiguredWorkflow] = []
    for repo_key, repo_url in sorted(merged.items()):
        if not repo_key.endswith("_repo") or not repo_url.strip():
            continue
        key = repo_key[: -len("_repo")]
        modes: list[str] = []
        if key.lower() in plate:
            modes.append("plate")
        if key.lower() in zarr:
            modes.append("zarr")
        if not modes:
            modes.append("standard")
        skills_path = merged.get(f"{key}_skills_path", "_agents/skills").strip()
        workflows.append(
            ConfiguredWorkflow(
                key=key,
                repository_url=repo_url.strip(),
                skills_path=skills_path or "_agents/skills",
                ui_modes=tuple(modes),
            )
        )

    digest = hashlib.sha256()
    for path in existing:
        digest.update(str(path).encode("utf-8"))
        digest.update(str(path.stat().st_mtime_ns).encode("ascii"))
        digest.update(path.read_bytes())
    if not existing:
        digest.update(b"<no-configuration>")
    return WorkflowConfiguration(
        paths=tuple(str(path) for path in existing),
        content_hash=digest.hexdigest(),
        workflows=tuple(workflows),
    )


def require_configuration(
    config_path: str | os.PathLike[str] | None = None,
) -> WorkflowConfiguration:
    configuration = load_configuration(config_path)
    if not configuration.paths:
        raise ConfigurationError("No BIOMERO slurm-config.ini file was found")
    return configuration
