import numpy as np
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import (FaultType, MethodShortCircuit, WindingType, ShuntConnectionType,
                                         PhasesShortCircuit)

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_1 = gce.Bus(name='Bus1', Vnom=4.16, xpos=0, ypos=200)
bus_1.is_slack = True
grid.add_bus(obj=bus_1)
gen = gce.Generator(vset=1.0, r1=0.004, x1=0.5, r2=0.02, x2=0.5, r0=0.01, x0=0.08)
grid.add_generator(bus=bus_1, api_obj=gen)

bus_2 = gce.Bus(name='Bus2', Vnom=4.16, xpos=0, ypos=400)
grid.add_bus(obj=bus_2)

bus_3 = gce.Bus(name='Bus3', Vnom=0.48, xpos=0, ypos=600, r_fault=0.1)
grid.add_bus(obj=bus_3)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------
trafo_b2_b3 = gce.Transformer2W(name='Trafo_B2_B3',
                                bus_from=bus_2,
                                bus_to=bus_3,
                                HV=4.16,
                                LV=0.48,
                                nominal_power=0.250,
                                rate=0.250,
                                r=1*4,
                                x=3*4)
trafo_b2_b3.conn_f = WindingType.GroundedStar
trafo_b2_b3.conn_t = WindingType.GroundedStar
grid.add_transformer2w(trafo_b2_b3)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
zs_line = np.array([
    [0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
    [0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
    [0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
], dtype=complex) / 1.60934

ysh_line = np.array([
    [1j * 6.2998, 1j * -1.9958, 1j * -1.2595],
    [1j * -1.9958, 1j * 5.9597, 1j * -0.7417],
    [1j * -1.2595, 1j * -0.7417, 1j * 5.6386]
], dtype=complex) / 10 ** 6 / 1.60934

config_line = gce.create_known_abc_overhead_template(name='Config. 601',
                                                    z_abc=zs_line,
                                                    ysh_abc=ysh_line,
                                                    phases=np.array([1, 2, 3]),
                                                    Vnom=4.16,
                                                    frequency=60)
grid.add_overhead_line(config_line)

line_b1_b2 = gce.Line(name='Line_B1_B2',
                      bus_from=bus_1,
                      bus_to=bus_2,
                      length=1)
line_b1_b2.apply_template(config_line, grid.Sbase, grid.fBase, logger)
grid.add_line(obj=line_b1_b2)

# ----------------------------------------------------------------------------------------------------------------------
# Loads
# ----------------------------------------------------------------------------------------------------------------------
load_b2 = gce.Load(G1=0.200,
                   B1=0.100,
                   G2=0.150,
                   B2=0.050,
                   G3=0.100,
                   B3=0.025)
load_b2.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_2, api_obj=load_b2)

load_b3 = gce.Load(G1=0.050,
                   B1=0.025,
                   G2=0.100,
                   B2=0.050,
                   G3=0.075,
                   B3=0.0375)
load_b3.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_3, api_obj=load_b3)

# ----------------------------------------------------------------------------------------------------------------------
# Run Power Flow
# ----------------------------------------------------------------------------------------------------------------------
res_pf = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True))

print('\n --- Power Flow Results --- \n')
print(res_pf.get_voltage_3ph_df())

# ----------------------------------------------------------------------------------------------------------------------
# Run Short-Circuit
# ----------------------------------------------------------------------------------------------------------------------
sc_options = gce.ShortCircuitOptions()

grid.add_short_circuit_definition(
    gce.ShortCircuitEvent(
        device=grid.buses[2],
        fault_type=FaultType.LG,
        method=MethodShortCircuit.phases,
        phases=PhasesShortCircuit.a
    )
)

sc_driver = gce.ShortCircuitDriver(grid=grid,
                                   options=sc_options,
                                   pf_options=gce.PowerFlowOptions(three_phase_unbalanced=True),
                                   pf_results=res_pf)
sc_driver.run()

# ----------------------------------------------------------------------------------------------------------------------
# Short-Circuit Results
# ----------------------------------------------------------------------------------------------------------------------
res_sc = sc_driver.results

print('\n --- Short-Circuit Results --- \n')
print(res_sc.get_voltage_3ph_df())