import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, SolverType, FaultType, MethodShortCircuit, \
    PhasesShortCircuit

logger = gce.Logger()

grid = gce.MultiCircuit()
grid.fBase = 60

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_1 = gce.Bus(name='Bus1', Vnom=4.16, xpos=0, ypos=0)
bus_1.is_slack = True
grid.add_bus(obj=bus_1)
gen = gce.Generator(vset=1.0, r1=1e-10, x1=1e-10, r2=1e-10, x2=1e-10, r0=1e-10, x0=1e-10)
grid.add_generator(bus=bus_1, api_obj=gen)

bus_2 = gce.Bus(name='Bus1', Vnom=0.48, xpos=200 * 5, ypos=0, r_fault=0.1)
grid.add_bus(obj=bus_2)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load_634 = gce.Load(G1=0.7,
                    B1=0.5,
                    G2=0.6,
                    B2=0.45,
                    G3=0.5,
                    B3=0.4)
load_634.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_2, api_obj=load_634)

# ----------------------------------------------------------------------------------------------------------------------
# Transformer
# ----------------------------------------------------------------------------------------------------------------------
XFM_1 = gce.Transformer2W(name='XFM-1',
                          bus_from=bus_1,
                          bus_to=bus_2,
                          HV=4.16,
                          LV=0.48,
                          nominal_power=0.5,
                          rate=0.5,
                          r=1.1 * 2,
                          x=2 * 2)
XFM_1.conn_f = WindingType.GroundedStar
XFM_1.conn_t = WindingType.GroundedStar
grid.add_transformer2w(XFM_1)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res_pf = gce.power_flow3ph(grid=grid, options=gce.PowerFlowOptions(solver_type=SolverType.NR,
                                                                   retry_with_other_methods=False))
# print(res_pf.get_voltage_3ph_df())

# ----------------------------------------------------------------------------------------------------------------------
# Run short-circuit
# ----------------------------------------------------------------------------------------------------------------------
sc_options = gce.ShortCircuitOptions()

grid.add_short_circuit_event(
    gce.ShortCircuitEvent(
        device=grid.buses[1],
        fault_type=FaultType.LG,
        method=MethodShortCircuit.phases,
        phases=PhasesShortCircuit.a
    )
)

sc_driver = gce.ShortCircuitDriver(grid=grid,
                                   options=sc_options,
                                   pf_options=gce.PowerFlowOptions(),
                                   pf_results=None,
                                   pf_results3ph=res_pf)
sc_driver.run()

res_sc = sc_driver.results
print(res_sc.get_voltage_3ph_df())
