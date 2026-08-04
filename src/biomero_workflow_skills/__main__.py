"""Inspect the configured catalog from the command line."""

from __future__ import annotations

import argparse
import json

from .catalog import WorkflowSkillCatalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer", default="omero-analysis")
    parser.add_argument("--config")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    catalog = WorkflowSkillCatalog(config_path=args.config)
    if args.refresh:
        catalog.refresh()
    print(json.dumps(catalog.get_catalog(args.consumer).to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
