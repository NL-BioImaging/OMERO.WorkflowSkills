from __future__ import annotations

import pytest

from biomero_workflow_skills import GitHubError
from biomero_workflow_skills.github import parse_repository_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/org/repo", ("org", "repo", ())),
        (
            "https://github.com/org/repo/tree/v1.2.3",
            ("org", "repo", ("v1.2.3",)),
        ),
        (
            "https://github.com/org/repo/tree/main/config.yaml",
            ("org", "repo", ("main", "config.yaml")),
        ),
        (
            "https://github.com/org/repo/blob/main/descriptor.json",
            ("org", "repo", ("main", "descriptor.json")),
        ),
    ],
)
def test_parse_repository_url(url, expected):
    assert parse_repository_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/org/repo",
        "https://evil.example/org/repo",
        "https://github.com/org",
        "https://github.com/org/repo/issues",
        "https://github.com/org/repo/tree/../secret",
    ],
)
def test_rejects_unsafe_repository_urls(url):
    with pytest.raises(GitHubError):
        parse_repository_url(url)

