# Workflow skill authoring and deployment

## Repository layout

Store each portable Agent Skill directly under `_agents/skills`:

```text
_agents/skills/
  analyze-example-measurements/
    SKILL.md
    references/
      REFERENCE.md
```

The directory and frontmatter `name` must match. Detailed schema material
belongs in `references/`; keep `SKILL.md` concise.

## BIOMERO metadata

Agent Skills metadata values are strings:

```yaml
---
name: analyze-example-measurements
description: Analyze Example Workflow measurement databases. Use for its DuckDB or SQLite outputs.
metadata:
  version: "1"
  biomero-purpose: attachment-analysis
  biomero-consumers: "omero-analysis-chat,omero-jupyterlite"
  biomero-auto-activate: "true"
  biomero-file-extensions: ".duckdb,.sqlite"
  biomero-filename-globs: "*measurements*.duckdb,*measurements*.sqlite"
  biomero-required-tables: "schema_info,measurement_runs"
---
```

`biomero-consumers` is mandatory for distribution. A future workflow-operation
skill can target only `omero-biomero`.

## Revision and configuration

The catalog uses the exact revision in `<workflow>_repo`; it never follows a
different "latest" release. The default path is `_agents/skills`. Set
`<workflow>_skills_path` next to `<workflow>_repo` for a nonstandard location.

A workflow missing a skill directory is valid and contributes no skills. When
an administrator removes a workflow, changes its revision, or removes a skill
in a new release, consumers receive a new authoritative snapshot and discard
their managed copy.

## Security and privacy

Only GitHub repositories configured by the BIOMERO administrator are read.
Downloaded packages may contain `SKILL.md` and UTF-8 text files immediately
under `references/`. Scripts, executable content, symlinks, binary assets,
unsafe paths, invalid frontmatter, and oversized packages are rejected.

The optional `BIOMERO_GITHUB_TOKEN` is read only by the server-side catalog and
is never returned in catalog data. Browser clients receive validated skill
instructions, hashes, and source provenance. They never contact GitHub.

## Caching

Validated data are written atomically below
`~/.cache/omero-workflow-skills`. Processes coordinate through a lock file.
Configured branches are revalidated after one hour. Immutable GitHub tags are
reused by resolved commit. On a transient failure, cached content is marked
stale only when it belongs to the same configured repository and ref.

## Consumer adapters

This distribution is deliberately not listed in `omero.web.apps`. An installed
consumer exposes authenticated catalog and package routes and an admin-only
refresh route. Multiple consumers use the same validated filesystem cache.

The first consumer installs the companion wheel from its offline wheelhouse.
Installing another consumer retains a compatible `>=0.1,<0.2` version.
Removing a consumer must check installed distribution requirements first; the
catalog is removed only when no installed consumer still requires it.

No GitHub token, unvalidated source, or cache internals are returned to a
browser. Consumers add their own execution-environment and tool instructions;
portable workflow knowledge must not contain plugin-specific browser paths.

## Release workflow

Pin workflow URLs to a release tag or commit for reproducibility. A branch is
suitable during development but is revalidated hourly. CI tests Python
3.10–3.12 and verifies each wheel. A `v*` tag creates GitHub release artifacts
and uses trusted publishing for PyPI after its environment is configured.

Publish portable skills in the workflow repository release before updating
BIOMERO's workflow URL and before removing a legacy bundled skill from a
consumer. This ordering prevents a temporary loss of guidance.

## Troubleshooting

- `no-skills` means the configured revision has no valid skills for that
  consumer.
- `stale` means GitHub failed transiently and the unchanged cached source is
  being served.
- `error` means the configured source is invalid or unavailable and stale data
  was intentionally not reused.
- Use a consumer's administrator refresh action after correcting a repository
  or configuration. `status()` reports the effective paths, content hash,
  cache path, and latest catalog.
