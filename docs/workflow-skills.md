# Workflow skill authoring and deployment

## Contents

- [Choose the skill type](#choose-the-skill-type)
- [Repository layout](#repository-layout)
- [Attachment-analysis skill](#attachment-analysis-skill)
- [Workflow-operation skill](#workflow-operation-skill)
- [Shared metadata rules](#shared-metadata-rules)
- [Revision and configuration](#revision-and-configuration)
- [Security and privacy](#security-and-privacy)
- [Caching](#caching)
- [Consumer adapters](#consumer-adapters)
- [Release workflow](#release-workflow)
- [Troubleshooting](#troubleshooting)

## Choose the skill type

Workflow repositories can publish two complementary kinds of skills:

| Skill type | Purpose | Current consumer | Activation |
| --- | --- | --- | --- |
| Attachment analysis | Explain and analyze workflow-generated measurement files | `omero-analysis-chat`, `omero-jupyterlite` | May activate automatically when files or schemas match |
| Workflow operation | Help select, configure, launch, monitor, and explain a BIOMERO workflow | `omero-biomero` | Must be initiated explicitly by the user |

Keep these as separate skills when a repository needs both. Analysis clients
must not receive workflow-launch instructions, and a workflow-operation skill
should not duplicate a large measurement schema.

## Repository layout

Store each portable Agent Skill directly under `_agents/skills`:

```text
_agents/skills/
  analyze-example-measurements/
    SKILL.md
    references/
      REFERENCE.md
  use-example-workflow/
    SKILL.md
    references/
      PARAMETERS.md
      OUTPUTS.md
      TROUBLESHOOTING.md
```

The directory and frontmatter `name` must match. Detailed schema material
belongs in `references/`; keep `SKILL.md` concise.

Only `SKILL.md` and UTF-8 `.md`, `.txt`, `.json`, `.yaml`, or `.yml`
references are distributed. Do not add scripts, executables, binaries,
symlinks, example datasets, or secrets to a skill package.

## Attachment-analysis skill

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

Use progressive references for detailed schemas, relationships, and analysis
examples. The main instructions should tell the consumer which reference to
load and under what condition.

## Workflow-operation skill

A workflow-operation skill teaches an AI-enabled BIOMERO consumer how to use
one configured workflow safely. It documents selection requirements,
parameters, outputs, validation, monitoring, and recovery. It does not execute
code from the GitHub repository. Actual operations must go through typed,
authenticated tools supplied by the consumer.

### 1. Create the folder

Use a short, verb-led name:

```text
_agents/skills/use-example-workflow/
  SKILL.md
  references/
    PARAMETERS.md
    OUTPUTS.md
    TROUBLESHOOTING.md
```

Use lowercase letters, digits, and hyphens. The folder name and frontmatter
`name` must be identical.

### 2. Add workflow-operation metadata

All metadata values must be quoted strings:

```yaml
---
name: use-example-workflow
description: Configure, launch, monitor, and explain the Example BIOMERO workflow. Use when a user explicitly wants to run Example processing on an authorized OMERO image, dataset, plate, or screen.
metadata:
  version: "1"
  biomero-purpose: workflow-operation
  biomero-consumers: "omero-biomero"
  biomero-auto-activate: "false"
---
```

Required choices for this skill type:

- Set `biomero-purpose` to `workflow-operation`.
- Set `biomero-consumers` to `omero-biomero`. Current browser-analysis
  consumers intentionally filter it out.
- Set `biomero-auto-activate` to `false`. Selecting an OMERO object must never
  launch or prepare a workflow automatically.
- Make the description name the workflow and the supported user intentions.
  Do not put triggering information only in the body.
- Increment `metadata.version` when the instructions or references change.

The configured `<workflow>_repo` entry already supplies the workflow key,
repository, release ref, resolved commit, and normal/plate classification.
Do not repeat environment-specific server addresses, credentials, partitions,
or OMERO IDs in the skill.

### 3. Write the operational procedure

Keep `SKILL.md` focused on the safe decision sequence. A recommended template
is:

```markdown
# Use Example Workflow

1. Confirm that the user explicitly asked to run the Example workflow.
2. Inspect the active OMERO user, group, selection, and available workflow
   tools. Never invent object IDs or tool capabilities.
3. Read [PARAMETERS.md](references/PARAMETERS.md) before proposing settings.
4. Validate the selected object type, required inputs, parameter types,
   ranges, mutually exclusive settings, and expected resource class.
5. Present the resolved inputs, parameters, outputs, and side effects.
6. Obtain explicit confirmation immediately before submission.
7. Submit exactly once through the consumer's authenticated workflow tool and
   retain its returned job or run ID.
8. Monitor that run ID. Do not resubmit merely because status is delayed.
9. Read [OUTPUTS.md](references/OUTPUTS.md) to explain completion and locate
   results. Read [TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) only after
   a validation or execution failure.
10. Record the workflow key, configured ref, resolved commit, parameters,
    input object, run ID, timestamps, status, and output objects as provenance.
```

The consumer, not the portable skill, decides the exact tool names and
confirmation UI. Phrase instructions in terms of capabilities such as
“inspect selection”, “validate parameters”, “submit workflow”, and “monitor
run”; do not hard-code a plugin's internal function names.

### 4. Document parameters

`references/PARAMETERS.md` should be the authoritative human-readable
parameter contract. For every parameter, document:

- descriptor/command name and user-facing label;
- type, units, required/default status, and allowed values or range;
- which OMERO object or uploaded value supplies it;
- dependencies, exclusions, and conditional visibility;
- whether it affects runtime, memory, GPU use, or output size;
- a conservative example.

Prefer a compact table followed by conditional rules:

```markdown
# Parameters

| Name | Type | Required | Default | Constraints | Meaning |
| --- | --- | --- | --- | --- | --- |
| `diameter` | number | no | `30` | `1..500`, pixels | Expected object diameter |
| `use_gpu` | boolean | no | `false` | GPU queue must be available | Enable GPU execution |

## Conditional rules

- Require `diameter` when automatic scale detection is disabled.
- Reject `use_gpu=true` when the consumer reports no compatible GPU resource.
```

Keep this reference aligned with the workflow descriptor used by the same
release. The skill may explain and constrain descriptor parameters, but must
not silently introduce parameters that the released workflow does not accept.

### 5. Document outputs and completion

`references/OUTPUTS.md` should describe:

- expected OMERO object types and FileAnnotations;
- filenames or namespaces when stable;
- which source object receives each result;
- partial/intermediate versus final outputs;
- success criteria and useful quality checks;
- how downstream measurement or analysis skills relate to the outputs.

Do not promise that an output exists merely because the scheduler job ended.
The operational procedure should verify the consumer-reported workflow status
and expected OMERO results.

### 6. Document failures without exposing infrastructure

`references/TROUBLESHOOTING.md` should map stable, user-actionable failure
classes to next steps: invalid selection, missing input, invalid parameter,
insufficient permission, unavailable resource, timeout, workflow failure, and
missing output. Tell the consumer when retrying is safe.

Do not include tokens, usernames, internal hostnames, Slurm credentials,
private paths, or instructions to bypass permissions. Infrastructure-specific
diagnostics remain deployment documentation, not portable skill content.

### 7. Apply safety boundaries

A workflow-operation skill must instruct the consumer to:

- preserve the active OMERO group and permission context;
- perform read-only discovery before proposing a run;
- show resolved inputs and parameters before submission;
- require explicit user confirmation for submission, cancellation, deletion,
  overwrite, or attachment changes;
- treat a returned run ID as the identity for monitoring and cancellation;
- avoid duplicate submission after timeouts or transient UI errors;
- never change BIOMERO configuration, GitHub release pins, or server settings;
- never claim success without checking run status and expected outputs.

The catalog distributes instructions only. Installing a skill does not grant
OMERO permissions, workflow permissions, GitHub write access, or server shell
access.

### 8. Validate and test the skill

Before releasing:

1. Check that the directory and `name` match and all metadata values are
   strings.
2. Confirm the skill is visible only to `omero-biomero`.
3. Compare every documented parameter and output with the release descriptor.
4. Test a valid run, validation failure, permission failure, scheduler
   failure, delayed status, cancellation, and missing-output case.
5. Confirm that selecting an object alone never submits a workflow.
6. Confirm that a retry does not duplicate an existing run.
7. Verify the recorded provenance contains the workflow release commit and
   returned run ID.

`omero-biomero` support is a future consumer integration. Publishing this
skill contract now makes workflow releases ready for that integration, but
does not add workflow-operation tools to OMERO.biomero by itself.

## Shared metadata rules

`biomero-consumers` is mandatory for distribution. Consumers receive only
skills that explicitly name them. Unknown metadata strings may be reserved
for future catalog versions, but authors should not depend on them until they
are documented here.

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

For a workflow-operation skill, release in this order:

1. update the workflow descriptor and implementation;
2. update `PARAMETERS.md`, `OUTPUTS.md`, and operational instructions;
3. test the skill against that exact workflow revision;
4. tag the workflow repository release;
5. update the administrator's `<workflow>_repo` pin;
6. refresh the shared catalog;
7. verify the resolved commit and skill version before enabling users.

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
