import VeraGridEngine.api as vge
from VeraGridEngine.enumerations import ConverterControlType

logger = vge.Logger()
grid = vge.MultiCircuit()

#   Buses
bus_ac_offshore = vge.Bus(name='Bus AC Offshore', xpos=0, ypos=0, is_slack=True)
grid.add_bus(obj=bus_ac_offshore)

bus_dc_offshore = vge.Bus(name='Bus DC Offshore', xpos=0, ypos=-400, is_dc=True)
grid.add_bus(obj=bus_dc_offshore)

bus_dc_onshore = vge.Bus(name='Bus DC Onshore', xpos=-400, ypos=-400, is_dc=True)
grid.add_bus(obj=bus_dc_onshore)

bus_ac_onshore = vge.Bus(name='Bus AC Onshore', xpos=-400, ypos=0, is_slack=True)
grid.add_bus(obj=bus_ac_onshore)


#   Generators / Grid Equivalents
offshore_grid = vge.Generator()
grid.add_generator(bus_ac_offshore, offshore_grid)

onshore_grid = vge.Generator()
grid.add_generator(bus_ac_onshore, onshore_grid)


#   Converters
offshore_vsc = vge.VSC(bus_from=bus_dc_offshore,
                       bus_to=bus_ac_offshore,
                       rate=15.0,
                       control1=ConverterControlType.Pac,
                       control2=ConverterControlType.Qac,
                       control1_val=10.0,
                       control2_val=0.0)
grid.add_vsc(offshore_vsc)

onshore_vsc = vge.VSC(bus_from=bus_dc_onshore,
                      bus_to=bus_ac_onshore,
                      rate=15.0,
                      control1=ConverterControlType.Vm_dc,
                      control2=ConverterControlType.Qac,
                      control1_val=1.0,
                      control2_val=-5.0)
grid.add_vsc(onshore_vsc)

#   DC Line
dc_line = vge.DcLine(bus_from=bus_dc_offshore,
                     bus_to=bus_dc_onshore,
                     r=0.1,
                     rate=15.0)
grid.add_dc_line(obj=dc_line)

#   Save
vge.save_file(grid=grid, filename='converter_controls.veragrid')