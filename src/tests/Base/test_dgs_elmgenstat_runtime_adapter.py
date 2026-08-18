from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmgenstat_runtime_adapter import (
    is_dgs_elmgenstat_slot_contract,
)
from VeraGridEngine.Utils.Symbolic.block import Block


def test_elmgenstat_slot_contract_accepts_current_reference_pair() -> None:
    """Recognize a complete PowerFactory static-generator slot."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmGenstat",
            "incoming_signals": ["id_ref;iq_ref"],
        },
    ]

    assert is_dgs_elmgenstat_slot_contract(block=block)


def test_elmgenstat_slot_contract_rejects_incomplete_reference_pair() -> None:
    """Reject a static-generator slot without its reactive-current input."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmGenstat",
            "incoming_signals": ["id_ref"],
        },
    ]

    assert not is_dgs_elmgenstat_slot_contract(block=block)
