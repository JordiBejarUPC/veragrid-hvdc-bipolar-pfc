import VeraGridEngine.api as vge
import numpy as np
import pandas as pd
from VeraGridEngine import ShuntConnectionType

grid = vge.MultiCircuit()

# ----------------------------------------------------------------------------------------------------------------------
# Buses
# ----------------------------------------------------------------------------------------------------------------------
bus_slack = vge.Bus(name='Slack', xpos=0, ypos=0)
bus_slack.is_slack = True
grid.add_bus(obj=bus_slack)

bus_load = vge.Bus(name='Load', xpos=0, ypos=200)
grid.add_bus(obj=bus_load)

# ----------------------------------------------------------------------------------------------------------------------
# Generators
# ----------------------------------------------------------------------------------------------------------------------
gen_slack = vge.Generator()
grid.add_generator(bus=bus_slack, api_obj=gen_slack)

gen_load = vge.Generator(P=5, power_factor=1.0, is_controlled=False)
grid.add_generator(bus=bus_load, api_obj=gen_load)

# ----------------------------------------------------------------------------------------------------------------------
# Line
# ----------------------------------------------------------------------------------------------------------------------
line_slack_load = vge.Line(bus_from=bus_slack,
                           bus_to=bus_load,
                           name='Slack-Load',
                           r=0.1,
                           x=1.0,
                           rate=np.sqrt(10**2 + 5**2))
grid.add_line(obj=line_slack_load)

# ----------------------------------------------------------------------------------------------------------------------
# Load
# ----------------------------------------------------------------------------------------------------------------------
load = vge.Load(P=10.0,
                Q=5.0)
load.conn = ShuntConnectionType.GroundedStar
grid.add_load(bus=bus_load, api_obj=load)

# ----------------------------------------------------------------------------------------------------------------------
# Run power flow
# ----------------------------------------------------------------------------------------------------------------------
res = vge.power_flow(grid=grid, options=vge.PowerFlowOptions())

# vge.save_file(grid=grid, filename='positive_sequence_3ph_pf.veragrid')
# pd.set_option("display.float_format", "{:.5f}".format)

print("\nPositive-sequence power flow results:")
print(res.get_voltage_df())

# ----------------------------------------------------------------------------------------------------------------------
# Run three-phase power flow
# ----------------------------------------------------------------------------------------------------------------------
res_3ph = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions())

print("\nThree-phase power flow results:")
print(res_3ph.get_voltage_3ph_df())

# ----------------------------------------------------------------------------------------------------------------------
# 14 Bus
# ----------------------------------------------------------------------------------------------------------------------
from VeraGridEngine.IO.file_handler import FileOpen

main_circuit = FileOpen("IEEE 14 bus.raw").open()

vge.save_file(grid=main_circuit, filename='14bus.veragrid')
print()