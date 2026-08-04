from omero_workflow_skills.catalog import WorkflowSkillCatalog as LegacyModuleCatalog

from biomero_workflow_skills import WorkflowSkillCatalog as NewCatalog
from biomero_workflow_skills import __version__ as new_version
from omero_workflow_skills import WorkflowSkillCatalog as LegacyCatalog
from omero_workflow_skills import __version__ as legacy_version


def test_legacy_imports_reexport_new_package():
    assert LegacyCatalog is NewCatalog
    assert LegacyModuleCatalog is NewCatalog
    assert legacy_version == new_version == "0.3.0"
