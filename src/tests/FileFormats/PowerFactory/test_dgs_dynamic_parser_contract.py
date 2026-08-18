# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import runpy
from pathlib import Path
from types import FunctionType

import pytest

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_to_blocks import (
    UnsupportedDgsExpression,
    build_standalone_blkdef_block_from_parsed_block,
    export_standalone_blkdef_to_python,
    parse_dgs_block_definitions_from_context,
)
from VeraGridEngine.IO.dgs.dynamic_models.dynamic_model_import import (
    add_dynamic_import_selection_requests_to_circuit,
    build_dgs_dynamic_model_import_bundle,
)
from VeraGridEngine.IO.file_open import FileOpen, FileOpenOptions
from VeraGridEngine.IO.dynamic_model_import_types import (
    DynamicModelImportEntryAvailability,
    DynamicModelImportSelectionRequest,
    DynamicModelImportSource,
)
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.enumerations import DeviceType, DynamicSimulationMode, FileType


def _get_dynamic_gain_block_dgs_path() -> Path:
    """Return the versioned DGS fixture containing supported and unsupported blocks."""

    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "DGS"
        / "dynamic_gain_block.dgs"
    )


def _build_exported_block(
        module_members: dict[str, object],
        variable_factory: VarFactory,
        block_name: str,
) -> Block:
    """
    Build one exported block after validating the generated callable and result.

    :param module_members: Runtime namespace produced from the exported module.
    :param variable_factory: Variable factory passed to the generated builder.
    :param block_name: Name assigned to the rebuilt block.
    :return: Validated rebuilt symbolic block.
    """
    block_builder: object = module_members["get_block"]
    if isinstance(block_builder, FunctionType):
        rebuilt_block: object = block_builder(
            vf=variable_factory,
            name=block_name,
        )
        if isinstance(rebuilt_block, Block):
            return rebuilt_block
        else:
            raise AssertionError("The exported DGS get_block function must return a Block")
    else:
        raise AssertionError("The exported DGS module must define a get_block function")


def test_dgs_parser_preserves_dynamic_composite_rows_without_inventing_types() -> None:
    """Preserve exact dynamic rows from a tracked PowerFactory DGS export."""

    dgs_path: Path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "test_ieee14_svs.dgs"
    )
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))

    composite_rows: list[tuple[str, str, str, int, str | None]] = [
        (model.ID, model.loc_name, model.fold_id, model.outserv, model.typ_id)
        for model in circuit.elmcomps
    ]
    assert composite_rows == [
        ("2", "WECC WT Control System Type 4B(1)", "85", 0, None),
        ("3", "WECC WT Control System Type 4B(2)", "85", 0, None),
        ("4", "WECC WT Control System Type 4B(3)", "85", 0, None),
        ("5", "WECC WT Control System Type 4B(4)", "85", 0, None),
        ("6", "WECC WT Control System Type 4B(6)", "85", 0, None),
        ("7", "WECC WT Control System Type 4B(7)", "85", 0, None),
        ("8", "WECC WT Control System Type 4B(8)", "85", 0, None),
        ("9", "WECC WT Control System Type 4B", "85", 0, None),
    ]
    assert len(circuit.elmdsls) == 40
    assert len(circuit.blkdefs) == 0
    assert len(circuit.blkslots) == 0


def test_dgs_parser_preserves_static_var_system_runtime_constants() -> None:
    """Keep the exact SVC values consumed by the dynamic runtime adapter."""

    dgs_path: Path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "grids"
        / "test_ieee14_svs.dgs"
    )
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))

    static_var_system_rows: list[
        tuple[str, str, float, float, int, int, float]
    ] = [
        (
            device.ID,
            device.loc_name,
            device.tcrmax,
            device.qmin,
            device.nxcap,
            device.nfixcap,
            device.Qfixcap,
        )
        for device in circuit.elmsvss
    ]
    assert static_var_system_rows == [
        ("86", "SVS_Droop", 10.0, -20.0, 2, 0, 0.0),
        ("87", "SVS_NoControl", 5.0, -10.0, 1, 0, 0.0),
        ("88", "SVS_Qcontrol", 30.0, -15.0, 2, 1, -5.0),
        ("89", "SVS_Ucontrol", 0.0, 0.0, 0, 0, 0.0),
    ]


def test_dgs_block_definition_builds_one_self_contained_symbolic_block() -> None:
    """Materialize the equation declared by a versioned DGS block definition."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks = parse_dgs_block_definitions_from_context(circuit=circuit)
    parsed_gain_block = parsed_blocks["2"]
    block: Block = build_standalone_blkdef_block_from_parsed_block(
        parsed_block=parsed_gain_block,
    )

    assert parsed_gain_block.unsupported_lines == []
    assert block.name == "Dynamic gain"
    assert [var.name for var in block.in_vars] == ["u"]
    assert [var.name for var in block.out_vars] == ["y"]
    assert len(block.algebraic_eqs) == 1

    parameter_var = next(iter(block.event_dict))
    equation_bindings: dict[str, float] = {
        block.in_vars[0].name: 3.0,
        block.out_vars[0].name: 6.0,
        parameter_var.name: 2.0,
    }
    assert block.algebraic_eqs[0].eval(**equation_bindings) == 0.0


def test_dgs_block_definition_rejects_unsupported_syntax() -> None:
    """Reject a partial template when one DGS equation cannot be represented."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    circuit: DgsCircuit = DgsCircuit()
    circuit.parse_dgs(path=str(dgs_path))
    parsed_blocks = parse_dgs_block_definitions_from_context(circuit=circuit)

    with pytest.raises(
        UnsupportedDgsExpression,
        match="Unsupported dynamic block.*unsupported syntax",
    ):
        build_standalone_blkdef_block_from_parsed_block(
            parsed_block=parsed_blocks["3"],
        )


def test_exported_dgs_block_module_rebuilds_the_source_equation(
        tmp_path: Path,
) -> None:
    """Execute a generated DGS block module without selecting RMS or EMT."""

    output_path: Path = tmp_path / "dynamic_gain_block.py"
    exported_path: Path = export_standalone_blkdef_to_python(
        dgs_path=str(_get_dynamic_gain_block_dgs_path()),
        output_path=str(output_path),
        block_id="2",
    )
    generated_source: str = exported_path.read_text(encoding="utf-8")
    module_members: dict[str, object] = runpy.run_path(str(exported_path))
    rebuilt_block: Block = _build_exported_block(
        module_members=module_members,
        variable_factory=VarFactory(),
        block_name="Rebuilt dynamic gain",
    )

    assert "EmtModelTemplate" not in generated_source
    assert "RmsModelTemplate" not in generated_source
    assert rebuilt_block.name == "Rebuilt dynamic gain"
    assert [var.name for var in rebuilt_block.in_vars] == [
        "u_Rebuilt dynamic gain"
    ]
    assert [var.name for var in rebuilt_block.out_vars] == [
        "y_Rebuilt dynamic gain"
    ]
    assert len(rebuilt_block.algebraic_eqs) == 1

    rebuilt_parameter = next(iter(rebuilt_block.event_dict))
    rebuilt_bindings: dict[str, float] = {
        rebuilt_block.in_vars[0].name: 3.0,
        rebuilt_block.out_vars[0].name: 6.0,
        rebuilt_parameter.name: 2.0,
    }
    assert rebuilt_block.algebraic_eqs[0].eval(**rebuilt_bindings) == 0.0


def test_dgs_dynamic_import_bundle_reports_supported_and_failed_blocks() -> None:
    """Expose valid DGS equations while retaining unsupported blocks as failures."""

    dgs_path: Path = _get_dynamic_gain_block_dgs_path()
    bundle, _logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(dgs_path),
    )
    entries_by_name = {
        entry.get_display_name(): entry
        for entry in bundle.get_entries()
    }

    assert bundle.get_source_tpe() is DynamicModelImportSource.PowerFactoryDgs
    assert set(entries_by_name) == {
        "Dynamic gain",
        "Unsupported dynamic block",
    }
    assert entries_by_name["Dynamic gain"].is_importable()
    assert (
        entries_by_name["Unsupported dynamic block"].get_availability()
        is DynamicModelImportEntryAvailability.Failed
    )


@pytest.mark.parametrize(
    "target_domain",
    [
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    ],
)
def test_dgs_dynamic_import_materializes_the_selected_domain_end_to_end(
        target_domain: DynamicSimulationMode,
) -> None:
    """Preserve one DGS equation through parsing, selection and installation."""

    bundle, bundle_logger = build_dgs_dynamic_model_import_bundle(
        dgs_path=str(_get_dynamic_gain_block_dgs_path()),
    )
    gain_entry = next(
        entry
        for entry in bundle.get_entries()
        if entry.get_display_name() == "Dynamic gain"
    )
    source_block: Block | None = gain_entry.get_source_block()
    circuit: MultiCircuit = MultiCircuit()
    install_logger: Logger = Logger()

    assert bundle_logger.error_count() == 0
    assert source_block is not None

    added_count: int = add_dynamic_import_selection_requests_to_circuit(
        circuit=circuit,
        bundle=bundle,
        selection_requests=[
            DynamicModelImportSelectionRequest(
                entry_key=gain_entry.get_unique_key(),
                target_domain=target_domain,
                device_tpe=DeviceType.NoDevice,
            )
        ],
        logger=install_logger,
    )
    installed_template: RmsModelTemplate | EmtModelTemplate
    if target_domain is DynamicSimulationMode.RMS:
        assert len(circuit.rms_models) == 1
        assert len(circuit.emt_models) == 0
        installed_template = circuit.rms_models[0]
    else:
        assert target_domain is DynamicSimulationMode.EMT
        assert len(circuit.emt_models) == 1
        assert len(circuit.rms_models) == 0
        installed_template = circuit.emt_models[0]

    assert added_count == 1
    assert install_logger.error_count() == 0
    assert installed_template.name == "Dynamic gain"
    assert installed_template.tpe is DeviceType.NoDevice
    assert installed_template.block is not source_block
    assert len(installed_template.block.algebraic_eqs) == 1


@pytest.mark.parametrize(
    "dynamic_simulation_mode",
    [
        DynamicSimulationMode.RMS,
        DynamicSimulationMode.EMT,
    ],
)
def test_file_open_installs_dgs_models_in_the_explicit_dynamic_simulation_mode(
        dynamic_simulation_mode: DynamicSimulationMode,
) -> None:
    """Carry the selected RMS or EMT mode through the public DGS file-open path."""

    file_open: FileOpen = FileOpen(
        file_name=str(_get_dynamic_gain_block_dgs_path()),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
            dgs_dynamic_simulation_mode=dynamic_simulation_mode,
        ),
    )
    circuit: MultiCircuit | None = file_open.open()

    assert circuit is not None

    installed_template: RmsModelTemplate | EmtModelTemplate
    if dynamic_simulation_mode is DynamicSimulationMode.RMS:
        assert len(circuit.rms_models) == 1
        assert len(circuit.emt_models) == 0
        installed_template = circuit.rms_models[0]
    else:
        assert dynamic_simulation_mode is DynamicSimulationMode.EMT
        assert len(circuit.emt_models) == 1
        assert len(circuit.rms_models) == 0
        installed_template = circuit.emt_models[0]

    assert installed_template.name == "Dynamic gain"
    assert any(
        entry.msg == "DGS dynamic model import completed"
        for entry in file_open.logger.entries
    )


def test_file_open_rejects_dynamic_dgs_import_without_an_explicit_mode() -> None:
    """Keep the static DGS result and report the missing RMS/EMT selection."""

    file_open: FileOpen = FileOpen(
        file_name=str(_get_dynamic_gain_block_dgs_path()),
        options=FileOpenOptions(
            file_type=FileType.DGS,
            dgs_use_dynamic_information=True,
        ),
    )
    circuit: MultiCircuit | None = file_open.open()

    assert circuit is not None

    assert len(circuit.rms_models) == 0
    assert len(circuit.emt_models) == 0
    assert any(
        entry.msg == "DGS dynamic model import requires an explicit RMS or EMT simulation mode"
        for entry in file_open.logger.entries
    )
