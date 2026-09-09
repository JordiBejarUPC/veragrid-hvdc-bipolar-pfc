

from __future__ import annotations

import time

import matplotlib.pyplot as plt
import numpy as np

from typing import Any

from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line

from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.rms_driver import RmsSimulationDriver
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup

from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template_v2 import get_complete_generator_template_rms

from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template

from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model

from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
import VeraGridEngine.api as gce


# pr = profile.Profile()
# pr.disable()

def find_name_in_block(name: str, block: Block) -> Any | None:
    """
    Search one symbolic block hierarchy for a variable by name.

    :param name: Symbolic variable name to locate.
    :type name: str
    :param block: Root block to inspect.
    :type block: Block
    :return: Matching symbolic object when found, otherwise ``None``.
    :rtype: Any | None
    """
    var: Any
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var
        else:
            pass

    mdl: Block
    for mdl in block.children:
        res: Any | None = find_name_in_block(name, mdl)
        if res is not None:
            return res
        else:
            pass

    return None


def rms_kundur() -> None:
    """
    Build and run the Kundur RMS benchmark using the standard RMS scripting flow.

    :return: None.
    :rtype: None
    """
    ###########################################################################################################################
    # Build VeraGrid object
    ###########################################################################################################################

    grid = gce.MultiCircuit()  # Buses
    bus1 = Bus(name="Bus1", Vnom=20)
    bus2 = Bus(name="Bus2", Vnom=20)
    bus3 = Bus(name="Bus3", Vnom=20, is_slack=True)
    bus4 = Bus(name="Bus4", Vnom=20)
    bus5 = Bus(name="Bus5", Vnom=230)
    bus6 = Bus(name="Bus6", Vnom=230)
    bus7 = Bus(name="Bus7", Vnom=230)
    bus8 = Bus(name="Bus8", Vnom=230)
    bus9 = Bus(name="Bus9", Vnom=230)
    bus10 = Bus(name="Bus10", Vnom=230)
    bus11 = Bus(name="Bus11", Vnom=230)

    grid.add_bus(bus1)
    grid.add_bus(bus2)
    grid.add_bus(bus3)
    grid.add_bus(bus4)
    grid.add_bus(bus5)
    grid.add_bus(bus6)
    grid.add_bus(bus7)
    grid.add_bus(bus8)
    grid.add_bus(bus9)
    grid.add_bus(bus10)
    grid.add_bus(bus11)

    for bus in grid.buses:
        initialize_bus_rms(bus, vf=grid.var_factory)

    # Line
    line0 = gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6, r=0.00500, x=0.05000, b=0.02187, rate=750.0)
    line1 = gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6, r=0.00500, x=0.05000, b=0.02187, rate=750.0)
    line2 = gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line3 = gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line4 = gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line5 = gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8, r=0.01100, x=0.11000, b=0.19250, rate=400.0)
    line6 = gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8, r=0.01100, x=0.11000, b=0.19250, rate=400.0)
    line7 = gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9, r=0.01100, x=0.11000, b=0.19250, rate=400.0)
    line8 = gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9, r=0.01100, x=0.11000, b=0.19250, rate=400.0)
    line9 = gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line10 = gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line11 = gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10, r=0.00300, x=0.03000, b=0.00583, rate=700.0)
    line12 = gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11, r=0.00500, x=0.05000, b=0.02187, rate=750.0)
    line13 = gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11, r=0.00500, x=0.05000, b=0.02187, rate=750.0)

    # Transformers
    xt1 = 0.15 * (100.0 / 900.0)

    trafo_G1 = Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1, r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0,
                    rate=900.0)
    trafo_G2 = gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2, r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0,
                        rate=900.0)
    trafo_G3 = gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3, r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0,
                        rate=900.0)
    trafo_G4 = gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4, r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0,
                        rate=900.0)

    # load
    load1 = gce.Load(name="load1", P=9.999999, Q=0.999999)
    load2 = gce.Load(name="load2", P=9.999999, Q=0.999999)

    # Generators
    fn_1 = 60.0
    M_1 = 13.0 * 9.0
    D_1 = 10.0 * 9.0
    ra_1 = 0.0
    xd_1 = 0.3 * 100.0 / 900.0
    omega_ref_1 = 1.0
    Kp_1 = 0.0
    Ki_1 = 0.0

    fn_2 = 60.0
    M_2 = 13.0 * 9.0
    D_2 = 10.0 * 9.0
    ra_2 = 0.0
    xd_2 = 0.3 * 100.0 / 900.0
    omega_ref_2 = 1.0
    Kp_2 = 0.0
    Ki_2 = 0.0

    fn_3 = 60.0
    M_3 = 12.35 * 9.0
    D_3 = 10.0 * 9.0
    ra_3 = 0.0
    xd_3 = 0.3 * 100.0 / 900.0
    omega_ref_3 = 1.0
    Kp_3 = 0.0
    Ki_3 = 0.0

    fn_4 = 60.0
    M_4 = 12.35 * 9.0
    D_4 = 10.0 * 9.0
    ra_4 = 0.0
    xd_4 = 0.3 * 100.0 / 900.0
    omega_ref_4 = 1.0
    Kp_4 = 0.0
    Ki_4 = 0.0

    # Generators
    gen1 = Generator(
        name="Gen1", P=10.0, vset=1.03, Snom=900.0,
        x1=xd_1, r1=ra_1, freq=fn_1,
           )

    gen2 = Generator(
        name="Gen2", P=10.0, vset=1.01, Snom=900.0,
        x1=xd_2, r1=ra_2, freq=fn_2,

    )

    gen3 = Generator(
        name="Gen3", P=10.0, vset=1.03, Snom=900.0,
        x1=xd_3, r1=ra_3, freq=fn_3,

    )

    gen4 = Generator(
        name="Gen4", P=10.0, vset=1.01, Snom=900.0,
        x1=xd_4, r1=ra_4, freq=fn_4,

    )

    grid.add_load(bus=bus7, api_obj=load1)
    grid.add_load(bus=bus9, api_obj=load2)

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)

    grid.add_line(line0)
    grid.add_line(line1)
    grid.add_line(line2)
    grid.add_line(line3)
    grid.add_line(line4)
    grid.add_line(line5)
    grid.add_line(line6)
    grid.add_line(line7)
    grid.add_line(line8)
    grid.add_line(line9)
    grid.add_line(line10)
    grid.add_line(line11)
    grid.add_line(line12)
    grid.add_line(line13)
    grid.add_line(trafo_G1)
    grid.add_line(trafo_G2)
    grid.add_line(trafo_G3)
    grid.add_line(trafo_G4)

    gce.save_file(grid=grid, filename="kundur_static_grid.veragrid")




    ######################################################################################################
    # Build Rms models
    ######################################################################################################


    # Build rms models from template
    # generators
    genqec_mdl1 = get_complete_generator_template_rms(grid.var_factory).block
    genqec_mdl2 = get_complete_generator_template_rms(grid.var_factory).block
    genqec_mdl3 = get_complete_generator_template_rms(grid.var_factory).block
    genqec_mdl4 = get_complete_generator_template_rms(grid.var_factory).block

    # lines
    line0_mdl = get_line_rms_template(grid.var_factory).block
    line1_mdl = get_line_rms_template(grid.var_factory).block
    line2_mdl = get_line_rms_template(grid.var_factory).block
    line3_mdl = get_line_rms_template(grid.var_factory).block
    line4_mdl = get_line_rms_template(grid.var_factory).block
    line5_mdl = get_line_rms_template(grid.var_factory).block
    line6_mdl = get_line_rms_template(grid.var_factory).block
    line7_mdl = get_line_rms_template(grid.var_factory).block
    line8_mdl = get_line_rms_template(grid.var_factory).block
    line9_mdl = get_line_rms_template(grid.var_factory).block
    line10_mdl = get_line_rms_template(grid.var_factory).block
    line11_mdl = get_line_rms_template(grid.var_factory).block
    line12_mdl = get_line_rms_template(grid.var_factory).block
    line13_mdl = get_line_rms_template(grid.var_factory).block

    #trafos
    trafo1_mdl = get_line_rms_template(grid.var_factory).block
    trafo2_mdl = get_line_rms_template(grid.var_factory).block
    trafo3_mdl = get_line_rms_template(grid.var_factory).block
    trafo4_mdl = get_line_rms_template(grid.var_factory).block

    #loads
    load1_mdl = get_load_rms_template(grid.var_factory).block
    load2_mdl = get_load_rms_template(grid.var_factory).block

    # set models parameters
    load1_mdl.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
    load1_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)

    load2_mdl.set_parameter_in_model(var_name="Pl0", new_value=-0.0999999)
    load2_mdl.set_parameter_in_model(var_name="Ql0", new_value=-0.009999999862208533)


    # genqec_mdl1.connect([genqec_mdl1.in_vars[0]], [bus1.rms_model.out_vars[0]])
    # genqec_mdl1.connect([genqec_mdl1.in_vars[1]], [bus1.rms_model.out_vars[1]])
    #
    # genqec_mdl2.connect([genqec_mdl2.in_vars[0]], [bus2.rms_model.out_vars[0]])
    # genqec_mdl2.connect([genqec_mdl2.in_vars[1]], [bus2.rms_model.out_vars[1]])
    #
    # genqec_mdl3.connect([genqec_mdl3.in_vars[0]], [bus3.rms_model.out_vars[0]])
    # genqec_mdl3.connect([genqec_mdl3.in_vars[1]], [bus3.rms_model.out_vars[1]])
    #
    # genqec_mdl4.connect([genqec_mdl4.in_vars[0]], [bus4.rms_model.out_vars[0]])
    # genqec_mdl4.connect([genqec_mdl4.in_vars[1]], [bus4.rms_model.out_vars[1]])
    #
    #
    # line0_mdl.connect([line0_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    # line0_mdl.connect([line0_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])
    #
    # line0_mdl.connect([line0_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    # line0_mdl.connect([line0_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])
    #
    # line1_mdl.connect([line1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    # line1_mdl.connect([line1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])
    #
    # line1_mdl.connect([line1_mdl.in_vars[2]], [bus6.rms_model.out_vars[0]])
    # line1_mdl.connect([line1_mdl.in_vars[3]], [bus6.rms_model.out_vars[1]])
    #
    # line2_mdl.connect([line2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    # line2_mdl.connect([line2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])
    #
    # line2_mdl.connect([line2_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    # line2_mdl.connect([line2_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])
    #
    # line3_mdl.connect([line3_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    # line3_mdl.connect([line3_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])
    #
    # line3_mdl.connect([line3_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    # line3_mdl.connect([line3_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])
    #
    # line4_mdl.connect([line4_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    # line4_mdl.connect([line4_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])
    #
    # line4_mdl.connect([line4_mdl.in_vars[2]], [bus7.rms_model.out_vars[0]])
    # line4_mdl.connect([line4_mdl.in_vars[3]], [bus7.rms_model.out_vars[1]])
    #
    # line5_mdl.connect([line5_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    # line5_mdl.connect([line5_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])
    #
    # line5_mdl.connect([line5_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    # line5_mdl.connect([line5_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])
    #
    # line6_mdl.connect([line6_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    # line6_mdl.connect([line6_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])
    #
    # line6_mdl.connect([line6_mdl.in_vars[2]], [bus8.rms_model.out_vars[0]])
    # line6_mdl.connect([line6_mdl.in_vars[3]], [bus8.rms_model.out_vars[1]])
    #
    # line7_mdl.connect([line7_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    # line7_mdl.connect([line7_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])
    #
    # line7_mdl.connect([line7_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    # line7_mdl.connect([line7_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])
    #
    # line8_mdl.connect([line8_mdl.in_vars[0]], [bus8.rms_model.out_vars[0]])
    # line8_mdl.connect([line8_mdl.in_vars[1]], [bus8.rms_model.out_vars[1]])
    #
    # line8_mdl.connect([line8_mdl.in_vars[2]], [bus9.rms_model.out_vars[0]])
    # line8_mdl.connect([line8_mdl.in_vars[3]], [bus9.rms_model.out_vars[1]])
    #
    # line9_mdl.connect([line9_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    # line9_mdl.connect([line9_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])
    #
    # line9_mdl.connect([line9_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    # line9_mdl.connect([line9_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])
    #
    # line10_mdl.connect([line10_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    # line10_mdl.connect([line10_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])
    #
    # line10_mdl.connect([line10_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    # line10_mdl.connect([line10_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])
    #
    # line11_mdl.connect([line11_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    # line11_mdl.connect([line11_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])
    #
    # line11_mdl.connect([line11_mdl.in_vars[2]], [bus10.rms_model.out_vars[0]])
    # line11_mdl.connect([line11_mdl.in_vars[3]], [bus10.rms_model.out_vars[1]])
    #
    # line12_mdl.connect([line12_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    # line12_mdl.connect([line12_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])
    #
    # line12_mdl.connect([line12_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    # line12_mdl.connect([line12_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])
    #
    # line13_mdl.connect([line13_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    # line13_mdl.connect([line13_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])
    #
    # line13_mdl.connect([line13_mdl.in_vars[2]], [bus11.rms_model.out_vars[0]])
    # line13_mdl.connect([line13_mdl.in_vars[3]], [bus11.rms_model.out_vars[1]])
    #
    # trafo1_mdl.connect([trafo1_mdl.in_vars[0]], [bus5.rms_model.out_vars[0]])
    # trafo1_mdl.connect([trafo1_mdl.in_vars[1]], [bus5.rms_model.out_vars[1]])
    #
    # trafo1_mdl.connect([trafo1_mdl.in_vars[2]], [bus1.rms_model.out_vars[0]])
    # trafo1_mdl.connect([trafo1_mdl.in_vars[3]], [bus1.rms_model.out_vars[1]])
    #
    # trafo2_mdl.connect([trafo2_mdl.in_vars[0]], [bus6.rms_model.out_vars[0]])
    # trafo2_mdl.connect([trafo2_mdl.in_vars[1]], [bus6.rms_model.out_vars[1]])
    #
    # trafo2_mdl.connect([trafo2_mdl.in_vars[2]], [bus2.rms_model.out_vars[0]])
    # trafo2_mdl.connect([trafo2_mdl.in_vars[3]], [bus2.rms_model.out_vars[1]])
    #
    # trafo3_mdl.connect([trafo3_mdl.in_vars[0]], [bus11.rms_model.out_vars[0]])
    # trafo3_mdl.connect([trafo3_mdl.in_vars[1]], [bus11.rms_model.out_vars[1]])
    #
    # trafo3_mdl.connect([trafo3_mdl.in_vars[2]], [bus3.rms_model.out_vars[0]])
    # trafo3_mdl.connect([trafo3_mdl.in_vars[3]], [bus3.rms_model.out_vars[1]])
    #
    # trafo4_mdl.connect([trafo4_mdl.in_vars[0]], [bus10.rms_model.out_vars[0]])
    # trafo4_mdl.connect([trafo4_mdl.in_vars[1]], [bus10.rms_model.out_vars[1]])
    #
    # trafo4_mdl.connect([trafo4_mdl.in_vars[2]], [bus4.rms_model.out_vars[0]])
    # trafo4_mdl.connect([trafo4_mdl.in_vars[3]], [bus4.rms_model.out_vars[1]])
    #
    #
    #
    # load1_mdl.connect([load1_mdl.in_vars[0]], [bus7.rms_model.out_vars[0]])
    # load1_mdl.connect([load1_mdl.in_vars[1]], [bus7.rms_model.out_vars[1]])
    #
    # load2_mdl.connect([load2_mdl.in_vars[0]], [bus9.rms_model.out_vars[0]])
    # load2_mdl.connect([load2_mdl.in_vars[1]], [bus9.rms_model.out_vars[1]])

    # Attach RMS models through the standard helper so model wiring and device
    # ownership follow the same path used by RMS tests and the GUI scripting flow.
    set_rms_model(device=gen1, model=genqec_mdl1, var_factory=grid.var_factory)
    set_rms_model(device=gen2, model=genqec_mdl2, var_factory=grid.var_factory)
    set_rms_model(device=gen3, model=genqec_mdl3, var_factory=grid.var_factory)
    set_rms_model(device=gen4, model=genqec_mdl4, var_factory=grid.var_factory)

    set_rms_model(device=line0, model=line0_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line1, model=line1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line2, model=line2_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line3, model=line3_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line4, model=line4_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line5, model=line5_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line6, model=line6_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line7, model=line7_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line8, model=line8_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line9, model=line9_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line10, model=line10_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line11, model=line11_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line12, model=line12_mdl, var_factory=grid.var_factory)
    set_rms_model(device=line13, model=line13_mdl, var_factory=grid.var_factory)

    set_rms_model(device=trafo_G1, model=trafo1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G2, model=trafo2_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G3, model=trafo3_mdl, var_factory=grid.var_factory)
    set_rms_model(device=trafo_G4, model=trafo4_mdl, var_factory=grid.var_factory)

    set_rms_model(device=load1, model=load1_mdl, var_factory=grid.var_factory)
    set_rms_model(device=load2, model=load2_mdl, var_factory=grid.var_factory)

    # grid.add_line(line0)
    # grid.add_line(line1)
    # grid.add_line(line2)
    # grid.add_line(line3)
    # grid.add_line(line4)
    # grid.add_line(line5)
    # grid.add_line(line6)
    # grid.add_line(line7)
    # grid.add_line(line8)
    # grid.add_line(line9)
    # grid.add_line(line10)
    # grid.add_line(line11)
    # grid.add_line(line12)
    # grid.add_line(line13)
    # grid.add_line(trafo_G1)
    # grid.add_line(trafo_G2)
    # grid.add_line(trafo_G3)
    # grid.add_line(trafo_G4)
    #
    # grid.add_load(bus=bus7, api_obj=load1)
    # grid.add_load(bus=bus9, api_obj=load2)
    #
    # grid.add_generator(bus=bus1, api_obj=gen1)
    # grid.add_generator(bus=bus2, api_obj=gen2)
    # grid.add_generator(bus=bus3, api_obj=gen3)
    # grid.add_generator(bus=bus4, api_obj=gen4)

    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver(grid, pf_options)
    power_flow.run()
    res = power_flow.results
    print(f"Converged: {res.converged}")

    # pr.enable()

    options = RmsOptions(time_step=0.001,
                         simulation_time=20,
                         tolerance=1e-6,
                         integration_method=DynamicIntegrationMethod.DaeBackEuler,
                         initialization_method=RmsInitializationMethod.Explicit,
                         use_init_values=False,
                         max_iter=1000,
                         verbose=0)
    # RmsSimulationDriver executes one trajectory per active RMS event group.
    # This benchmark has no disturbance, so create one empty active group that
    # represents the nominal/base-case simulation. Without it the driver builds
    # the RMS problem but never enters the time-integration loop.
    if len(grid.rms_events_groups) == 0:
        grid.rms_events_groups.append(
            RmsEventsGroup(name="Base case", active=True)
        )

    active_rms_groups = [
        group.name
        for group in grid.rms_events_groups
        if group.active
    ]
    print(f"Active RMS event groups: {active_rms_groups}")

    total_simulation_time: float = 0.0
    t0 = time.perf_counter()

    driver: RmsSimulationDriver = RmsSimulationDriver(grid=grid, options=options, pf_results=res)
    driver.run()

    total_simulation_time += time.perf_counter() - t0
    print(f"total simulation time: {total_simulation_time}")



    ######################################################################################################
    # RMS diagnostic plots
    ######################################################################################################

    if driver.results is None:
        raise RuntimeError("RMS simulation finished without a results object.")

    if driver.problem is None:
        raise RuntimeError("RMS simulation finished without a compiled RMS problem.")

    active_group_indices = np.flatnonzero(driver.results.has_event_group_results)

    if active_group_indices.size == 0:
        raise RuntimeError(
            "No active RMS event group produced simulation results. "
            f"Declared groups={list(driver.results.rms_events_group_names)}"
        )

    print(
        "RMS group status: "
        f"has_results={driver.results.has_event_group_results}, "
        f"well_initialized={driver.results.well_initialized}, "
        f"converged={driver.results.converged}"
    )

    # Plot the first active event group. This is the standard scripting case for
    # this Kundur example; if more event groups are added later, changing this
    # index is enough to inspect another case.
    group_idx = int(active_group_indices[0])
    y = driver.results.values[:, :, group_idx]
    t = np.arange(y.shape[0], dtype=float) * options.time_step
    problem = driver.problem

    print(
        f"Plotting RMS event group {group_idx}: "
        f"{driver.results.rms_events_group_names[group_idx]}"
    )

    generators = [gen1, gen2, gen3, gen4]
    generator_models = {
        gen1.name: genqec_mdl1,
        gen2.name: genqec_mdl2,
        gen3.name: genqec_mdl3,
        gen4.name: genqec_mdl4,
    }

    def get_required_series(block: Block, var_name: str, owner_name: str) -> np.ndarray:
        """
        Return one simulated RMS variable and fail explicitly if it is absent.

        :param block: RMS model hierarchy to inspect.
        :param var_name: Symbolic variable name.
        :param owner_name: Device name used in the error message.
        :return: Time series from the selected RMS event group.
        """
        var = find_name_in_block(var_name, block)

        if var is None:
            raise KeyError(
                f"Variable '{var_name}' was not found in the RMS model of '{owner_name}'."
            )

        return y[:, problem.get_var_idx(var)]

    def get_bus_series(bus: Bus, var_name: str) -> np.ndarray:
        """
        Return one bus RMS variable, normally Vm or Va.

        :param bus: Bus whose RMS shell is inspected.
        :param var_name: Symbolic bus variable name.
        :return: Time series from the selected RMS event group.
        """
        return get_required_series(
            block=bus.rms_model,
            var_name=var_name,
            owner_name=bus.name,
        )

    # ----------------------------------------------------------------------------------
    # 1. Bus voltage magnitudes
    # ----------------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(12, 6))

    for bus in [bus1, bus2, bus3, bus4, bus7, bus8, bus9]:
        vm = get_bus_series(bus=bus, var_name="Vm")
        ax.plot(t, vm, label=bus.name)

    ax.set_title("Kundur RMS bus voltage magnitudes")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Voltage magnitude [p.u.]")
    ax.grid(True)
    ax.legend(ncol=2)
    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 2. Bus voltage angles relative to the slack bus
    # ----------------------------------------------------------------------------------

    fig, ax = plt.subplots(figsize=(12, 6))

    va_ref = get_bus_series(bus=bus3, var_name="Va")

    for bus in [bus1, bus2, bus4, bus7, bus8, bus9]:
        va = get_bus_series(bus=bus, var_name="Va")
        ax.plot(
            t,
            np.rad2deg(va - va_ref),
            label=f"{bus.name} - Bus3",
        )

    ax.set_title("Kundur RMS bus voltage angles relative to Bus3")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Relative voltage angle [deg]")
    ax.grid(True)
    ax.legend(ncol=2)
    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 3. Generator frequency deviations
    # ----------------------------------------------------------------------------------

    omega_by_generator: dict[str, np.ndarray] = {}

    fig, ax = plt.subplots(figsize=(12, 6))

    for generator in generators:
        model = generator_models[generator.name]
        omega = get_required_series(
            block=model,
            var_name="omega",
            owner_name=generator.name,
        )
        omega_by_generator[generator.name] = omega

        frequency_deviation_hz = (omega - 1.0) * generator.freq
        ax.plot(t, frequency_deviation_hz, label=generator.name)

    ax.set_title("Generator frequency deviation")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Δf [Hz]")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 4. Rotor-angle dynamics and the Kundur inter-area coordinate
    # ----------------------------------------------------------------------------------

    delta_by_generator: dict[str, np.ndarray] = {}

    for generator in generators:
        model = generator_models[generator.name]
        delta_by_generator[generator.name] = get_required_series(
            block=model,
            var_name="delta",
            owner_name=generator.name,
        )

    delta_ref = delta_by_generator["Gen3"]

    fig, ax = plt.subplots(figsize=(12, 6))

    for generator in generators:
        if generator.name == "Gen3":
            continue

        relative_delta = delta_by_generator[generator.name] - delta_ref
        relative_delta_deviation_deg = np.rad2deg(
            relative_delta - relative_delta[0]
        )

        ax.plot(
            t,
            relative_delta_deviation_deg,
            label=f"{generator.name} - Gen3",
        )

    # Characteristic Kundur inter-area coordinate:
    # average machines 1-2 against average machines 3-4.
    delta_area_1 = 0.5 * (
        delta_by_generator["Gen1"] + delta_by_generator["Gen2"]
    )
    delta_area_2 = 0.5 * (
        delta_by_generator["Gen3"] + delta_by_generator["Gen4"]
    )
    inter_area_delta = delta_area_1 - delta_area_2
    inter_area_delta_deviation_deg = np.rad2deg(
        inter_area_delta - inter_area_delta[0]
    )

    ax.plot(
        t,
        inter_area_delta_deviation_deg,
        linewidth=2.0,
        label="Area 1 avg - Area 2 avg",
    )

    ax.set_title("Rotor-angle deviations")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Relative rotor-angle deviation [deg]")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 5. Generator active and reactive powers
    # ----------------------------------------------------------------------------------

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    for generator in generators:
        model = generator_models[generator.name]

        pg = get_required_series(
            block=model,
            var_name="Pg",
            owner_name=generator.name,
        )
        qg = get_required_series(
            block=model,
            var_name="Qg",
            owner_name=generator.name,
        )

        axes[0].plot(t, pg, label=generator.name)
        axes[1].plot(t, qg, label=generator.name)

    axes[0].set_title("Generator electrical active power")
    axes[0].set_ylabel("Pg [p.u.]")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].set_title("Generator electrical reactive power")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Qg [p.u.]")
    axes[1].grid(True)
    axes[1].legend()

    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 6. Mechanical versus electrical torque
    # ----------------------------------------------------------------------------------

    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)
    axes_flat = axes.ravel()

    for ax, generator in zip(axes_flat, generators):
        model = generator_models[generator.name]

        tm = get_required_series(
            block=model,
            var_name="Tm",
            owner_name=generator.name,
        )
        te = get_required_series(
            block=model,
            var_name="Te",
            owner_name=generator.name,
        )

        ax.plot(t, tm, label="Tm")
        ax.plot(t, te, label="Te")
        ax.set_title(generator.name)
        ax.set_ylabel("Torque [p.u.]")
        ax.grid(True)
        ax.legend()

    for ax in axes[-1, :]:
        ax.set_xlabel("Time [s]")

    fig.suptitle("Generator mechanical and electrical torque")
    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 7. Excitation system and PSS
    # ----------------------------------------------------------------------------------

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    for generator in generators:
        model = generator_models[generator.name]

        vf = get_required_series(
            block=model,
            var_name="Vf",
            owner_name=generator.name,
        )
        ir_pu = get_required_series(
            block=model,
            var_name="IRPu",
            owner_name=generator.name,
        )
        v_pss = get_required_series(
            block=model,
            var_name="V_pss",
            owner_name=generator.name,
        )

        axes[0].plot(t, vf, label=generator.name)
        axes[1].plot(t, ir_pu, label=generator.name)
        axes[2].plot(t, v_pss, label=generator.name)

    axes[0].set_title("Exciter field voltage")
    axes[0].set_ylabel("Vf [p.u.]")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].set_title("Generator field-current signal")
    axes[1].set_ylabel("IRPu [p.u.]")
    axes[1].grid(True)
    axes[1].legend()

    axes[2].set_title("Power-system stabilizer output")
    axes[2].set_xlabel("Time [s]")
    axes[2].set_ylabel("Vpss [p.u.]")
    axes[2].grid(True)
    axes[2].legend()

    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 8. Detailed d-q variables of Gen1
    # ----------------------------------------------------------------------------------

    id_gen1 = get_required_series(
        block=genqec_mdl1,
        var_name="Id",
        owner_name=gen1.name,
    )
    iq_gen1 = get_required_series(
        block=genqec_mdl1,
        var_name="Iq",
        owner_name=gen1.name,
    )
    vd_gen1 = get_required_series(
        block=genqec_mdl1,
        var_name="Vd",
        owner_name=gen1.name,
    )
    vq_gen1 = get_required_series(
        block=genqec_mdl1,
        var_name="Vq",
        owner_name=gen1.name,
    )

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(t, id_gen1, label="Id")
    axes[0].plot(t, iq_gen1, label="Iq")
    axes[0].set_title("Gen1 d-q currents")
    axes[0].set_ylabel("Current [p.u.]")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(t, vd_gen1, label="Vd")
    axes[1].plot(t, vq_gen1, label="Vq")
    axes[1].set_title("Gen1 d-q voltages")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Voltage [p.u.]")
    axes[1].grid(True)
    axes[1].legend()

    fig.tight_layout()

    # ----------------------------------------------------------------------------------
    # 9. Inter-area 7-8 corridor active and reactive power
    # ----------------------------------------------------------------------------------

    pf_78_1 = get_required_series(
        block=line5_mdl,
        var_name="Pf",
        owner_name=line5.name,
    )
    pf_78_2 = get_required_series(
        block=line6_mdl,
        var_name="Pf",
        owner_name=line6.name,
    )
    qf_78_1 = get_required_series(
        block=line5_mdl,
        var_name="Qf",
        owner_name=line5.name,
    )
    qf_78_2 = get_required_series(
        block=line6_mdl,
        var_name="Qf",
        owner_name=line6.name,
    )

    p_78_total = pf_78_1 + pf_78_2
    q_78_total = qf_78_1 + qf_78_2

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    axes[0].plot(t, pf_78_1, label=line5.name)
    axes[0].plot(t, pf_78_2, label=line6.name)
    axes[0].plot(
        t,
        p_78_total,
        linewidth=2.0,
        label="Total 7-8 corridor",
    )
    axes[0].set_title("Inter-area active-power transfer")
    axes[0].set_ylabel("Pf [p.u.]")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(t, qf_78_1, label=line5.name)
    axes[1].plot(t, qf_78_2, label=line6.name)
    axes[1].plot(
        t,
        q_78_total,
        linewidth=2.0,
        label="Total 7-8 corridor",
    )
    axes[1].set_title("Inter-area reactive-power transfer")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Qf [p.u.]")
    axes[1].grid(True)
    axes[1].legend()

    fig.tight_layout()

    print("Generating Kundur RMS diagnostic plots...")
    plt.show(block=False)


if __name__ == '__main__':
    rms_kundur()
