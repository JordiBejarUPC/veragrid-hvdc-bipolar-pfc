import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import FaultType, MethodShortCircuit

logger = gce.Logger()
grid = gce.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_0 = gce.Bus(name='Bus0', Vnom=115, xpos=0, ypos=0)
bus_0.is_slack = True
grid.add_bus(obj=bus_0)
gen = gce.Generator(r1=0.01, x1=0.1)
grid.add_generator(bus=bus_0, api_obj=gen)

bus_1 = gce.Bus(name='Bus1', Vnom=4.16, xpos=0, ypos=200)
grid.add_bus(obj=bus_1)

bus_2 = gce.Bus(name='Bus2', Vnom=4.16, xpos=0, ypos=400)
grid.add_bus(obj=bus_2)

bus_3 = gce.Bus(name='Bus3', Vnom=0.48, xpos=0, ypos=600, r_fault=10)
grid.add_bus(obj=bus_3)

# ----------------------------------------------------------------------------------------------------------------------
# Lines and Transformers
# ----------------------------------------------------------------------------------------------------------------------
trafo_b0_b1 = gce.Transformer2W(name='Trafo_B0_B1',
                                bus_from=bus_0,
                                bus_to=bus_1,
                                HV=110,
                                LV=4.16,
                                nominal_power=1,
                                rate=1,
                                r=2,
                                x=6)
grid.add_transformer2w(trafo_b0_b1)

line_b1_b2 = gce.Line(name='Line_B1_B2',
                      bus_from=bus_1,
                      bus_to=bus_2,
                      length=10,
                      r=0.1,
                      x=1)
grid.add_line(obj=line_b1_b2)

trafo_b2_b3 = gce.Transformer2W(name='Trafo_B2_B3',
                                bus_from=bus_2,
                                bus_to=bus_3,
                                HV=4.16,
                                LV=0.48,
                                nominal_power=0.250,
                                rate=0.250,
                                r=1,
                                x=3)
grid.add_transformer2w(trafo_b2_b3)

# ----------------------------------------------------------------------------------------------------------------------
# Loads
# ----------------------------------------------------------------------------------------------------------------------
load_b2 = gce.Load(P=0.500,
                   Q=0.300)
grid.add_load(bus=bus_2, api_obj=load_b2)

load_b3 = gce.Load(P=0.200,
                   Q=0.100)
grid.add_load(bus=bus_3, api_obj=load_b3)

# ----------------------------------------------------------------------------------------------------------------------
# Run Power Flow
# ----------------------------------------------------------------------------------------------------------------------
res_pf = gce.power_flow(grid=grid)

print('\n --- Power Flow Results --- \n')
print(res_pf.get_voltage_df())
print()
print(res_pf.get_current_df())

# ----------------------------------------------------------------------------------------------------------------------
# Run Short-Circuit
# ----------------------------------------------------------------------------------------------------------------------
sc_options = gce.ShortCircuitOptions(bus_index=3,
                                     fault_type=FaultType.ph3,
                                     method=MethodShortCircuit.sequences)

sc_driver = gce.ShortCircuitDriver(grid=grid,
                                   options=sc_options,
                                   pf_options=gce.PowerFlowOptions(),
                                   pf_results=res_pf)
sc_driver.run()

# ----------------------------------------------------------------------------------------------------------------------
# Short-Circuit Results
# ----------------------------------------------------------------------------------------------------------------------
res_sc = sc_driver.results

print('\n --- Short-Circuit Results --- \n')
print(res_sc.get_voltage_df())
print()
print(res_sc.get_current_df())