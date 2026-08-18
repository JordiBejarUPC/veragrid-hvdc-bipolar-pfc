from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmvsc_runtime_adapter import (
    is_dgs_elmvsc_slot_contract,
    is_dgs_elmvscmono_slot_contract,
)
from VeraGridEngine.Utils.Symbolic.block import Block


def test_elmvsc_slot_contract_accepts_complete_converter_boundary() -> None:
    """Recognize a complete PowerFactory MMC converter slot."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmVsc",
            "incoming_signals": ["block", "Pmr", "Pmi", "mdc"],
            "outgoing_signals": ["idc", "Ucap"],
        },
    ]

    assert is_dgs_elmvsc_slot_contract(block=block)


def test_elmvsc_slot_contract_rejects_incomplete_converter_boundary() -> None:
    """Reject an MMC converter slot without its DC modulation input."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmVsc",
            "incoming_signals": ["block", "Pmr", "Pmi"],
            "outgoing_signals": ["idc", "Ucap"],
        },
    ]

    assert not is_dgs_elmvsc_slot_contract(block=block)


def test_elmvscmono_slot_contract_accepts_complete_bridge_boundary() -> None:
    """Recognize a complete PowerFactory monopolar converter slot."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmVscmono",
            "incoming_signals": ["Pmd", "Pmq", "cosref", "sinref"],
            "outgoing_signals": ["id", "iq", "uDC"],
        },
    ]

    assert is_dgs_elmvscmono_slot_contract(block=block)


def test_elmvscmono_slot_contract_rejects_incomplete_bridge_boundary() -> None:
    """Reject a monopolar converter slot without its sine reference."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmVscmono",
            "incoming_signals": ["Pmd", "Pmq", "cosref"],
            "outgoing_signals": ["id", "iq", "uDC"],
        },
    ]

    assert not is_dgs_elmvscmono_slot_contract(block=block)
