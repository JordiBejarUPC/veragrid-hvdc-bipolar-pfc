"""
Add VSC converters to the IEEE 33-bus FlexDis grid.

Based on the reference image, converters are placed at:
  - Bus 18 (wind turbine)
  - Bus 22 (battery storage)
  - Bus 25 (solar/wind)
  - Bus 33 (battery storage)

Each VSC connects a new DC bus (with a DC generator as DER source) to the existing AC bus.
"""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.enumerations import ConverterControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from VeraGridEngine.enumerations import SolverType

INPUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'
OUTPUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

# Load the original grid (without any previous VSC additions)
grid = gce.open_file(INPUT)

# Remove any previously added DC buses and VSCs (in case we re-run)
grid._vsc_devices = [v for v in grid.vsc_devices if not v.name.startswith("VSC Bus")]
grid._buses = [b for b in grid.buses if not b.name.startswith("DC Bus")]
grid._generators = [g for g in grid.generators if not g.name.startswith("DER")]

# Build bus lookup
bus_dict = {b.name: b for b in grid.buses}

# VSC converter definitions: (AC bus name, VSC name, rate MVA, DER P injection MW)
vsc_specs = [
    ("Bus 18", "VSC Bus 18", 0.5, 0.2),   # Wind at bus 18
    ("Bus 22", "VSC Bus 22", 0.5, 0.15),   # Battery at bus 22
    ("Bus 25", "VSC Bus 25", 0.5, 0.3),    # Solar/Wind at bus 25
    ("Bus 33", "VSC Bus 33", 0.5, 0.15),   # Battery at bus 33
]

for ac_bus_name, vsc_name, rate, p_gen in vsc_specs:
    ac_bus = bus_dict[ac_bus_name]

    # Create a DC bus for this converter (slack to set DC voltage reference)
    dc_bus = gce.Bus(
        name=f"DC {ac_bus_name}",
        Vnom=ac_bus.Vnom,
        is_dc=True,
        is_slack=True,
    )
    grid.add_bus(dc_bus)

    # Add a DC generator on the DC bus to represent the DER source
    gen = Generator(
        name=f"DER {ac_bus_name}",
    )
    grid.add_generator(bus=dc_bus, api_obj=gen)

    # Create the VSC converter
    # bus_from = DC bus (positive pole), bus_to = AC bus
    # Pac control injects power from DC to AC, Qac sets reactive power
    vsc = gce.VSC(
        bus_from=dc_bus,
        bus_to=ac_bus,
        name=vsc_name,
        rate=rate,
        alpha1=0.0,
        alpha2=0.0,
        alpha3=0.0,
        control1=ConverterControlType.Pac,
        control1_val=-p_gen,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
        kdp=0.0,
        u_setpoint=1.0,
        Q_min=-rate,
        Q_max=rate,
    )
    grid.add_vsc(vsc)
    print(f"Added {vsc_name}: DC '{dc_bus.name}' (DER P={p_gen} MW) -> AC '{ac_bus.name}', rate={rate} MVA")

# Save the modified grid
gce.save_file(grid, OUTPUT)
print(f"\nSaved to {OUTPUT}")
print(f"Total buses: {len(grid.buses)} (33 AC + 4 DC)")
print(f"Total VSC devices: {len(grid.vsc_devices)}")
print(f"Total generators: {len(grid.generators)}")
