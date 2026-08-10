"""Local Agent Plugins 1.0.0 manifest validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from .errors import ValidationError
from .validation import CAPABILITY_PATTERN, NAME_PATTERN

SCHEMA_ID = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
EXTENSION_NAMESPACE = "nl.bioimaging.biomero"


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    sha256: str
    skills: dict[str, dict[str, Any]]


def safe_plugin_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    if normalized in {"", "."}:
        return ""
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValidationError(f"unsafe plugin path: {value}")
    return pure.as_posix()


def plugin_file_path(plugin_path: str, relative: str) -> str:
    root = safe_plugin_path(plugin_path)
    return f"{root}/{relative}" if root else relative


def validate_plugin_manifest(content: bytes) -> PluginManifest:
    if len(content) > 1024 * 1024 or b"\x00" in content:
        raise ValidationError("plugin.json must be bounded UTF-8 JSON")
    try:
        raw = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("plugin.json is not valid UTF-8 JSON") from exc
    schema = json.loads(
        files("biomero_workflow_skills")
        .joinpath("schemas/plugin.schema.json")
        .read_text(encoding="utf-8")
    )
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda e: list(e.path))
    if errors:
        raise ValidationError(f"invalid Agent Plugin manifest: {errors[0].message}")
    if raw.get("$schema") != SCHEMA_ID:
        raise ValidationError("plugin.json must target Agent Plugins 1.0.0")
    name = raw["name"]
    version = raw.get("version", "")
    if not isinstance(version, str):
        raise ValidationError("plugin version must be a string")
    extensions = raw.get("extensions", {})
    biomero = extensions.get(EXTENSION_NAMESPACE)
    if not isinstance(biomero, dict):
        raise ValidationError(f"plugin.json is missing extensions.{EXTENSION_NAMESPACE}")
    skills = biomero.get("skills")
    if not isinstance(skills, dict):
        raise ValidationError("BIOMERO extension skills must be an object")
    validated: dict[str, dict[str, Any]] = {}
    for skill_name, metadata in skills.items():
        if not isinstance(skill_name, str) or not NAME_PATTERN.fullmatch(skill_name):
            raise ValidationError("BIOMERO extension contains an invalid skill name")
        if not isinstance(metadata, dict):
            raise ValidationError(f"{skill_name}: BIOMERO metadata must be an object")
        validated[skill_name] = _skill_metadata(skill_name, metadata)
    return PluginManifest(
        name=name,
        version=version,
        sha256=hashlib.sha256(content).hexdigest(),
        skills=validated,
    )


def _string_list(skill: str, metadata: dict[str, Any], key: str) -> tuple[str, ...]:
    value = metadata.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValidationError(f"{skill}: {key} must be a string array")
    return tuple(value)


def _skill_metadata(skill: str, metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "purpose", "consumers", "auto_activate", "match", "required_resources",
        "required_capabilities", "preferred_capabilities"
    }
    unknown = set(metadata) - allowed
    if unknown:
        raise ValidationError(f"{skill}: unsupported BIOMERO fields: {', '.join(sorted(unknown))}")
    purpose = metadata.get("purpose", "generic")
    if not isinstance(purpose, str) or not purpose:
        raise ValidationError(f"{skill}: purpose must be a non-empty string")
    auto_activate = metadata.get("auto_activate", False)
    if not isinstance(auto_activate, bool):
        raise ValidationError(f"{skill}: auto_activate must be boolean")
    match = metadata.get("match", {})
    allowed_match = {"extensions", "filename_globs", "required_tables"}
    if not isinstance(match, dict) or set(match) - allowed_match:
        raise ValidationError(f"{skill}: invalid match object")
    result: dict[str, Any] = {
        "purpose": purpose,
        "consumers": _string_list(skill, metadata, "consumers"),
        "auto_activate": auto_activate,
        "match": {
            key: _string_list(skill, match, key)
            for key in ("extensions", "filename_globs", "required_tables")
        },
        "required_resources": _string_list(skill, metadata, "required_resources"),
        "required_capabilities": _string_list(skill, metadata, "required_capabilities"),
        "preferred_capabilities": _string_list(skill, metadata, "preferred_capabilities"),
    }
    capabilities = result["required_capabilities"] + result["preferred_capabilities"]
    if any(not CAPABILITY_PATTERN.fullmatch(value) for value in capabilities):
        raise ValidationError(f"{skill}: invalid capability")
    return result
