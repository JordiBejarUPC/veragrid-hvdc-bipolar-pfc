

from __future__ import annotations

import cProfile as profile

import numpy as np

from matplotlib import pyplot as plt

from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Dynamic.dynamic_model_host import DynamicModelHost
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Branches.line import Line

from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration

from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template

from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template

from VeraGridEngine.Templates.Rms.load1_rms_template import get_load1_rms_template
from VeraGridEngine.Templates.Rms.load2_rms_template import get_load2_rms_template

from VeraGridEngine.Simulations.SmallSignalStability.small_signal_driver import SmallSignalStabilityDriver
from VeraGridEngine.Simulations.SmallSignalStability.small_signal_options import SmallSignalStabilityOptions

from VeraGridEngine.Utils.Symbolic import Block
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowDriver
import VeraGridEngine.api as gce
from VeraGridEngine.Utils.Symbolic.symbolic_io import block_deep_copy

pr = profile.Profile()
pr.disable()

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars + list(block.event_dict.keys()):
        if name == var.name:
            return var

    for mdl in block.children:
        res = find_name_in_block(name, mdl)
        if res is not None:
            return res


def rms_kundur_small_signal():
    ###########################################################################################################################
    # Build VeraGrid object
    ###########################################################################################################################


    grid = gce.MultiCircuit()

    # Buses
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


    bus1.initialize_rms()
    bus2.initialize_rms()
    bus3.initialize_rms()
    bus4.initialize_rms()
    bus5.initialize_rms()
    bus6.initialize_rms()
    bus7.initialize_rms()
    bus8.initialize_rms()
    bus9.initialize_rms()
    bus10.initialize_rms()
    bus11.initialize_rms()

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

    # Line

    line0 = gce.Line(name="line 5-6-1", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0)


    line1 = gce.Line(name="line 5-6-2", bus_from=bus5, bus_to=bus6,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0)


    line2 = gce.Line(name="line 6-7-1", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line3 = gce.Line(name="line 6-7-2", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line4 = gce.Line(name="line 6-7-3", bus_from=bus6, bus_to=bus7,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line5 = gce.Line(name="line 7-8-1", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0)


    line6 = gce.Line(name="line 7-8-2", bus_from=bus7, bus_to=bus8,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0)


    line7 = gce.Line(name="line 8-9-1", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0)


    line8 = gce.Line(name="line 8-9-2", bus_from=bus8, bus_to=bus9,
             r=0.01100, x=0.11000, b=0.19250, rate=400.0)


    line9 = gce.Line(name="line 9-10-1", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line10 = gce.Line(name="line 9-10-2", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line11 = gce.Line(name="line 9-10-3", bus_from=bus9, bus_to=bus10,
             r=0.00300, x=0.03000, b=0.00583, rate=700.0)


    line12 = gce.Line(name="line 10-11-1", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0)


    line13 = gce.Line(name="line 10-11-2", bus_from=bus10, bus_to=bus11,
             r=0.00500, x=0.05000, b=0.02187, rate=750.0)


    # Transformers
    xt1 = 0.15 * (100.0 / 900.0)
    trafo_G1 = Line(name="trafo 5-1", bus_from=bus5, bus_to=bus1,
             r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)


    trafo_G2 = gce.Line(name="trafo 6-2", bus_from=bus6, bus_to=bus2,
             r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)


    trafo_G3 = gce.Line(name="trafo 11-3", bus_from=bus11, bus_to=bus3,
             r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)


    trafo_G4 = gce.Line(name="trafo 10-4", bus_from=bus10, bus_to=bus4,
             r=0.00000, x=0.15 * (100.0 / 900.0), b=0.0, rate=900.0)


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
        tm0=6.999999999999999,
        vf=1.1410480598099169,
        M=M_1, D=D_1,
        omega_ref=omega_ref_1,
        Kp=Kp_1, Ki=Ki_1
    )

    gen2 = Generator(
        name="Gen2", P=10.0, vset=1.01, Snom=900.0,
        x1=xd_2, r1=ra_2, freq=fn_2,
        tm0=6.999999999999998,
        vf=1.1801018702912192,
        M=M_2, D=D_2,
        omega_ref=omega_ref_2,
        Kp=Kp_2, Ki=Ki_2
    )

    gen3 = Generator(
        name="Gen3", P=10.0, vset=1.03, Snom=900.0,
        x1=xd_3, r1=ra_3, freq=fn_3,
        tm0=7.331838148595014,
        vf=1.15513088317088697,
        M=M_3, D=D_3,
        omega_ref=omega_ref_3,
        Kp=Kp_3, Ki=Ki_3
    )

    gen4 = Generator(
        name="Gen4", P=10.0, vset=1.01, Snom=900.0,
        x1=xd_4, r1=ra_4, freq=fn_4,
        tm0=6.999999999999998,
        vf=1.2028207647478641,
        M=M_4, D=D_4,
        omega_ref=omega_ref_4,
        Kp=Kp_4, Ki=Ki_4
    )



    ######################################################################################################
    # Build Rms models
    ######################################################################################################

    # Build dynamic_model_host

    gen1_dynhost = DynamicModelHost()
    gen2_dynhost = DynamicModelHost()
    gen3_dynhost = DynamicModelHost()
    gen4_dynhost = DynamicModelHost()

    line0_dynhost = DynamicModelHost()
    line1_dynhost = DynamicModelHost()
    line2_dynhost = DynamicModelHost()
    line3_dynhost = DynamicModelHost()
    line4_dynhost = DynamicModelHost()
    line5_dynhost = DynamicModelHost()
    line6_dynhost = DynamicModelHost()
    line7_dynhost = DynamicModelHost()
    line8_dynhost = DynamicModelHost()
    line9_dynhost = DynamicModelHost()
    line10_dynhost = DynamicModelHost()
    line11_dynhost = DynamicModelHost()
    line12_dynhost = DynamicModelHost()
    line13_dynhost = DynamicModelHost()

    trafo1_dynhost = DynamicModelHost()
    trafo2_dynhost = DynamicModelHost()
    trafo3_dynhost = DynamicModelHost()
    trafo4_dynhost = DynamicModelHost()

    load1_dynhost = DynamicModelHost()
    load2_dynhost = DynamicModelHost()

    # Build rms models from template
    # generators
    genrow_mdl1 = get_complete_generator_template(grid.var_factory).block
    genrow_mdl2 = get_complete_generator_template(grid.var_factory).block
    genrow_mdl3 = get_complete_generator_template(grid.var_factory).block
    genrow_mdl4 = get_complete_generator_template(grid.var_factory).block

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
    load1_mdl = get_load1_rms_template(grid.var_factory).block
    load2_mdl = get_load2_rms_template(grid.var_factory).block

    # connection with buses

    genrow_mdl1.connect([genrow_mdl1.in_vars[0]], [bus1.rms_model.model.out_vars[0]])
    genrow_mdl1.connect([genrow_mdl1.in_vars[1]], [bus1.rms_model.model.out_vars[1]])

    genrow_mdl2.connect([genrow_mdl2.in_vars[0]], [bus2.rms_model.model.out_vars[0]])
    genrow_mdl2.connect([genrow_mdl2.in_vars[1]], [bus2.rms_model.model.out_vars[1]])

    genrow_mdl3.connect([genrow_mdl3.in_vars[0]], [bus3.rms_model.model.out_vars[0]])
    genrow_mdl3.connect([genrow_mdl3.in_vars[1]], [bus3.rms_model.model.out_vars[1]])

    genrow_mdl4.connect([genrow_mdl4.in_vars[0]], [bus4.rms_model.model.out_vars[0]])
    genrow_mdl4.connect([genrow_mdl4.in_vars[1]], [bus4.rms_model.model.out_vars[1]])


    line0_mdl.connect([line0_mdl.in_vars[0]], [bus5.rms_model.model.out_vars[0]])
    line0_mdl.connect([line0_mdl.in_vars[1]], [bus5.rms_model.model.out_vars[1]])

    line0_mdl.connect([line0_mdl.in_vars[2]], [bus6.rms_model.model.out_vars[0]])
    line0_mdl.connect([line0_mdl.in_vars[3]], [bus6.rms_model.model.out_vars[1]])

    line1_mdl.connect([line1_mdl.in_vars[0]], [bus5.rms_model.model.out_vars[0]])
    line1_mdl.connect([line1_mdl.in_vars[1]], [bus5.rms_model.model.out_vars[1]])

    line1_mdl.connect([line1_mdl.in_vars[2]], [bus6.rms_model.model.out_vars[0]])
    line1_mdl.connect([line1_mdl.in_vars[3]], [bus6.rms_model.model.out_vars[1]])

    line2_mdl.connect([line2_mdl.in_vars[0]], [bus6.rms_model.model.out_vars[0]])
    line2_mdl.connect([line2_mdl.in_vars[1]], [bus6.rms_model.model.out_vars[1]])

    line2_mdl.connect([line2_mdl.in_vars[2]], [bus7.rms_model.model.out_vars[0]])
    line2_mdl.connect([line2_mdl.in_vars[3]], [bus7.rms_model.model.out_vars[1]])

    line3_mdl.connect([line3_mdl.in_vars[0]], [bus6.rms_model.model.out_vars[0]])
    line3_mdl.connect([line3_mdl.in_vars[1]], [bus6.rms_model.model.out_vars[1]])

    line3_mdl.connect([line3_mdl.in_vars[2]], [bus7.rms_model.model.out_vars[0]])
    line3_mdl.connect([line3_mdl.in_vars[3]], [bus7.rms_model.model.out_vars[1]])

    line4_mdl.connect([line4_mdl.in_vars[0]], [bus6.rms_model.model.out_vars[0]])
    line4_mdl.connect([line4_mdl.in_vars[1]], [bus6.rms_model.model.out_vars[1]])

    line4_mdl.connect([line4_mdl.in_vars[2]], [bus7.rms_model.model.out_vars[0]])
    line4_mdl.connect([line4_mdl.in_vars[3]], [bus7.rms_model.model.out_vars[1]])

    line5_mdl.connect([line5_mdl.in_vars[0]], [bus7.rms_model.model.out_vars[0]])
    line5_mdl.connect([line5_mdl.in_vars[1]], [bus7.rms_model.model.out_vars[1]])

    line5_mdl.connect([line5_mdl.in_vars[2]], [bus8.rms_model.model.out_vars[0]])
    line5_mdl.connect([line5_mdl.in_vars[3]], [bus8.rms_model.model.out_vars[1]])

    line6_mdl.connect([line6_mdl.in_vars[0]], [bus7.rms_model.model.out_vars[0]])
    line6_mdl.connect([line6_mdl.in_vars[1]], [bus7.rms_model.model.out_vars[1]])

    line6_mdl.connect([line6_mdl.in_vars[2]], [bus8.rms_model.model.out_vars[0]])
    line6_mdl.connect([line6_mdl.in_vars[3]], [bus8.rms_model.model.out_vars[1]])

    line7_mdl.connect([line7_mdl.in_vars[0]], [bus8.rms_model.model.out_vars[0]])
    line7_mdl.connect([line7_mdl.in_vars[1]], [bus8.rms_model.model.out_vars[1]])

    line7_mdl.connect([line7_mdl.in_vars[2]], [bus9.rms_model.model.out_vars[0]])
    line7_mdl.connect([line7_mdl.in_vars[3]], [bus9.rms_model.model.out_vars[1]])

    line8_mdl.connect([line8_mdl.in_vars[0]], [bus8.rms_model.model.out_vars[0]])
    line8_mdl.connect([line8_mdl.in_vars[1]], [bus8.rms_model.model.out_vars[1]])

    line8_mdl.connect([line8_mdl.in_vars[2]], [bus9.rms_model.model.out_vars[0]])
    line8_mdl.connect([line8_mdl.in_vars[3]], [bus9.rms_model.model.out_vars[1]])

    line9_mdl.connect([line9_mdl.in_vars[0]], [bus9.rms_model.model.out_vars[0]])
    line9_mdl.connect([line9_mdl.in_vars[1]], [bus9.rms_model.model.out_vars[1]])

    line9_mdl.connect([line9_mdl.in_vars[2]], [bus10.rms_model.model.out_vars[0]])
    line9_mdl.connect([line9_mdl.in_vars[3]], [bus10.rms_model.model.out_vars[1]])

    line10_mdl.connect([line10_mdl.in_vars[0]], [bus9.rms_model.model.out_vars[0]])
    line10_mdl.connect([line10_mdl.in_vars[1]], [bus9.rms_model.model.out_vars[1]])

    line10_mdl.connect([line10_mdl.in_vars[2]], [bus10.rms_model.model.out_vars[0]])
    line10_mdl.connect([line10_mdl.in_vars[3]], [bus10.rms_model.model.out_vars[1]])

    line11_mdl.connect([line11_mdl.in_vars[0]], [bus9.rms_model.model.out_vars[0]])
    line11_mdl.connect([line11_mdl.in_vars[1]], [bus9.rms_model.model.out_vars[1]])

    line11_mdl.connect([line11_mdl.in_vars[2]], [bus10.rms_model.model.out_vars[0]])
    line11_mdl.connect([line11_mdl.in_vars[3]], [bus10.rms_model.model.out_vars[1]])

    line12_mdl.connect([line12_mdl.in_vars[0]], [bus10.rms_model.model.out_vars[0]])
    line12_mdl.connect([line12_mdl.in_vars[1]], [bus10.rms_model.model.out_vars[1]])

    line12_mdl.connect([line12_mdl.in_vars[2]], [bus11.rms_model.model.out_vars[0]])
    line12_mdl.connect([line12_mdl.in_vars[3]], [bus11.rms_model.model.out_vars[1]])

    line13_mdl.connect([line13_mdl.in_vars[0]], [bus10.rms_model.model.out_vars[0]])
    line13_mdl.connect([line13_mdl.in_vars[1]], [bus10.rms_model.model.out_vars[1]])

    line13_mdl.connect([line13_mdl.in_vars[2]], [bus11.rms_model.model.out_vars[0]])
    line13_mdl.connect([line13_mdl.in_vars[3]], [bus11.rms_model.model.out_vars[1]])

    trafo1_mdl.connect([trafo1_mdl.in_vars[0]], [bus5.rms_model.model.out_vars[0]])
    trafo1_mdl.connect([trafo1_mdl.in_vars[1]], [bus5.rms_model.model.out_vars[1]])

    trafo1_mdl.connect([trafo1_mdl.in_vars[2]], [bus1.rms_model.model.out_vars[0]])
    trafo1_mdl.connect([trafo1_mdl.in_vars[3]], [bus1.rms_model.model.out_vars[1]])

    trafo2_mdl.connect([trafo2_mdl.in_vars[0]], [bus6.rms_model.model.out_vars[0]])
    trafo2_mdl.connect([trafo2_mdl.in_vars[1]], [bus6.rms_model.model.out_vars[1]])

    trafo2_mdl.connect([trafo2_mdl.in_vars[2]], [bus2.rms_model.model.out_vars[0]])
    trafo2_mdl.connect([trafo2_mdl.in_vars[3]], [bus2.rms_model.model.out_vars[1]])

    trafo3_mdl.connect([trafo3_mdl.in_vars[0]], [bus11.rms_model.model.out_vars[0]])
    trafo3_mdl.connect([trafo3_mdl.in_vars[1]], [bus11.rms_model.model.out_vars[1]])

    trafo3_mdl.connect([trafo3_mdl.in_vars[2]], [bus3.rms_model.model.out_vars[0]])
    trafo3_mdl.connect([trafo3_mdl.in_vars[3]], [bus3.rms_model.model.out_vars[1]])

    trafo4_mdl.connect([trafo4_mdl.in_vars[0]], [bus10.rms_model.model.out_vars[0]])
    trafo4_mdl.connect([trafo4_mdl.in_vars[1]], [bus10.rms_model.model.out_vars[1]])

    trafo4_mdl.connect([trafo4_mdl.in_vars[2]], [bus4.rms_model.model.out_vars[0]])
    trafo4_mdl.connect([trafo4_mdl.in_vars[3]], [bus4.rms_model.model.out_vars[1]])



    load1_mdl.connect([load1_mdl.in_vars[0]], [bus7.rms_model.model.out_vars[0]])
    load1_mdl.connect([load1_mdl.in_vars[1]], [bus7.rms_model.model.out_vars[1]])

    load2_mdl.connect([load2_mdl.in_vars[0]], [bus9.rms_model.model.out_vars[0]])
    load2_mdl.connect([load2_mdl.in_vars[1]], [bus9.rms_model.model.out_vars[1]])

    # external mapping

    big_gen1 = Block(children=[genrow_mdl1])
    big_gen2 = Block(children=[genrow_mdl2])
    big_gen3 = Block(children=[genrow_mdl3])
    big_gen4 = Block(children=[genrow_mdl4])

    big_gen1.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl1.out_vars[0]})
    big_gen1.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl1.out_vars[1]})

    big_gen2.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl2.out_vars[0]})
    big_gen2.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl2.out_vars[1]})

    big_gen3.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl3.out_vars[0]})
    big_gen3.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl3.out_vars[1]})

    big_gen4.external_mapping.update({VarPowerFlowRefferenceType.P: genrow_mdl4.out_vars[0]})
    big_gen4.external_mapping.update({VarPowerFlowRefferenceType.Q: genrow_mdl4.out_vars[1]})

    # add models to dyn_host

    gen1_dynhost.model = big_gen1
    gen2_dynhost.model = big_gen2
    gen3_dynhost.model = big_gen3
    gen4_dynhost.model = big_gen4

    line0_dynhost.model = line0_mdl
    line1_dynhost.model = line1_mdl
    line2_dynhost.model = line2_mdl
    line3_dynhost.model = line3_mdl
    line4_dynhost.model = line4_mdl
    line5_dynhost.model = line5_mdl
    line6_dynhost.model = line6_mdl
    line7_dynhost.model = line7_mdl
    line8_dynhost.model = line8_mdl
    line9_dynhost.model = line9_mdl
    line10_dynhost.model = line10_mdl
    line11_dynhost.model = line11_mdl
    line12_dynhost.model = line12_mdl
    line13_dynhost.model = line13_mdl

    trafo1_dynhost.model = trafo1_mdl
    trafo2_dynhost.model = trafo2_mdl
    trafo3_dynhost.model = trafo3_mdl
    trafo4_dynhost.model = trafo4_mdl

    load1_dynhost.model = load1_mdl
    load2_dynhost.model = load2_mdl


    # attach rms models to Veragrid objects
    gen1.rms_model = gen1_dynhost
    gen2.rms_model = gen2_dynhost
    gen3.rms_model = gen3_dynhost
    gen4.rms_model = gen4_dynhost

    line0.rms_model = line0_dynhost
    line1.rms_model = line1_dynhost
    line2.rms_model = line2_dynhost
    line3.rms_model = line3_dynhost
    line4.rms_model = line4_dynhost
    line5.rms_model = line5_dynhost
    line6.rms_model = line6_dynhost
    line7.rms_model = line7_dynhost
    line8.rms_model = line8_dynhost
    line9.rms_model = line9_dynhost
    line10.rms_model = line10_dynhost
    line11.rms_model = line11_dynhost
    line12.rms_model = line12_dynhost
    line13.rms_model = line13_dynhost

    trafo_G1.rms_model = trafo1_dynhost
    trafo_G2.rms_model = trafo2_dynhost
    trafo_G3.rms_model = trafo3_dynhost
    trafo_G4.rms_model = trafo4_dynhost

    load1.rms_model = load1_dynhost
    load2.rms_model = load2_dynhost

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

    grid.add_load(bus=bus7, api_obj=load1)
    grid.add_load(bus=bus9, api_obj=load2)

    grid.add_generator(bus=bus1, api_obj=gen1)
    grid.add_generator(bus=bus2, api_obj=gen2)
    grid.add_generator(bus=bus3, api_obj=gen3)
    grid.add_generator(bus=bus4, api_obj=gen4)

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

    pr.enable()

    rms_options = RmsOptions(time_step=0.001,
                 simulation_time=10,
                 tolerance=1e-6,
                 integration_method=DynamicIntegrationMethod.BackEuler,
                 initialization_method=RmsInitializationMethod.Explicit,
                 use_init_values=False,
                 max_iter=1000,
                 verbose=0)

    problem = RmsProblemDae(grid=grid,
                            options=rms_options,
                            pf_results=res)

    ss_options = SmallSignalStabilityOptions(ss_assessment_time=0)

    problem = RmsProblemDae(grid=grid,
                            options=rms_options,
                            pf_results=res)

    small_signal_driver = SmallSignalStabilityDriver(grid=grid,
                                                     problem=problem,
                                                     rms_options=rms_options,
                                                     ss_options=ss_options)

    small_signal_driver.run()

    eigenvalues = small_signal_driver.results.eigenvalues
    PFactors = small_signal_driver.results.participation_factors
    damping_ratios = small_signal_driver.results.damping_ratios

    print(f"eigenvalues = {eigenvalues}")
    print(f"PFactors = {PFactors}")
    print(f"damping_ratios = {damping_ratios}")



if __name__ == '__main__':
    rms_kundur_small_signal()
