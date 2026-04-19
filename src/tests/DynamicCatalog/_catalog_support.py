from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any

from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import PENDING_LOOKUP_TYPE_IDS
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_descriptor_by_typ_id
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_manifest_path
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_templates_dir
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import import_powerfactory_basic_catalog_module
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import load_powerfactory_basic_catalog_manifest


def build_manifest_path() -> Path:
    """
    Return the shipped PowerFactory basic catalog manifest path.
    """

    return get_powerfactory_basic_catalog_manifest_path()


def build_templates_dir() -> Path:
    """
    Return the directory with shipped standalone template modules.
    """

    return get_powerfactory_basic_catalog_templates_dir()


def build_pending_lookup_type_ids() -> list[str]:
    """
    Return the frozen typ_id list for the unsupported lookup subset.
    """

    return sorted(PENDING_LOOKUP_TYPE_IDS, key=int)


def load_manifest() -> dict[str, Any]:
    """
    Load the shipped PowerFactory basic catalog manifest.
    """

    return load_powerfactory_basic_catalog_manifest()


def manifest_entries() -> list[dict[str, Any]]:
    """
    Return manifest rows exactly as stored in the shipped snapshot.
    """

    raw_entries: Any = load_manifest()["entries"]
    if isinstance(raw_entries, list):
        return list(raw_entries)
    else:
        raise TypeError("Manifest entries are not stored as a list")


def find_template_path(typ_id: str) -> Path:
    """
    Resolve the shipped standalone module path for one typ_id.
    """

    descriptor = get_powerfactory_basic_catalog_descriptor_by_typ_id()[typ_id]
    return build_templates_dir() / descriptor.module_filename


def import_template_module(typ_id: str) -> ModuleType:
    """
    Import one shipped standalone template module by typ_id.
    """

    return import_powerfactory_basic_catalog_module(typ_id)
