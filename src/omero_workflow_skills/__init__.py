"""Temporary import compatibility for biomero_workflow_skills."""

import sys
from importlib import import_module

from biomero_workflow_skills import *  # noqa: F401,F403
from biomero_workflow_skills import __all__ as __all__
from biomero_workflow_skills import __version__ as __version__

for _module in (
    "cache",
    "catalog",
    "config",
    "errors",
    "github",
    "models",
    "validation",
):
    sys.modules[f"{__name__}.{_module}"] = import_module(
        f"biomero_workflow_skills.{_module}"
    )
