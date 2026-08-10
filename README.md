# BIOMERO.WorkflowSkills

`biomero-workflow-skills` is a small, framework-neutral catalog for Agent
Plugins and Agent Skills stored with BIOMERO workflow repositories. It resolves
exact GitHub revisions, validates each package locally, and exposes typed
catalog data to OMERO plugins.

Agent Plugins 1.0.0 are discovered from `<workflow>_plugin_path` (default `.`).
The package uses its bundled schema without network access, reads only immediate
`skills/*/SKILL.md` directories, and materializes only bounded UTF-8 skill files
and text references. Repositories without `plugin.json` retain the 0.x
`_agents/skills` fallback. A present but invalid manifest is reported as an
error.

It is an optional provider for
[OMERO.Analysis](https://github.com/NL-BioImaging/OMERO.Analysis).
It is not an OMERO.web application and does not modify or import
`OMERO.biomero`.

## Basic use

```python
from biomero_workflow_skills import WorkflowSkillCatalog

catalog = WorkflowSkillCatalog()
available = catalog.get_catalog("omero-analysis")
package = catalog.get_package(
    "cisegmentation",
    "analyze-cisegmentation-measurements",
)
```

For stateless adapters, `get_package(..., consumer="omero-analysis")` is
also supported and performs the consumer-filtered catalog lookup first.
Only `attachment-analysis` skills explicitly declaring `omero-analysis` are
returned. `[APPLICATIONS]` is intentionally ignored; applications such as
BIOMERO.ZarrViewer publish their own skills.

The package reads `BIOMERO_WORKFLOW_SKILLS_CONFIG` when set. Otherwise it merges
the existing files at `/etc/slurm-config.ini`, `/OMERO/slurm-config.ini`, and
`~/slurm-config.ini`, matching BIOMERO's configuration precedence.

Public GitHub repositories need no credential. Set `BIOMERO_GITHUB_TOKEN` to a
read-only token for private repositories or a larger API allowance.

The cache follows configured release pins: tags and commits are immutable,
while branches are revalidated hourly with GitHub ETags. Removing a workflow
or skill removes it from the next authoritative response; stale content is
used only for a transient failure of the same unchanged source.

See [Workflow skill authoring and deployment](docs/workflow-skills.md) for the
repository contract, security model, caching, and plugin integration.
