"""Validate downloaded Agent Skills and extract BIOMERO metadata."""

from __future__ import annotations

import hashlib
import mimetypes
import re
from collections.abc import Mapping
from pathlib import PurePosixPath

import yaml

from .errors import ValidationError
from .models import SkillFile, SkillMatchRules, WorkflowSkillSummary

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SKILLS_PER_WORKFLOW = 32
MAX_FILES_PER_SKILL = 128
MAX_FILE_BYTES = 1024 * 1024
MAX_PACKAGE_BYTES = 5 * 1024 * 1024
ALLOWED_REFERENCE_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}


def validate_skill(
    workflow_key: str,
    directory_name: str,
    files: Mapping[str, bytes],
    package_url: str,
) -> tuple[WorkflowSkillSummary, tuple[SkillFile, ...]]:
    if len(files) > MAX_FILES_PER_SKILL:
        raise ValidationError(f"{directory_name}: too many files")
    if "SKILL.md" not in files:
        raise ValidationError(f"{directory_name}: SKILL.md is required")
    total = sum(len(content) for content in files.values())
    if total > MAX_PACKAGE_BYTES:
        raise ValidationError(f"{directory_name}: package exceeds {MAX_PACKAGE_BYTES} bytes")

    validated_files: list[SkillFile] = []
    for path, content in sorted(files.items()):
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts or "\\" in path:
            raise ValidationError(f"{directory_name}: unsafe path {path}")
        if path != "SKILL.md":
            if len(pure.parts) != 2 or pure.parts[0] != "references":
                raise ValidationError(f"{directory_name}: only text references are supported")
            if pure.suffix.lower() not in ALLOWED_REFERENCE_SUFFIXES:
                raise ValidationError(f"{directory_name}: unsupported reference type {pure.suffix}")
        if len(content) > MAX_FILE_BYTES:
            raise ValidationError(f"{directory_name}: {path} exceeds {MAX_FILE_BYTES} bytes")
        if b"\x00" in content:
            raise ValidationError(f"{directory_name}: {path} is not text")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationError(f"{directory_name}: {path} is not UTF-8") from exc
        media_type = mimetypes.guess_type(path)[0] or "text/plain"
        validated_files.append(
            SkillFile(
                path=path,
                media_type=media_type,
                size=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                content=text,
            )
        )

    skill_text = next(item.content for item in validated_files if item.path == "SKILL.md")
    frontmatter = parse_frontmatter(skill_text)
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        raise ValidationError(f"{directory_name}: invalid skill name")
    if name != directory_name:
        raise ValidationError(f"{directory_name}: directory and skill name differ")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 1024
    ):
        raise ValidationError(f"{directory_name}: invalid description")
    metadata = frontmatter.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValidationError(f"{directory_name}: metadata must be a string map")
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in metadata.items()
    ):
        raise ValidationError(f"{directory_name}: metadata values must be strings")

    consumers = _csv(metadata.get("biomero-consumers", ""))
    purpose = metadata.get("biomero-purpose", "generic").strip() or "generic"
    version = metadata.get("version", "1").strip() or "1"
    match = SkillMatchRules(
        extensions=tuple(
            value.lower()
            for value in _csv(metadata.get("biomero-file-extensions", ""))
        ),
        filename_globs=_csv(metadata.get("biomero-filename-globs", "")),
        required_tables=_csv(metadata.get("biomero-required-tables", "")),
        auto_activate=metadata.get("biomero-auto-activate", "false").strip().lower() == "true",
    )
    package_hash = hashlib.sha256()
    for item in validated_files:
        package_hash.update(item.path.encode("utf-8"))
        package_hash.update(bytes.fromhex(item.sha256))
    return (
        WorkflowSkillSummary(
            workflow_key=workflow_key,
            name=name,
            description=description.strip(),
            purpose=purpose,
            consumers=consumers,
            version=version,
            sha256=package_hash.hexdigest(),
            package_url=package_url,
            match=match,
        ),
        tuple(validated_files),
    )


def parse_frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        raise ValidationError("SKILL.md must start with YAML frontmatter")
    closing = text.find("\n---", 4)
    if closing < 0:
        raise ValidationError("SKILL.md frontmatter is not closed")
    try:
        value = yaml.safe_load(text[4:closing])
    except yaml.YAMLError as exc:
        raise ValidationError("SKILL.md frontmatter is invalid YAML") from exc
    if not isinstance(value, dict):
        raise ValidationError("SKILL.md frontmatter must be a mapping")
    return value


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())
