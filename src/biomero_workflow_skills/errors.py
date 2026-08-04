"""Catalog exceptions."""


class CatalogError(RuntimeError):
    """Base error for catalog operations."""


class ConfigurationError(CatalogError):
    """The workflow configuration is unavailable or invalid."""


class GitHubError(CatalogError):
    """GitHub could not provide a configured workflow resource."""


class TransientGitHubError(GitHubError):
    """GitHub failed temporarily, so an unchanged cached package may be used."""


class PermanentGitHubError(GitHubError):
    """The configured repository or resource is definitively unavailable."""


class ValidationError(CatalogError):
    """A downloaded skill package violates the catalog contract."""


class SkillNotFoundError(CatalogError):
    """A requested workflow skill is not available to the consumer."""
