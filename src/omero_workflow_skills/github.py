"""Restricted GitHub REST client for configured workflow repositories."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .errors import GitHubError, PermanentGitHubError, TransientGitHubError

API_ROOT = "https://api.github.com"
ALLOWED_REPOSITORY_HOST = "github.com"


@dataclass(frozen=True)
class RepositoryLocation:
    owner: str
    repository: str
    configured_ref: str
    descriptor_path: str


@dataclass(frozen=True)
class ResolvedRepository:
    location: RepositoryLocation
    commit_sha: str
    ref_kind: str


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 20.0) -> None:
        self.token = (
            token
            if token is not None
            else os.environ.get("BIOMERO_GITHUB_TOKEN", "")
        )
        self.timeout = timeout
        self._etag_cache: dict[str, tuple[str, Any]] = {}

    def resolve_repository(self, repository_url: str) -> ResolvedRepository:
        owner, repository, tail = parse_repository_url(repository_url)
        candidates = ["/".join(tail[:length]) for length in range(len(tail), 0, -1)]
        if not candidates:
            candidates = ["HEAD"]
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                commit = self._json(
                    f"/repos/{_quote(owner)}/{_quote(repository)}/commits/{_quote(candidate)}"
                )
                sha = str(commit["sha"])
                descriptor = "/".join(tail[len(candidate.split("/")) :])
                kind = self._ref_kind(owner, repository, candidate)
                return ResolvedRepository(
                    RepositoryLocation(owner, repository, candidate, descriptor),
                    sha,
                    kind,
                )
            except (GitHubError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
        raise GitHubError(
            f"Could not resolve configured GitHub revision: {repository_url}"
        ) from last_error

    def list_directory(
        self, source: ResolvedRepository, path: str
    ) -> list[dict[str, Any]]:
        encoded = "/".join(_quote(part) for part in _safe_parts(path))
        value = self._json(
            f"/repos/{_quote(source.location.owner)}/{_quote(source.location.repository)}"
            f"/contents/{encoded}?ref={_quote(source.commit_sha)}"
        )
        if not isinstance(value, list):
            raise GitHubError(f"Expected a GitHub directory at {path}")
        return [item for item in value if isinstance(item, dict)]

    def read_file(self, source: ResolvedRepository, path: str) -> bytes:
        encoded = "/".join(_quote(part) for part in _safe_parts(path))
        value = self._json(
            f"/repos/{_quote(source.location.owner)}/{_quote(source.location.repository)}"
            f"/contents/{encoded}?ref={_quote(source.commit_sha)}"
        )
        if not isinstance(value, dict) or value.get("type") != "file":
            raise GitHubError(f"Expected a regular GitHub file at {path}")
        if value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
            raise GitHubError(f"GitHub did not return base64 content for {path}")
        try:
            return base64.b64decode(value["content"], validate=False)
        except (ValueError, TypeError) as exc:
            raise GitHubError(f"GitHub returned invalid base64 content for {path}") from exc

    def _ref_kind(self, owner: str, repository: str, ref: str) -> str:
        for kind, namespace in (("tag", "tags"), ("branch", "heads")):
            try:
                self._json(
                    f"/repos/{_quote(owner)}/{_quote(repository)}/git/ref/"
                    f"{namespace}/{_quote(ref)}"
                )
                return kind
            except GitHubError:
                continue
        return "commit"

    def _json(self, path: str) -> Any:
        url = f"{API_ROOT}{path}"
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "api.github.com":
            raise GitHubError("Refusing a non-GitHub API request")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "OMERO.WorkflowSkills/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        cached = self._etag_cache.get(url)
        if cached:
            headers["If-None-Match"] = cached[0]
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.geturl().split(":", 1)[0].lower() != "https":
                    raise GitHubError("GitHub redirected to a non-HTTPS URL")
                value = json.loads(response.read().decode("utf-8"))
                etag = response.headers.get("ETag")
                if etag:
                    self._etag_cache[url] = (etag, value)
                return value
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and cached:
                return cached[1]
            if exc.code == 404:
                raise PermanentGitHubError(
                    f"GitHub resource was not found: {path}"
                ) from exc
            if exc.code in {408, 429, 500, 502, 503, 504}:
                raise TransientGitHubError(
                    f"GitHub request failed temporarily with HTTP {exc.code}"
                ) from exc
            raise PermanentGitHubError(
                f"GitHub request failed with HTTP {exc.code}"
            ) from exc
        except (
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            raise TransientGitHubError(f"GitHub request failed: {exc}") from exc


def parse_repository_url(repository_url: str) -> tuple[str, str, tuple[str, ...]]:
    parsed = urllib.parse.urlparse(repository_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != ALLOWED_REPOSITORY_HOST:
        raise GitHubError("Workflow repositories must use https://github.com")
    segments = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if len(segments) < 2:
        raise GitHubError("GitHub repository URL must contain an owner and repository")
    owner = segments[0]
    repository = segments[1].removesuffix(".git")
    tail: tuple[str, ...] = ()
    if len(segments) > 2:
        if segments[2] not in {"tree", "blob"} or len(segments) < 4:
            raise GitHubError("Use a GitHub repository, tree, or descriptor URL")
        tail = tuple(segments[3:])
    for part in (owner, repository, *tail):
        if not part or part in {".", ".."} or "\\" in part or "\x00" in part:
            raise GitHubError("GitHub repository URL contains an unsafe path")
    return owner, repository, tail


def _safe_parts(path: str) -> tuple[str, ...]:
    normalized = path.replace("\\", "/")
    parts = tuple(part for part in normalized.split("/") if part)
    if not parts or any(part in {".", ".."} or "\x00" in part for part in parts):
        raise GitHubError("GitHub content path is unsafe")
    return parts


def _quote(value: str) -> str:
    return urllib.parse.quote(value, safe="")
