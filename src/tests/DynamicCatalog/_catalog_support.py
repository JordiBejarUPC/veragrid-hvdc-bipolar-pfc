from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Sequence

from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import PowerFactoryBasicTemplateDescriptor
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_pending_powerfactory_basic_catalog_descriptors
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_descriptor_by_key
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_descriptors
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_templates_dir
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import import_powerfactory_basic_catalog_module_by_key


def build_templates_dir() -> Path:
    """
    Return the directory with shipped standalone template modules.

    :returns: Standalone-template directory.
    """

    return get_powerfactory_basic_catalog_templates_dir()


def descriptor_entries() -> Sequence[PowerFactoryBasicTemplateDescriptor]:
    """
    Return every shipped catalog descriptor.

    :returns: Full descriptor tuple.
    """

    return get_powerfactory_basic_catalog_descriptors()


def pending_descriptor_entries() -> Sequence[PowerFactoryBasicTemplateDescriptor]:
    """
    Return the pending catalog descriptors.

    :returns: Pending descriptor tuple.
    """

    return get_pending_powerfactory_basic_catalog_descriptors()


def descriptor_lookup_by_key() -> dict[str, PowerFactoryBasicTemplateDescriptor]:
    """
    Return the descriptor lookup indexed by semantic key.

    :returns: Descriptor lookup by semantic key.
    """

    return get_powerfactory_basic_catalog_descriptor_by_key()


def _resolve_descriptor(template_identifier: str) -> PowerFactoryBasicTemplateDescriptor:
    """
    Resolve one descriptor from either the semantic key or the old numeric fixture id.

    :param template_identifier: Semantic key or numeric fixture identifier.
    :returns: Matching descriptor.
    :raises KeyError: Raised when no descriptor matches.
    """

    descriptor_by_key: dict[str, PowerFactoryBasicTemplateDescriptor] = descriptor_lookup_by_key()
    descriptor: PowerFactoryBasicTemplateDescriptor | None = descriptor_by_key.get(template_identifier, None)

    if descriptor is not None:
        return descriptor
    else:
        pass

    if template_identifier.isdigit():
        prefix: str = f"typ_{template_identifier}__"
        candidate: PowerFactoryBasicTemplateDescriptor
        for candidate in descriptor_entries():
            if candidate.module_name.startswith(prefix):
                return candidate
            else:
                pass
    else:
        pass

    raise KeyError(f"Unknown catalog template identifier '{template_identifier}'")


def find_template_path(template_identifier: str) -> Path:
    """
    Resolve the shipped standalone module path for one catalog template.

    :param template_identifier: Semantic key or numeric fixture identifier.
    :returns: Standalone module path.
    """

    descriptor: PowerFactoryBasicTemplateDescriptor = _resolve_descriptor(template_identifier)
    return build_templates_dir() / descriptor.module_filename


def import_template_module(template_identifier: str) -> ModuleType:
    """
    Import one shipped standalone template module by semantic key.

    :param template_identifier: Semantic key or numeric fixture identifier.
    :returns: Imported standalone module.
    """

    descriptor: PowerFactoryBasicTemplateDescriptor = _resolve_descriptor(template_identifier)
    return import_powerfactory_basic_catalog_module_by_key(descriptor.template_key)
