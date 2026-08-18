from pathlib import Path

from VeraGridEngine.IO.dgs.dynamic_models.dgs_elmsvs_runtime_adapter import (
    build_dgs_elmsvs_rms_runtime_template,
    is_dgs_elmsvs_slot_contract,
)
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import Expr, Var
from VeraGridEngine.Utils.Symbolic.symbolic_io import duplicate_block
from VeraGridEngine.enumerations import (
    ParamPowerFlowReferenceType,
    VarPowerFlowReferenceType,
)


def build_elmsvs_control_template_for_test(
        qreact_mvar: float,
        qcap_mvar: float,
        qfixcap_mvar: float,
        nxcap: int,
        nfixcap: int,
) -> RmsModelTemplate:
    """Build the smallest complete graphical ElmSvs controller boundary."""

    bsvs: Var = Var(name="bsvs")
    control_block: Block = Block(
        name="ElmSvs controller",
        in_vars=[
            Var(name="u"),
            Var(name="uremote"),
            Var(name="ysvs"),
            Var(name="qreact"),
            Var(name="qcap"),
            Var(name="qfixcap"),
            Var(name="nxcap"),
            Var(name="nfixcap"),
        ],
        out_vars=[bsvs],
        algebraic_vars=[bsvs],
    )
    control_block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmSvs",
            "incoming_signals": ["bsvs"],
            "outgoing_signals": [
                "ysvs",
                "qreact",
                "qcap",
                "qfixcap",
                "nxcap",
                "nfixcap",
            ],
            "svs_qreact_mvar": qreact_mvar,
            "svs_qcap_mvar": qcap_mvar,
            "svs_qfixcap_mvar": qfixcap_mvar,
            "svs_nxcap": nxcap,
            "svs_nfixcap": nfixcap,
        },
    ]
    template: RmsModelTemplate = RmsModelTemplate(name="ElmSvs controller")
    template.block = control_block
    return template


def test_elmsvs_slot_contract_accepts_complete_equipment_boundary() -> None:
    """Recognize a complete PowerFactory static-var-system slot."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmSvs",
            "incoming_signals": ["bsvs"],
            "outgoing_signals": [
                "ysvs",
                "qreact",
                "qcap",
                "qfixcap",
                "nxcap",
                "nfixcap",
            ],
        },
    ]

    assert is_dgs_elmsvs_slot_contract(block=block)


def test_elmsvs_slot_contract_rejects_incomplete_equipment_boundary() -> None:
    """Reject a static-var-system slot without its reactive-power output."""

    block: Block = Block()
    block.__dict__["dgs_direct_slot_interfaces"] = [
        {
            "element_kind": "ElmSvs",
            "incoming_signals": ["bsvs"],
            "outgoing_signals": [
                "ysvs",
                "qcap",
                "qfixcap",
                "nxcap",
                "nfixcap",
            ],
        },
    ]

    assert not is_dgs_elmsvs_slot_contract(block=block)


def test_elmsvs_susceptance_seed_uses_visible_safe_division() -> None:
    """Reconstruct susceptance from Q, Sbase and the squared terminal voltage."""

    adapted_template: RmsModelTemplate | None = (
        build_dgs_elmsvs_rms_runtime_template(
            control_template=build_elmsvs_control_template_for_test(
                qreact_mvar=100.0,
                qcap_mvar=0.0,
                qfixcap_mvar=0.0,
                nxcap=1,
                nfixcap=0,
            ),
        )
    )
    assert adapted_template is not None

    susceptance: Var = adapted_template.block.out_vars[-1]
    seed_expression: Expr = adapted_template.block.init_eqs[susceptance]
    assert adapted_template.block.post_init_seed_eqs[susceptance] is seed_expression

    reactive_power: Var = adapted_template.block.external_mapping[
        VarPowerFlowReferenceType.Q
    ]
    terminal_voltage: Var = adapted_template.block.external_mapping[
        VarPowerFlowReferenceType.Vm
    ]
    system_power_base: Var = adapted_template.block.api_obj_mapping[
        ParamPowerFlowReferenceType.Sbase
    ]
    bindings: dict[int, float] = {
        reactive_power.uid: -0.5,
        terminal_voltage.uid: 2.0,
        system_power_base.uid: 100.0,
    }

    assert seed_expression.eval_uid(bindings) == -12.5
    bindings[terminal_voltage.uid] = 0.0
    assert seed_expression.eval_uid(bindings) == -50.0e6

    duplicated_block: Block = duplicate_block(
        block=adapted_template.block,
        var_factory=VarFactory(),
    )
    duplicated_susceptance: Var = duplicated_block.out_vars[-1]
    duplicated_seed: Expr = duplicated_block.post_init_seed_eqs[
        duplicated_susceptance
    ]
    assert str(duplicated_seed) == str(seed_expression)


def test_elmsvs_adapter_preserves_equipment_values_from_real_dgs() -> None:
    """Carry the physical SVC constants from a tracked DGS into the wrapper."""

    dgs_path: Path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "grids"
        / "test_ieee14_svs.dgs"
    )
    dgs_circuit: DgsCircuit = DgsCircuit()
    dgs_circuit.parse_dgs(path=str(dgs_path))
    source_svs = next(
        svs
        for svs in dgs_circuit.elmsvss
        if svs.loc_name == "SVS_Droop"
    )

    adapted_template: RmsModelTemplate | None = (
        build_dgs_elmsvs_rms_runtime_template(
            control_template=build_elmsvs_control_template_for_test(
                qreact_mvar=source_svs.tcrmax,
                qcap_mvar=source_svs.qmin,
                qfixcap_mvar=source_svs.Qfixcap,
                nxcap=source_svs.nxcap,
                nfixcap=source_svs.nfixcap,
            ),
        )
    )
    assert adapted_template is not None

    parameter_values: dict[str, float] = {
        parameter.name: constant.value
        for parameter, constant in adapted_template.block.parameters.items()
    }
    assert parameter_values["qreact"] == 10.0
    assert parameter_values["qcap"] == -20.0
    assert parameter_values["qfixcap"] == 0.0
    assert parameter_values["nxcap"] == 2.0
    assert parameter_values["nfixcap"] == 0.0
