"""
Rebuild the IEEE 33 FlexDis grid with VSC converters from the original,
ensuring diagram entries are fully correct.
"""
import sys, zipfile, json
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.enumerations import ConverterControlType

INPUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'
OUTPUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

# Step 1: Read the diagram BEFORE loading the grid (to get original positions)
with zipfile.ZipFile(INPUT, 'r') as zf:
    diagram_name = [n for n in zf.namelist() if n.endswith('.diagram')][0]
    diagram = json.loads(zf.read(diagram_name))

# Build idtag->position lookup from diagram
bus_positions = {}
for idtag, entry in diagram['data']['Bus'].items():
    bus_positions[idtag] = (entry['x'], entry['y'])

# Step 2: Load grid
grid = gce.open_file(INPUT)

# Remove any previously added DC buses, VSCs, and DER generators
grid._vsc_devices = [v for v in grid.vsc_devices if not v.name.startswith("VSC Bus")]
grid._buses = [b for b in grid.buses if not b.name.startswith("DC Bus")]
grid._generators = [g for g in grid.generators if not g.name.startswith("DER")]

# Also clean diagram of old DC bus and VSC entries
for idtag in list(diagram['data']['Bus'].keys()):
    if idtag not in {b.idtag for b in grid.buses}:
        del diagram['data']['Bus'][idtag]
if 'VSC' in diagram['data']:
    del diagram['data']['VSC']

bus_dict = {b.name: b for b in grid.buses}

# Step 3: Add VSC converters
DC_OFFSET_Y = 150
vsc_specs = [
    ("Bus 18", "VSC Bus 18", 0.5, 0.2),
    ("Bus 22", "VSC Bus 22", 0.5, 0.15),
    ("Bus 25", "VSC Bus 25", 0.5, 0.3),
    ("Bus 33", "VSC Bus 33", 0.5, 0.15),
]

diagram['data']['VSC'] = {}

for ac_bus_name, vsc_name, rate, p_gen in vsc_specs:
    ac_bus = bus_dict[ac_bus_name]
    ac_x, ac_y = bus_positions[ac_bus.idtag]

    # DC bus
    dc_bus = gce.Bus(
        name=f"DC {ac_bus_name}",
        Vnom=ac_bus.Vnom,
        is_dc=True,
        is_slack=True,
    )
    grid.add_bus(dc_bus)

    # DER generator on DC bus
    gen = Generator(name=f"DER {ac_bus_name}")
    grid.add_generator(bus=dc_bus, api_obj=gen)

    # VSC converter
    vsc = gce.VSC(
        bus_from=dc_bus,
        bus_to=ac_bus,
        name=vsc_name,
        rate=rate,
        alpha1=0.0, alpha2=0.0, alpha3=0.0,
        control1=ConverterControlType.Pac,
        control1_val=-p_gen,
        control2=ConverterControlType.Qac,
        control2_val=0.0,
        kdp=0.0,
        u_setpoint=1.0,
        Q_min=-rate,
        Q_max=rate,
        min_ac_voltage=0.85,
    )
    grid.add_vsc(vsc)

    # Diagram: DC bus entry
    diagram['data']['Bus'][dc_bus.idtag] = {
        "x": ac_x,
        "y": ac_y + DC_OFFSET_Y,
        "h": 40,
        "w": 180.0,
        "r": 0.0,
        "poly_line": [],
        "draw_labels": True,
        "api_object": dc_bus.idtag
    }

    # Diagram: VSC entry
    diagram['data']['VSC'][vsc.idtag] = {
        "x": ac_x,
        "y": ac_y + DC_OFFSET_Y / 2,
        "h": 40,
        "w": 80.0,
        "r": 0.0,
        "poly_line": [],
        "draw_labels": True,
        "api_object": vsc.idtag
    }

    print(f"Added {vsc_name}: DC '{dc_bus.name}' -> AC '{ac_bus.name}'")

# Step 4: Save the grid (this writes model data)
gce.save_file(grid, OUTPUT)

# Step 5: Patch the diagram into the saved file
file_contents = {}
with zipfile.ZipFile(OUTPUT, 'r') as zf:
    for name in zf.namelist():
        file_contents[name] = zf.read(name)

file_contents[diagram_name] = json.dumps(diagram, indent=2).encode('utf-8')

with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zf:
    for name, data in file_contents.items():
        zf.writestr(name, data)

# Step 6: Verify
grid2 = gce.open_file(OUTPUT)
print(f"\nVerification: {len(grid2.buses)} buses, {len(grid2.vsc_devices)} VSCs, {len(grid2.generators)} gens")
for vsc in grid2.vsc_devices:
    print(f"  {vsc.name}: min_ac_voltage = {vsc.min_ac_voltage} p.u.")
print("File saved to", OUTPUT)
