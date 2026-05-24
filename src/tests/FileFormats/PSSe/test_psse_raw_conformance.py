# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Regression tests for PSSE RAW parser and writer conformance."""

from pathlib import Path

import VeraGridEngine.Devices as dev
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.IO.raw.versioned.v34.switched_shunt import RawSwitchedShuntV34
from VeraGridEngine.IO.raw.versioned.v35.switched_shunt import RawSwitchedShuntV35
from VeraGridEngine.IO.raw.versioned.v36.switched_shunt import RawSwitchedShuntV36
from VeraGridEngine.IO.raw.versioned.v34.system_switching_device import RawSystemSwitchingDeviceV34
from VeraGridEngine.IO.raw.versioned.v35.system_switching_device import RawSystemSwitchingDeviceV35
from VeraGridEngine.IO.raw.versioned.v36.system_switching_device import RawSystemSwitchingDeviceV36
from VeraGridEngine.IO.raw.versioned.v29.transformer import RawTransformerV29 as RawTransformer
from VeraGridEngine.IO.raw.versioned.v33.branch import RawBranchV33
from VeraGridEngine.IO.raw.versioned.v35.node import RawNodeV35
from VeraGridEngine.IO.raw.versioned.v35.induction_machine import RawInductionMachineV35
from VeraGridEngine.IO.raw.versioned.v35.gne_device import RawGneDeviceV35
from VeraGridEngine.IO.raw.versioned.v36.load import RawLoadV36
from VeraGridEngine.IO.raw.versioned.v36.fixed_shunt import RawFixedShuntV36
from VeraGridEngine.IO.raw.versioned.v36.generator import RawGeneratorV36
from VeraGridEngine.IO.raw.versioned.v34.transformer import RawTransformerV34
from VeraGridEngine.IO.raw.versioned.v35.transformer import RawTransformerV35
from VeraGridEngine.IO.raw.versioned.v34.vsc_dc_line import RawVscDCLineV34
from VeraGridEngine.IO.raw.versioned.v35.vsc_dc_line import RawVscDCLineV35
from VeraGridEngine.IO.raw.raw_parser_writer import interpret_line, read_and_split, read_raw
from VeraGridEngine.IO.raw.veragrid_to_raw import veragrid_to_raw
from VeraGridEngine.basic_structures import Logger


def test_read_raw_keeps_psse35_system_wide_records_out_of_bus_section(tmp_path: Path) -> None:
    """PSSE 35 system-wide records must not be parsed as bus records."""

    raw_text: str = "\n".join(
        [
            "0,100.0,35,0,0,60.0",
            "Test case",
            "Test case 2",
            "GENERAL, THRSHZ=0.0001",
            "SOLVER, FNSL, ACTAPS=0",
            "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA",
            "1,'BUS1',230.0,3,1,1,1,1.0,0.0,1.1,0.9,1.1,0.9",
            "0 / END OF BUS DATA",
            "Q",
        ]
    )
    raw_path: Path = tmp_path / "psse35_system_wide.raw"
    raw_path.write_text(raw_text, encoding="utf-8")

    sections_dict = read_and_split(str(raw_path))
    psse_circuit = read_raw(str(raw_path), logger=Logger())

    assert "system-wide" in sections_dict
    assert len(sections_dict["system-wide"]) == 2
    assert len(sections_dict["bus"]) == 1
    assert len(psse_circuit.buses) == 1
    assert psse_circuit.buses[0].I == 1


def test_switched_shunt_writer_uses_psse35_status_triplets() -> None:
    """PSSE 35 switched shunts must write S/N/B triplets for each block."""

    switched_shunt = RawSwitchedShuntV35()
    switched_shunt.I = 10
    switched_shunt.ID = "A1"
    switched_shunt.MODSW = 1
    switched_shunt.ADJM = 0
    switched_shunt.STAT = 1
    switched_shunt.VSWHI = 1.05
    switched_shunt.VSWLO = 0.95
    switched_shunt.SWREG = 11
    switched_shunt.NREG = 0
    switched_shunt.RMPCT = 100.0
    switched_shunt.RMIDNT = ""
    switched_shunt.BINIT = 0.25
    switched_shunt.S1 = 1
    switched_shunt.N1 = 3
    switched_shunt.B1 = 0.25

    raw_values = interpret_line(switched_shunt.get_raw_line(35))

    assert len(raw_values) == 36
    assert raw_values[12:15] == [1, 3, 0.25]


def test_switched_shunt_writer_uses_psse36_name_field() -> None:
    """PSSE 36 switched shunts must write NAME before the S/N/B triplets."""

    switched_shunt = RawSwitchedShuntV36()
    switched_shunt.I = 10
    switched_shunt.ID = "A1"
    switched_shunt.MODSW = 1
    switched_shunt.ADJM = 0
    switched_shunt.STAT = 1
    switched_shunt.VSWHI = 1.05
    switched_shunt.VSWLO = 0.95
    switched_shunt.SWREG = 11
    switched_shunt.NREG = 0
    switched_shunt.RMPCT = 100.0
    switched_shunt.RMIDNT = ""
    switched_shunt.BINIT = 0.25
    switched_shunt.NAME = "SVD1"
    switched_shunt.S1 = 1
    switched_shunt.N1 = 3
    switched_shunt.B1 = 0.25

    raw_values = interpret_line(switched_shunt.get_raw_line(36))

    assert len(raw_values) == 37
    assert raw_values[12] == "SVD1"
    assert raw_values[13:16] == [1, 3, 0.25]


def test_switched_shunt_writer_uses_swrem_before_psse35() -> None:
    """PSSE 34 switched shunts must write SWREM instead of the PSSE 35 SWREG field."""

    switched_shunt = RawSwitchedShuntV34()
    switched_shunt.I = 20
    switched_shunt.MODSW = 1
    switched_shunt.ADJM = 0
    switched_shunt.STAT = 1
    switched_shunt.VSWHI = 1.05
    switched_shunt.VSWLO = 0.95
    switched_shunt.SWREM = 77
    switched_shunt.SWREG = 88
    switched_shunt.RMPCT = 100.0
    switched_shunt.BINIT = 0.10

    raw_values = interpret_line(switched_shunt.get_raw_line(34))

    assert raw_values[6] == 77


def test_vsc_dc_line_writer_uses_version_specific_control_fields() -> None:
    """PSSE 34 uses REMOT while PSSE 35 uses VSREG/NREG in VSC dc records."""

    vsc_34 = RawVscDCLineV34()
    vsc_35 = RawVscDCLineV35()

    for vsc_line in (vsc_34, vsc_35):
        vsc_line.NAME = "VSC1"
        vsc_line.MDC = 1
        vsc_line.RDC = 2.5
        vsc_line.IBUS1 = 101
        vsc_line.TYPE1 = 1
        vsc_line.MODE1 = 1
        vsc_line.DCSET1 = 50.0
        vsc_line.ACSET1 = 1.01
        vsc_line.ALOSS1 = 1.0
        vsc_line.BLOSS1 = 2.0
        vsc_line.MINLOSS1 = 3
        vsc_line.SMAX1 = 120.0
        vsc_line.IMAX1 = 400.0
        vsc_line.PWF1 = 0.5
        vsc_line.MAXQ1 = 40.0
        vsc_line.MINQ1 = -40.0
        vsc_line.RMPCT1 = 100.0
        vsc_line.IBUS2 = 102
        vsc_line.TYPE2 = 2
        vsc_line.MODE2 = 1
        vsc_line.DCSET2 = -50.0
        vsc_line.ACSET2 = 0.99
        vsc_line.ALOSS2 = 1.0
        vsc_line.BLOSS2 = 2.0
        vsc_line.MINLOSS2 = 3
        vsc_line.SMAX2 = 120.0
        vsc_line.IMAX2 = 400.0
        vsc_line.PWF2 = 0.5
        vsc_line.MAXQ2 = 40.0
        vsc_line.MINQ2 = -40.0
        vsc_line.RMPCT2 = 100.0

    vsc_34.REMOT1 = 201
    vsc_34.REMOT2 = 202
    vsc_35.VSREG1 = 301
    vsc_35.NREG1 = 1
    vsc_35.VSREG2 = 302
    vsc_35.NREG2 = 2

    raw_values_34_line_2 = interpret_line(vsc_34.get_raw_line(34).splitlines()[1])
    raw_values_35_line_2 = interpret_line(vsc_35.get_raw_line(35).splitlines()[1])

    assert len(raw_values_34_line_2) == 15
    assert raw_values_34_line_2[13] == 201
    assert len(raw_values_35_line_2) == 16
    assert raw_values_35_line_2[13:15] == [301, 1]


def test_system_switching_device_writer_supports_psse34_and_psse35() -> None:
    """System switching device export must use the actual property names for both supported revisions."""

    switching_device_34 = RawSystemSwitchingDeviceV34()
    switching_device_35 = RawSystemSwitchingDeviceV35()

    for switching_device in (switching_device_34, switching_device_35):
        switching_device.I = 1
        switching_device.J = 2
        switching_device.CKT = "1"
        switching_device.X = 0.001
        switching_device.RATE1 = 100.0
        switching_device.STATUS = 1
        switching_device.NSTATUS = 0
        switching_device.METERED = 2
        switching_device.STYPE = 3
        switching_device.NAME = "SW1"

    raw_values_34 = interpret_line(switching_device_34.get_raw_line(34))
    raw_values_35 = interpret_line(switching_device_35.get_raw_line(35))

    assert switching_device_34.CKTID == "1"
    assert raw_values_34[16:21] == [1, 0, 2, 3, "SW1"]
    assert raw_values_35[16:21] == [1, 0, 2, 3, "SW1"]


def test_system_switching_device_writer_uses_psse36_rating_set_name() -> None:
    """PSSE 36 system switching devices must write RSETNAM instead of RATE fields."""

    switching_device = RawSystemSwitchingDeviceV36()
    switching_device.I = 1
    switching_device.J = 2
    switching_device.CKT = "1"
    switching_device.X = 0.0001
    switching_device.RSETNAM = "BREAKER_01"
    switching_device.STATUS = 1
    switching_device.NSTATUS = 1
    switching_device.METERED = 2
    switching_device.STYPE = 3
    switching_device.NAME = "SW1"

    raw_values = interpret_line(switching_device.get_raw_line(36))

    assert len(raw_values) == 10
    assert raw_values[4] == "BREAKER_01"
    assert raw_values[5:10] == [1, 1, 2, 3, "SW1"]


def test_psse36_load_fixed_shunt_and_generator_include_new_name_fields() -> None:
    """PSSE 36 adds NAME to loads and fixed shunts, plus DROOPNAME/NAME to generators."""

    load = RawLoadV36()
    load.I = 101
    load.ID = "1"
    load.STATUS = 1
    load.AREA = 1
    load.ZONE = 1
    load.OWNER = 1
    load.LOADTYPE = "IND"
    load.NAME = "LOAD_A"

    fixed_shunt = RawFixedShuntV36()
    fixed_shunt.I = 102
    fixed_shunt.ID = "1"
    fixed_shunt.STATUS = 1
    fixed_shunt.NAME = "FSH_A"

    generator = RawGeneratorV36()
    generator.I = 103
    generator.ID = "1"
    generator.STAT = 1
    generator.O1 = 1
    generator.F1 = 1.0
    generator.DROOPNAME = "DROOP_A"
    generator.NAME = "GEN_A"

    load_values = interpret_line(load.get_raw_line(36))
    fixed_shunt_values = interpret_line(fixed_shunt.get_raw_line(36))
    generator_values = interpret_line(generator.get_raw_line(36))

    assert len(load_values) == 19
    assert load_values[-1] == "LOAD_A"
    assert len(fixed_shunt_values) == 6
    assert fixed_shunt_values[-1] == "FSH_A"
    assert len(generator_values) == 32
    assert generator_values[-2:] == ["DROOP_A", "GEN_A"]


def test_transformer_writer_uses_version_specific_psse34_and_psse35_layouts() -> None:
    """PSSE 34 omits NODE and two-winding ZCOD, while PSSE 35 keeps NODE but still omits two-winding ZCOD."""

    transformer_34 = RawTransformerV34()
    transformer_35 = RawTransformerV35()

    for transformer in (transformer_34, transformer_35):
        transformer.windings = 2
        transformer.I = 1
        transformer.J = 2
        transformer.K = 0
        transformer.CKT = "1"
        transformer.CW = 1
        transformer.CZ = 1
        transformer.CM = 1
        transformer.MAG1 = 0.0
        transformer.MAG2 = 0.0
        transformer.NMETR = 2
        transformer.NAME = "TX"
        transformer.STAT = 1
        transformer.O1 = 1
        transformer.F1 = 1.0
        transformer.VECGRP = "YN"
        transformer.ZCOD = 1
        transformer.R1_2 = 0.01
        transformer.X1_2 = 0.10
        transformer.SBASE1_2 = 100.0
        transformer.WINDV1 = 1.0
        transformer.NOMV1 = 220.0
        transformer.ANG1 = 0.0
        transformer.RATE1_1 = 100.0
        transformer.RATE1_2 = 101.0
        transformer.RATE1_3 = 102.0
        transformer.RATE1_4 = 103.0
        transformer.RATE1_5 = 104.0
        transformer.RATE1_6 = 105.0
        transformer.RATE1_7 = 106.0
        transformer.RATE1_8 = 107.0
        transformer.RATE1_9 = 108.0
        transformer.RATE1_10 = 109.0
        transformer.RATE1_11 = 110.0
        transformer.RATE1_12 = 111.0
        transformer.COD1 = 1
        transformer.CONT1 = 11
        transformer.NODE1 = 7
        transformer.RMA1 = 1.1
        transformer.RMI1 = 0.9
        transformer.VMA1 = 1.1
        transformer.VMI1 = 0.9
        transformer.NTP1 = 33
        transformer.TAB1 = 0
        transformer.CR1 = 0.0
        transformer.CX1 = 0.0
        transformer.CNXA1 = 0.0
        transformer.WINDV2 = 1.0
        transformer.NOMV2 = 110.0

    raw_values_34_line_1 = interpret_line(transformer_34.get_raw_line(34).splitlines()[0])
    raw_values_34_line_3 = interpret_line(transformer_34.get_raw_line(34).splitlines()[2])
    raw_values_35_line_1 = interpret_line(transformer_35.get_raw_line(35).splitlines()[0])
    raw_values_35_line_3 = interpret_line(transformer_35.get_raw_line(35).splitlines()[2])

    assert len(raw_values_34_line_1) == 21
    assert len(raw_values_34_line_3) == 26
    assert len(raw_values_35_line_1) == 21
    assert len(raw_values_35_line_3) == 27
    assert raw_values_35_line_3[17] == 7


def test_psse33_branch_writer_uses_rateabc_field_order() -> None:
    """PSSE 33 branches must expose RATEA/RATEB/RATEC."""

    branch = RawBranchV33()
    branch.I = 1
    branch.J = 2
    branch.CKT = "1"
    branch.R = 0.01
    branch.X = 0.10
    branch.B = 0.001
    branch.RATEA = 100.0
    branch.RATEB = 110.0
    branch.RATEC = 120.0
    branch.GI = 0.0
    branch.BI = 0.0
    branch.GJ = 0.0
    branch.BJ = 0.0
    branch.ST = 1
    branch.MET = 1
    branch.LEN = 10.0

    raw_values = interpret_line(branch.get_raw_line(33))

    assert raw_values[6:9] == [100.0, 110.0, 120.0]
    assert branch.RATE1 == 100.0
    assert branch.RATE2 == 110.0
    assert branch.RATE3 == 120.0


def test_psse35_node_writer_omits_isub_from_raw_record() -> None:
    """PSSE 35 node RAW records are NI, NAME, I, STATUS, VM, VA without ISUB in-line."""

    node = RawNodeV35()
    node.ISUB = 99
    node.NI = 4
    node.NAME = "NODE_4"
    node.I = 3009
    node.STATUS = 1
    node.VM = 1.02
    node.VA = 3.5

    raw_values = interpret_line(node.get_raw_line(35))

    assert raw_values == [4, "NODE_4", 3009, 1, 1.02, 3.5]


def test_psse35_induction_machine_uses_stat_field_name() -> None:
    """Induction machine classes should expose STAT per the manual while keeping compatibility aliasing."""

    machine = RawInductionMachineV35()
    machine.I = 3010
    machine.ID = "1"
    machine.STAT = 1
    machine.SCODE = 1
    machine.DCODE = 2
    machine.AREA = 5
    machine.ZONE = 4
    machine.OWNER = 5
    machine.TCODE = 1
    machine.BCODE = 1
    machine.MBASE = 1.0
    machine.RATEKV = 21.6
    machine.PCODE = 1
    machine.PSET = 1.0
    machine.H = 1.0
    machine.A = 1.0
    machine.B = 1.0
    machine.D = 1.0
    machine.E = 1.0
    machine.RA = 0.0
    machine.XA = 0.0
    machine.XM = 0.0
    machine.R1 = 0.0
    machine.X1 = 0.0
    machine.R2 = 0.0
    machine.X2 = 0.0
    machine.X3 = 0.0
    machine.E1 = 0.0
    machine.SE1 = 0.0
    machine.E2 = 0.0
    machine.SE2 = 0.0
    machine.IA1 = 0.0
    machine.IA2 = 0.0
    machine.XAMULT = 1.0

    raw_values = interpret_line(machine.get_raw_line(35).splitlines()[0])

    assert raw_values[2] == 1
    assert machine.STATUS == 1


def test_psse35_gne_writer_uses_nmet_field_name() -> None:
    """PSSE 35 GNE records should use NMET rather than older NMETR spelling."""

    gne = RawGneDeviceV35()
    gne.NAME = "GNE1"
    gne.MODEL = "MODEL1"
    gne.NTERM = 2
    gne.BUS1 = 101
    gne.BUS2 = 102
    gne.NREAL = 2
    gne.NINTG = 1
    gne.NCHAR = 1
    gne.STATUS = 1
    gne.OWNER = 5
    gne.NMET = 2
    gne.REAL1 = 1.5
    gne.REAL2 = 2.5
    gne.INTG1 = 7
    gne.CHAR1 = "A1"

    lines = gne.get_raw_line(35).splitlines()
    header_values = interpret_line(lines[0])
    status_values = interpret_line(lines[1])

    assert header_values == ["GNE1", "MODEL1", 2, 101, 102, 2, 1, 1]
    assert status_values == [1, 5, 2]


def test_veragrid_to_raw_exports_each_hvdc_line_once() -> None:
    """Generic VeraGrid HVDC lines must not be exported into both PSSE HVDC categories."""

    logger = Logger()
    grid = MultiCircuit()

    bus_from = dev.Bus(name="B1", code="1", Vnom=220.0)
    bus_to = dev.Bus(name="B2", code="2", Vnom=220.0)
    grid.add_bus(bus_from)
    grid.add_bus(bus_to)

    hvdc_line = dev.HvdcLine(
        bus_from=bus_from,
        bus_to=bus_to,
        name="HVDC1",
        code="1_2_1",
        Pset=50.0,
        r=5.0,
        Vset_f=1.0,
        Vset_t=1.0,
        rate=100.0,
    )
    grid.add_hvdc(hvdc_line)

    psse_circuit = veragrid_to_raw(grid=grid, version=35, logger=logger)

    assert len(psse_circuit.two_terminal_dc_lines) == 1
    assert len(psse_circuit.vsc_dc_lines) == 0


def test_veragrid_to_raw_preserves_vsc_hvdc_endpoint_data() -> None:
    """
    Ensure the VSC exporter writes the converter bus and control records needed for roundtrip parsing.
    """
    grid: MultiCircuit = MultiCircuit()
    bus_from: dev.Bus = dev.Bus(name="From", Vnom=220.0, code="101")
    bus_to: dev.Bus = dev.Bus(name="To", Vnom=220.0, code="102")

    grid.add_bus(bus_from)
    grid.add_bus(bus_to)

    hvdc_line: dev.HvdcLine = dev.HvdcLine(
        bus_from=bus_from,
        bus_to=bus_to,
        name="VSC link",
        Pset=75.0,
        Vset_f=0.97,
        Vset_t=1.01,
        rate=120.0,
    )
    grid.add_hvdc(hvdc_line)

    logger: Logger = Logger()
    psse_circuit = veragrid_to_raw(grid=grid, version=35, logger=logger)

    assert len(psse_circuit.two_terminal_dc_lines) == 0
    assert len(psse_circuit.vsc_dc_lines) == 1

    exported_vsc = psse_circuit.vsc_dc_lines[0]

    assert exported_vsc.IBUS1 == 101
    assert exported_vsc.IBUS2 == 102
    assert exported_vsc.TYPE1 == 1
    assert exported_vsc.TYPE2 == 2
    assert exported_vsc.MODE1 == 1
    assert exported_vsc.MODE2 == 1
    assert exported_vsc.DCSET1 == 75.0
    assert exported_vsc.DCSET2 == -75.0
    assert exported_vsc.ACSET1 == 0.97
    assert exported_vsc.ACSET2 == 1.01
    assert exported_vsc.SMAX1 == 120.0
    assert exported_vsc.SMAX2 == 120.0
    assert exported_vsc.VSREG1 == 101
    assert exported_vsc.VSREG2 == 102


def test_veragrid_to_raw_uses_requested_version_specific_classes() -> None:
    """Export must instantiate the target version object classes, not generic v29 shells."""

    grid = MultiCircuit()
    bus = dev.Bus(name="B1", code="1", Vnom=220.0)
    grid.add_bus(bus)
    grid.add_load(bus, dev.Load(name="LOAD_A"))
    grid.add_shunt(bus, dev.Shunt(name="FSH_A"))

    logger = Logger()
    psse_circuit = veragrid_to_raw(grid=grid, version=36, logger=logger)

    assert psse_circuit.REV == 36
    assert type(psse_circuit.loads[0]).__name__ == "RawLoadV36"
    assert type(psse_circuit.fixed_shunts[0]).__name__ == "RawFixedShuntV36"
    assert interpret_line(psse_circuit.loads[0].get_raw_line(36))[-1] == "LOAD_A"
    assert interpret_line(psse_circuit.fixed_shunts[0].get_raw_line(36))[-1] == "FSH_A"


def test_veragrid_to_raw_v34_vsc_export_uses_remot_fields() -> None:
    """PSSE 34 VSC export must populate REMOT instead of VSREG/NREG."""

    grid = MultiCircuit()
    bus_from = dev.Bus(name="From", Vnom=220.0, code="101")
    bus_to = dev.Bus(name="To", Vnom=220.0, code="102")
    grid.add_bus(bus_from)
    grid.add_bus(bus_to)
    grid.add_hvdc(dev.HvdcLine(
        bus_from=bus_from,
        bus_to=bus_to,
        name="VSC34",
        Pset=75.0,
        Vset_f=0.97,
        Vset_t=1.01,
        rate=120.0,
    ))

    exported_vsc = veragrid_to_raw(grid=grid, version=34, logger=Logger()).vsc_dc_lines[0]

    assert type(exported_vsc).__name__ == "RawVscDCLineV34"
    assert exported_vsc.REMOT1 == 101
    assert exported_vsc.REMOT2 == 102


def test_veragrid_to_raw_switch_normal_status_uses_psse_semantics() -> None:
    """Normal-open VeraGrid switches must export NSTATUS=0; normally closed must export NSTATUS=1."""

    grid = MultiCircuit()
    bus_from = dev.Bus(name="From", Vnom=220.0, code="1")
    bus_to = dev.Bus(name="To", Vnom=220.0, code="2")
    grid.add_bus(bus_from)
    grid.add_bus(bus_to)
    grid.add_branch(dev.Switch(bus_from=bus_from, bus_to=bus_to, name="SW_OPEN", normal_open=True))
    grid.add_branch(dev.Switch(bus_from=bus_from, bus_to=bus_to, name="SW_CLOSED", normal_open=False))

    exported_switches = veragrid_to_raw(grid=grid, version=35, logger=Logger()).switches

    assert exported_switches[0].NSTATUS == 0
    assert exported_switches[1].NSTATUS == 1


def test_psse33_transformer_preserves_second_winding_rate_b_value() -> None:
    """PSSE 33 three-winding transformer parsing and writing must preserve RATE2-2."""

    transformer = RawTransformer()
    transformer.parse(
        data=[
            [1, 2, 3, "1", 1, 1, 1, 0.0, 0.0, 2, "TR3", 1, 1, 1.0, 0, 0.0, 0, 0.0, 0, 0.0, "VG"],
            [0.01, 0.10, 100.0, 0.02, 0.20, 100.0, 0.03, 0.30, 100.0, 1.0, 0.0],
            [1.0, 220.0, 0.0, 100.0, 101.0, 102.0, 1, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0.0, 0.0, 0.0],
            [1.0, 110.0, 0.0, 200.0, 201.0, 202.0, 1, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0.0, 0.0, 0.0],
            [1.0, 33.0, 0.0, 300.0, 301.0, 302.0, 1, 0, 1.1, 0.9, 1.1, 0.9, 33, 0, 0.0, 0.0, 0.0],
        ],
        version=33,
        logger=Logger(),
    )

    raw_lines = transformer.get_raw_line(33).splitlines()
    second_winding_values = interpret_line(raw_lines[3])

    assert transformer.RATB2 == 201.0
    assert transformer.RATE2_2 == 201.0
    assert second_winding_values[4] == 201.0
