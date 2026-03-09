import VeraGridEngine.api as vge
from VeraGridEngine import SolverType

grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
#   Buses
# ----------------------------------------------------------------------------------------------------------------------
hv_bus = vge.Bus(name='HV Bus', Vnom=110, xpos=0, ypos=0)
hv_bus.is_slack = True
grid.add_bus(obj=hv_bus)

mv_bus = vge.Bus(name='MV Bus', Vnom=33, xpos=500, ypos=500)
grid.add_bus(obj=mv_bus)

lv_bus = vge.Bus(name='LV Bus', Vnom=0.4, xpos=-500, ypos=500)
grid.add_bus(obj=lv_bus)

# ----------------------------------------------------------------------------------------------------------------------
#   Transformer
# ----------------------------------------------------------------------------------------------------------------------
trafo_3w = vge.Transformer3W(V1=110,
                             V2=33,
                             V3=0.4,
                             bus1=hv_bus,
                             bus2=mv_bus,
                             bus3=lv_bus,
                             x12=0.03,
                             x23=0.03,
                             x31=0.03,
                             rate12=1.0,
                             rate23=1.0,
                             rate31=1.0)
grid.add_transformer3w(obj=trafo_3w)
trafo_3w.compute_delta_to_star()

# ----------------------------------------------------------------------------------------------------------------------
#   Loads
# ----------------------------------------------------------------------------------------------------------------------
mv_load = vge.Load(P=100,
                   Q=50)
grid.add_load(bus=mv_bus, api_obj=mv_load)

lv_load = vge.Load(P=50,
                   Q=10)
grid.add_load(bus=lv_bus, api_obj=lv_load)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = vge.power_flow(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                             retry_with_other_methods=False,
                                                             verbose=True))
print(res.get_voltage_df())

vge.save_file(grid, 'three_winding_v1.veragrid')