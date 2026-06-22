from __future__ import annotations

from dataclasses import dataclass

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.fmu_template import FmuTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Templates.BasicBlockCatalog import BasicBlockTemplateDescriptor
from VeraGridEngine.enumerations import BlockType


def _library_leaf_label_sort_key(leaf: "LibraryLeafSpec") -> str:
    """
    Return the case-insensitive sort key for one library leaf.

    :param leaf: Library leaf specification.
    :return: Lower-case label.
    """
    return leaf.label.lower()


def is_supported_library_payload(item_data: object) -> bool:
    """
    Check whether a tree item payload can be dragged into the editor scene.

    :param item_data: Candidate payload object.
    :return: ``True`` when the payload can be materialized in the editor.
    """
    if isinstance(item_data, BlockType):
        return True
    elif isinstance(item_data, BasicBlockTemplateDescriptor):
        return True
    elif isinstance(item_data, (RmsModelTemplate, EmtModelTemplate, FmuTemplate)):
        return True
    elif isinstance(item_data, SignalPairPayload):
        return True
    else:
        return False


@dataclass(frozen=True)
class SignalPairPayload:
    """
    Marker payload for the signal pair tool that creates two connected blocks
    (one input, one output) sharing the same variable.
    """


@dataclass(frozen=True)
class LibraryLeafSpec:
    """
    One draggable leaf entry in the library tree.
    """

    label: str
    payload: object
    search_text: str = ""
