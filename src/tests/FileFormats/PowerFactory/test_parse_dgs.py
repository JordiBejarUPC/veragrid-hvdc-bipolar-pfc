# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import os
import pandas as pd
import numpy as np
from types import SimpleNamespace

import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.file_open import FileOpen
from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit
from VeraGridEngine.IO.dgs.dgs_objects import ElmTr2, ElmXnet, StaCubic, TypCon, TypTow, TypTr2
from VeraGridEngine.IO.dgs.dgs_to_veragrid import (_apply_elmtow_tower_coupling,
                                                   _build_neutral_grounded_terminal_ids,
                                                   convert_dgs_to_overhead_line_type_geometrical_parameters,
                                                   convert_dgs_to_transformer,
                                                   convert_dgs_to_transformer_type,
                                                   convert_dgs_to_wire,
                                                   _get_overhead_line_template_with_phases,
                                                   _get_veragrid_phase_vector_from_cubic)
from VeraGridEngine.Devices.Branches.overhead_line_type import create_known_abc_overhead_template
from VeraGridEngine.enumerations import WindingType
from VeraGridEngine.Simulations.PowerFlow.power_flow_worker import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
from VeraGridEngine.IO.dgs.veragrid_to_dgs import circuit_to_dgs


def test_stacubic_cphinfo_phase_mapping_and_overhead_template() -> None:
    cubic = StaCubic()
    cubic.cPhInfo = "cN"
    cubic.it2p1 = 0
    cubic.it2p2 = 1
    cubic.it2p3 = 2

    phases = _get_veragrid_phase_vector_from_cubic(cubic=cubic, phase_count=3, invalid_values=set())

    assert phases.tolist() == [3, 0]

    z_nabc = np.diag(np.array([1.0 + 1.0j, 2.0 + 1.0j, 3.0 + 1.0j, 4.0 + 1.0j], dtype=complex))
    y_nabc = np.eye(4, dtype=complex) * 1e-6j
    template = create_known_abc_overhead_template(
        name="abcN",
        z_nabc=z_nabc,
        ysh_nabc=y_nabc,
        phases=np.array([0, 1, 2, 3]),
        Vnom=4.16,
        frequency=60.0,
    )

    filtered_template = _get_overhead_line_template_with_phases(
        template=template,
        phases=phases,
        logger=Logger(),
        device_name="L1",
        device_class="ElmLne",
    )
    admittance = filtered_template.get_ys(circuit_idx=1, Sbase=100.0, length=1.0, Vnom=4.16)

    assert filtered_template is not template
    assert filtered_template.z_phases_nabc.tolist() == [0, 3]
    assert filtered_template.y_phases_nabc.tolist() == [0, 3]
    assert filtered_template.z_nabc.shape == (2, 2)
    assert filtered_template.y_nabc.shape == (2, 2)
    assert admittance.phN
    assert not admittance.phA
    assert not admittance.phB
    assert admittance.phC
    assert np.allclose(admittance.values[1, :], 0.0)
    assert np.allclose(admittance.values[:, 1], 0.0)
    assert np.allclose(admittance.values[2, :], 0.0)
    assert np.allclose(admittance.values[:, 2], 0.0)


def test_overhead_template_with_same_phase_set_is_not_cloned_for_order_only_difference() -> None:
    z_nabc = np.diag(np.array([2.0 + 1.0j, 3.0 + 1.0j, 4.0 + 1.0j, 1.0 + 1.0j], dtype=complex))
    y_nabc = np.eye(4, dtype=complex) * 1e-6j
    template = create_known_abc_overhead_template(
        name="LineConfig601",
        z_nabc=z_nabc,
        ysh_nabc=y_nabc,
        phases=np.array([1, 2, 3, 0]),
        Vnom=4.16,
        frequency=60.0,
    )

    resolved_template = _get_overhead_line_template_with_phases(
        template=template,
        phases=np.array([0, 1, 2, 3]),
        logger=Logger(),
        device_name="LOHL650-632",
        device_class="ElmLne",
    )

    assert resolved_template is template


def test_single_phase_transformer_type_keeps_zero_positive_sequence_short_circuit_voltage() -> None:
    typtr2 = TypTr2()
    typtr2.loc_name = "AutoTRF1ph"
    typtr2.nt2ph = 2
    typtr2.strn = 1.667
    typtr2.frnom = 60.0
    typtr2.utrn_h = 2.401777
    typtr2.utrn_l = 2.401777
    typtr2.uktr = 0.0
    typtr2.uk0tr = 3.0
    typtr2.pcutr = 0.0
    typtr2.ur0tr = 0.0
    typtr2.tr2cn_h = "D"
    typtr2.tr2cn_l = "D"
    typtr2.itapch = 1
    typtr2.tap_side = 1
    typtr2.dutap = 0.625
    typtr2.nntap0 = 0
    typtr2.ntpmn = -16
    typtr2.ntpmx = 16

    template = convert_dgs_to_transformer_type(typtr2=typtr2)

    assert template.Vsc == 0.0


def test_external_grid_cphinfo_neutral_marks_terminal_grounded() -> None:
    dgs_grid = DgsCircuit()
    external_grid = ElmXnet()
    external_grid.ID = "15"
    external_grid.outserv = 0
    dgs_grid.elmxnets.append(external_grid)

    cubic = StaCubic()
    cubic.fold_id = "10"
    cubic.obj_id = "15"
    cubic.obj_bus = 0
    cubic.cPhInfo = "abcN"

    grounded_terminals = _build_neutral_grounded_terminal_ids(
        dgs_grid=dgs_grid,
        cubics_by_objid={"15": [cubic]},
    )

    assert grounded_terminals == {"10"}


def test_transformer_internal_lv_neutral_grounding_sets_to_side_ygrounded() -> None:
    bus_650 = dev.Bus(name="650", Vnom=4.16)
    bus_rg60 = dev.Bus(name="RG60", Vnom=4.16)

    typtr2 = TypTr2()
    typtr2.ID = "63"
    typtr2.loc_name = "AutoTRF1ph"
    typtr2.nt2ph = 2
    typtr2.strn = 1.667
    typtr2.frnom = 60.0
    typtr2.utrn_h = 2.401777
    typtr2.utrn_l = 2.401777
    typtr2.uktr = 1.0
    typtr2.pcutr = 0.0
    typtr2.uk0tr = 3.0
    typtr2.ur0tr = 0.0
    typtr2.tr2cn_h = "D"
    typtr2.tr2cn_l = "D"
    typtr2.itapch = 1
    typtr2.tap_side = 1
    typtr2.dutap = 0.625
    typtr2.nntap0 = 0
    typtr2.ntpmn = -16
    typtr2.ntpmx = 16

    tr2 = ElmTr2()
    tr2.ID = "12"
    tr2.loc_name = "UregA"
    tr2.typ_id = "63"
    tr2.nntap = 10
    tr2.ratfac = 1.0
    tr2.cgnd_h = 1
    tr2.cgnd_l = 0

    cubic_650 = StaCubic()
    cubic_650.ID = "40"
    cubic_650.fold_id = "650_term"
    cubic_650.obj_id = "12"
    cubic_650.obj_bus = 0
    cubic_650.cPhInfo = "aN"

    cubic_rg60 = StaCubic()
    cubic_rg60.ID = "41"
    cubic_rg60.fold_id = "rg60_term"
    cubic_rg60.obj_id = "12"
    cubic_rg60.obj_bus = 1
    cubic_rg60.cPhInfo = "aN"

    trafo = convert_dgs_to_transformer(
        tr2=tr2,
        buses=[bus_650, bus_rg60],
        stacubic_dict={},
        templates_dict={"63": convert_dgs_to_transformer_type(typtr2=typtr2)},
        typtr2_dict={"63": typtr2},
        freq=60.0,
        baseMVA=100.0,
        logger=Logger(),
        cubics_by_objid={"12": [cubic_650, cubic_rg60]},
        bus_by_term_id={"650_term": bus_650, "rg60_term": bus_rg60},
        switch_by_cubic_id={},
        neutral_grounded_terminal_ids=set(),
    )

    assert trafo.bus_from is bus_650
    assert trafo.bus_to is bus_rg60
    assert trafo.conn_f == WindingType.NeutralStar
    assert trafo.conn_t == WindingType.GroundedStar


def test_typtow_nphas_single_conductor_row_becomes_neutral() -> None:
    phase_conductor = TypCon()
    phase_conductor.ID = "59"
    phase_conductor.loc_name = "556.5 ACSR"
    phase_conductor.uline = 4.16
    phase_conductor.sline = 0.73
    phase_conductor.rpha = 0.115512
    phase_conductor.diaco = 23.5458
    phase_conductor.mlei = "Al"

    neutral_conductor = TypCon()
    neutral_conductor.ID = "60"
    neutral_conductor.loc_name = "n4 ACSR"
    neutral_conductor.uline = 4.16
    neutral_conductor.sline = 0.34
    neutral_conductor.rpha = 0.367851
    neutral_conductor.diaco = 14.3002
    neutral_conductor.mlei = "Al"

    typtow = TypTow()
    typtow.ID = "62"
    typtow.loc_name = "LineConfig601"
    typtow.frnom = 60.0
    typtow.gearth = 100.0
    typtow.pcond_c = ["59", "60"]
    typtow.nphas = [3.0, 1.0]
    typtow.xy_c = [
        [-0.3048, -1.0668, 1.0668, 8.5344, 8.5344, 8.5344],
        [0.1523999951232, 0.0, 0.0, 7.31519976591361, 0.0, 0.0],
    ]

    typcon_by_id = {
        "59": phase_conductor,
        "60": neutral_conductor,
    }
    wire_by_id = {
        "59": convert_dgs_to_wire(typcon=phase_conductor),
        "60": convert_dgs_to_wire(typcon=neutral_conductor),
    }

    template = convert_dgs_to_overhead_line_type_geometrical_parameters(
        typtow=typtow,
        typcon_by_id=typcon_by_id,
        wire_by_id=wire_by_id,
        default_frequency_hz=60.0,
    )
    wires = template.wires_in_tower.data

    assert [wire.phase for wire in wires] == [1, 2, 3, 0]
    assert [wire.phase_type for wire in wires] == ["A", "B", "C", "N"]
    assert [wire.circuit_index for wire in wires] == [1, 1, 1, 1]
    assert wires[3].name == "n4 ACSR"
    assert np.isclose(wires[3].xpos, 0.1523999951232)
    assert np.isclose(wires[3].ypos, 7.31519976591361)


def test_dgs_ieee_grids():
    files = [
        ('IEEE14_test.dgs', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE30_test.dgs', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE118_v2_test.dgs', 'IEEE 118 Bus.sav.xlsx'),
    ]

    data_dir = os.path.join("data")
    for solver_type in [SolverType.NR,
                        SolverType.IWAMOTO,
                        SolverType.LM,
                        SolverType.FASTDECOUPLED,
                        SolverType.PowellDogLeg,
                        SolverType.HELM]:

        options = PowerFlowOptions(solver_type,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False)

        for f1, f2 in files:
            fname = os.path.join(data_dir, "grids", "DGS", f1)
            main_circuit = FileOpen(fname).open()
            power_flow = PowerFlowDriver(main_circuit, options)
            power_flow.run()

            results_file = os.path.join(data_dir, "results", f2)
            df_v = pd.read_excel(results_file, sheet_name='Vabs', index_col=0)
            df_p = pd.read_excel(results_file, sheet_name='Pbranch', index_col=0)

            v_gc = np.abs(power_flow.results.voltage)
            v_psse = df_v.values[:, 0]
            p_gc = power_flow.results.Sf.real
            p_psse = df_p.values[:, 0]

            v_ok = np.allclose(v_gc, v_psse, atol=1e-4)
            flow_ok = np.allclose(p_gc, p_psse, atol=1e-2)

            assert v_ok
            assert flow_ok

        print(solver_type, 'ok')

def test_roundtrip_raw_to_dgs_to_dgs_ieee_grids():
    """
    Roundtrip test:
      RAW -> powerflow (res1)
      export to DGS
      import same DGS -> powerflow (res2)
      check res1 == res2 (Vabs and Pbranch) with same tolerances as the RAW-vs-PSS/E test
    """

    files = [
        ('IEEE 14 bus.raw', 'IEEE 14 bus.sav.xlsx'),
        ('IEEE 30 bus.raw', 'IEEE 30 bus.sav.xlsx'),
        ('IEEE 118 Bus v2.raw', 'IEEE 118 Bus.sav.xlsx'),
    ]


    out_dir = os.path.join("data", "grids", "DGS", "_roundtrip_tmp")
    os.makedirs(out_dir, exist_ok=True)

    for solver_type in [SolverType.NR,
                        SolverType.IWAMOTO,
                        SolverType.LM,
                        SolverType.FASTDECOUPLED,
                        SolverType.PowellDogLeg,
                        SolverType.HELM]:

        options = PowerFlowOptions(solver_type,
                                   verbose=0,
                                   control_q=False,
                                   retry_with_other_methods=False)

        for f1, _ in files:
            raw_path = os.path.join("data", "grids", "RAW", f1)
            main_circuit = FileOpen(raw_path).open()

            pf1 = PowerFlowDriver(main_circuit, options)
            pf1.run()

            v1 = np.abs(pf1.results.voltage)
            p1 = pf1.results.Sf.real

            # export to dgs (same logic as FileHandler.save_dgs)
            dgs_path = os.path.join(out_dir, f1.replace('.raw', f'__{solver_type.name}.dgs'))
            dgs = circuit_to_dgs(grid=main_circuit)
            dgs.write_dgs(path=dgs_path)

            # import the same dgs and run again
            rt_circuit = FileOpen(dgs_path).open()

            pf2 = PowerFlowDriver(rt_circuit, options)
            pf2.run()

            v2 = np.abs(pf2.results.voltage)
            p2 = pf2.results.Sf.real

            v_ok = np.allclose(v1, v2, atol=1e-4)
            flow_ok = np.allclose(p1, p2, atol=1e-2)
            assert v_ok
            assert flow_ok

        print(solver_type, 'ok')


def test_circuit_to_dgs_uses_profile_values_when_t_idx_is_provided() -> None:
    """DGS export must use profile values when ``t_idx`` is provided."""

    grid: dev.MultiCircuit = dev.MultiCircuit(name="profile-export")

    bus_1: dev.Bus = dev.Bus(name="B1", Vnom=110.0, active=True)
    bus_2: dev.Bus = dev.Bus(name="B2", Vnom=110.0, active=True)
    bus_1.active_prof = np.array([True, False])
    grid.add_bus(bus_1)
    grid.add_bus(bus_2)

    load: dev.Load = dev.Load(name="LD1", P=10.0, Q=2.0, active=True)
    load.P_prof = np.array([12.0, 22.0])
    load.Q_prof = np.array([3.0, 5.0])
    load.active_prof = np.array([True, False])
    grid.add_load(bus=bus_1, api_obj=load)

    line: dev.Line = dev.Line(
        bus_from=bus_1,
        bus_to=bus_2,
        name="L12",
        r=0.01,
        x=0.05,
        b=0.001,
        rate=100.0,
        active=True,
    )
    line.rate_prof = np.array([120.0, 220.0])
    line.active_prof = np.array([True, False])
    grid.add_line(line)

    switch: dev.Switch = dev.Switch(
        bus_from=bus_1,
        bus_to=bus_2,
        name="SW12",
        rate=80.0,
        active=True,
        rated_current=0.0,
    )
    switch.rate_prof = np.array([90.0, 180.0])
    switch.active_prof = np.array([True, False])
    grid.add_switch(switch)

    snapshot_export = circuit_to_dgs(grid=grid, t_idx=None)
    profile_export = circuit_to_dgs(grid=grid, t_idx=1)

    snapshot_line_current: float = 100.0 / (np.sqrt(3.0) * 110.0)
    profile_line_current: float = 220.0 / (np.sqrt(3.0) * 110.0)
    snapshot_switch_current: float = 80.0 / (np.sqrt(3.0) * 110.0)
    profile_switch_current: float = 180.0 / (np.sqrt(3.0) * 110.0)

    assert snapshot_export.elmterms[0].outserv == 0
    assert profile_export.elmterms[0].outserv == 1

    assert snapshot_export.elmlods[0].plini == 10.0
    assert profile_export.elmlods[0].plini == 22.0
    assert snapshot_export.elmlods[0].qlini == 2.0
    assert profile_export.elmlods[0].qlini == 5.0
    assert snapshot_export.elmlods[0].outserv == 0
    assert profile_export.elmlods[0].outserv == 1

    assert np.isclose(snapshot_export.typlnes[0].InomAir, snapshot_line_current)
    assert np.isclose(profile_export.typlnes[0].InomAir, profile_line_current)
    assert snapshot_export.elmlnes[0].outserv == 0
    assert profile_export.elmlnes[0].outserv == 1

    assert np.isclose(snapshot_export.typswitches[0].InomA, snapshot_switch_current)
    assert np.isclose(profile_export.typswitches[0].InomA, profile_switch_current)
    assert snapshot_export.elmcoups[0].on_off == 1
    assert profile_export.elmcoups[0].on_off == 0


def test_dgs_tower_coupling_logs_non_empty_message_for_blank_value_error() -> None:
    class FakeLine:
        def __init__(self) -> None:
            self.name = "L1"

        def set_circuit_idx(self, val: int, obj) -> None:
            pass

        def apply_template(self, obj, Sbase: float, freq: float, logger: Logger) -> None:
            raise ValueError()

    logger = Logger()
    cubic_1 = StaCubic()
    cubic_1.it2p1 = 0
    cubic_1.it2p2 = 1
    cubic_1.it2p3 = 2
    cubic_2 = StaCubic()
    cubic_2.it2p1 = 0
    cubic_2.it2p2 = 1
    cubic_2.it2p3 = 2
    dgs_grid = SimpleNamespace(
        elmtows=[
            SimpleNamespace(
                outserv=0,
                pGeo=["tower-1"],
                loc_name="Tower 1",
                ID="tower-id",
                plines=["line-1"],
            )
        ]
    )

    _apply_elmtow_tower_coupling(
        dgs_grid=dgs_grid,
        grid=dev.MultiCircuit(),
        line_by_dgs_id={"line-1": [FakeLine()]},
        overhead_line_type_dict={"tower-1": dev.OverheadLineType(name="tower-1")},
        baseMVA=100.0,
        frequency=50.0,
        logger=logger,
        cubics_by_objid={"line-1": [cubic_1, cubic_2]},
    )

    assert len(logger.entries) == 1
    assert logger.entries[0].msg == "Failed to apply tower template."
