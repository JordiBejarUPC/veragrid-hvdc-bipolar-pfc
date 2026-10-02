import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import ConverterControlType, PfcControlType

Ub = 220

grid = gce.MultiCircuit(
    name="pfc_basic_example",
)

bus10 = gce.Bus(name = "Bus10",
               Vnom = Ub,
               is_slack=True,
               is_dc=True)
grid.add_bus(bus10)

bus0 = gce.Bus(name = "Bus0",
               Vnom = Ub,
               is_dc=True)
grid.add_bus(bus0)

grid.add_dc_line(gce.DcLine(name = "dc_line_74",
                       bus_from=bus0,
                       bus_to=bus10,
                       r=0.05))

grid.add_generator(bus0, gce.Generator(name='g0',
                                       vset=1.0))
bus1 = gce.Bus(name = "Bus1",
               Vnom = Ub,
               is_dc=True)
grid.add_bus(bus1)

bus2 = gce.Bus(name = "Bus2",
               Vnom = Ub,
               is_dc=True)
grid.add_bus(bus2)


grid.add_pfc(gce.PFC(name = "PFC_0",
                     bus_dc_r = bus10,
                     bus_dc_s = bus1,
                     bus_dc_t = bus2,
                     control1=PfcControlType.Ps_dc,
                     control1_val=20,
                     control2=PfcControlType.V1_pfc,
                     control2_val=0.5,
                     control3 = PfcControlType.V2_pfc,
                     control3_val = 0.5))


bus3 = gce.Bus(name = "Bus3",
               Vnom = Ub,
               is_dc=True)
grid.add_bus(bus3)

grid.add_dc_line(gce.DcLine(name = "dc_line_74",
                       bus_from=bus1,
                       bus_to=bus3,
                       r=0.05))

grid.add_load(bus3, gce.Load(name='Pls',
                             P = 20,
                             Q = 0))

bus4 = gce.Bus(name = "Bus4",
               Vnom = Ub,
               is_dc=True)
grid.add_bus(bus4)

grid.add_dc_line(gce.DcLine(name = "dc_line_74",
                       bus_from=bus2,
                       bus_to=bus4,
                       r=0.05))

grid.add_load(bus3, gce.Load(name='Pl4',
                             P = 20,
                             Q = 0))

#PowerFlow solver
options_pf = gce.PowerFlowOptions(verbose=2,generate_report=True,retry_with_other_methods=False)
gce.power_flow(grid, options=options_pf)