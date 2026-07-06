"""
Add DC buses and VSC devices to the diagram inside the .veragrid file,
positioning them near their AC counterparts.
"""
import sys, zipfile, json, io
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce

FILEPATH = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

# Load grid to get idtags
grid = gce.open_file(FILEPATH)

# Build lookup by name
bus_by_name = {b.name: b for b in grid.buses}
vsc_by_name = {v.name: v for v in grid.vsc_devices}

# Read the diagram from the ZIP
with zipfile.ZipFile(FILEPATH, 'r') as zf:
    diagram_files = [n for n in zf.namelist() if n.endswith('.diagram')]
    diagram_name = diagram_files[0]
    diagram = json.loads(zf.read(diagram_name))

# Get AC bus positions from the diagram
ac_bus_positions = {}
for idtag, entry in diagram['data']['Bus'].items():
    # Find bus name for this idtag
    for bus in grid.buses:
        if bus.idtag == idtag:
            ac_bus_positions[bus.name] = (entry['x'], entry['y'])
            break

print("AC bus positions for VSC locations:")
for name in ["Bus 18", "Bus 22", "Bus 25", "Bus 33"]:
    x, y = ac_bus_positions[name]
    print(f"  {name}: x={x:.1f}, y={y:.1f}")

# DC bus offset: place DC bus 150px below the AC bus
DC_OFFSET_Y = 150

# Add DC bus entries to diagram
for dc_name, ac_name in [("DC Bus 18", "Bus 18"), ("DC Bus 22", "Bus 22"),
                          ("DC Bus 25", "Bus 25"), ("DC Bus 33", "Bus 33")]:
    dc_bus = bus_by_name[dc_name]
    ac_x, ac_y = ac_bus_positions[ac_name]
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
    print(f"Added {dc_name} to diagram at ({ac_x:.1f}, {ac_y + DC_OFFSET_Y:.1f})")

# Add VSC entries to diagram
if 'VSC' not in diagram['data']:
    diagram['data']['VSC'] = {}

for vsc_name, ac_name in [("VSC Bus 18", "Bus 18"), ("VSC Bus 22", "Bus 22"),
                           ("VSC Bus 25", "Bus 25"), ("VSC Bus 33", "Bus 33")]:
    vsc = vsc_by_name[vsc_name]
    ac_x, ac_y = ac_bus_positions[ac_name]
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
    print(f"Added {vsc_name} to diagram at ({ac_x:.1f}, {ac_y + DC_OFFSET_Y/2:.1f})")

# Rewrite the ZIP with updated diagram
# Read all existing files
file_contents = {}
with zipfile.ZipFile(FILEPATH, 'r') as zf:
    for name in zf.namelist():
        if name == diagram_name:
            file_contents[name] = json.dumps(diagram, indent=2).encode('utf-8')
        else:
            file_contents[name] = zf.read(name)

# Write back
with zipfile.ZipFile(FILEPATH, 'w', zipfile.ZIP_DEFLATED) as zf:
    for name, data in file_contents.items():
        zf.writestr(name, data)

print(f"\nUpdated diagram in {FILEPATH}")
