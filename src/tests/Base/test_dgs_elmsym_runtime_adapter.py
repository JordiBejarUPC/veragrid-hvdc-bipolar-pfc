from VeraGridEngine.IO.dynamic_models.dgs_elmsym_runtime_adapter import (
    is_dgs_elmsym_slot_contract,
)
from VeraGridEngine.Utils.Symbolic.block import Block


def test_elmsym_slot_contract_accepts_complete_direct_interface() -> None:
    """Recognize a complete PowerFactory synchronous-machine slot."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "slot_filter": "ElmSym*",
            "incoming_signals": ["pt;ve"],
            "outgoing_signals": [
                "ID;IQ;IFDIEEE;RPOWER;SG;VT;VTD;VTQ;cosn;speed",
            ],
        },
    ]

    assert is_dgs_elmsym_slot_contract(block=block)


def test_elmsym_slot_contract_rejects_incomplete_direct_interface() -> None:
    """Reject a synchronous-machine slot without its excitation input."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "slot_filter": "ElmSym*",
            "incoming_signals": ["pt"],
            "outgoing_signals": [
                "ID;IQ;IFDIEEE;RPOWER;SG;VT;VTD;VTQ;cosn;speed",
            ],
        },
    ]

    assert not is_dgs_elmsym_slot_contract(block=block)
