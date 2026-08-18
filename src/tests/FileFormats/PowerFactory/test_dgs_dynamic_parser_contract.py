# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from pathlib import Path

from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit


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
