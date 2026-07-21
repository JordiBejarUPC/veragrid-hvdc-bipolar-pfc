import os
import VeraGridEngine as vg

folder = "data"
src_name = os.path.join(folder, "ACTIVSg2000.RAW")
dst_name = os.path.join(folder, "ACTIVS_Laredo.veragrid")

grid = vg.open_file(src_name, options=vg.FileOpenOptions(file_type=vg.FileType.PSSE_raw))

# Find the "Laredo" zone object among all parsed zones
zones = {z.name: z for z in grid.get_zones()}
laredo_zone = zones["Laredo"]

# Buses that do NOT belong to the Laredo zone get removed, along with every
# branch/injection attached to them (delete_associated=True). This also drops
# the 21 tie-lines that cross into neighboring zones, so the isolated grid
# loses whatever support those ties provided in the full-system solve.
buses_to_remove = [b for b in grid.get_buses() if b.zone is not laredo_zone]
grid.delete_buses(buses_to_remove, delete_associated=True)

# Cutting the tie-lines to other zones can strand buses that only had external
# connections. Find them by connected-component analysis over the remaining
# lines/transformers and keep only the main (largest) component.
buses = grid.get_buses()
adj = {b: set() for b in buses}
for br in list(grid.get_lines()) + list(grid.get_transformers2w()):
    adj[br.bus_from].add(br.bus_to)
    adj[br.bus_to].add(br.bus_from)

seen = set()
components = []
for b in buses:
    if b in seen:
        continue
    stack = [b]
    comp = set()
    while stack:
        x = stack.pop()
        if x in comp:
            continue
        comp.add(x)
        stack.extend(adj[x] - comp)
    seen |= comp
    components.append(comp)

main_component = max(components, key=len)
islanded_buses = [b for b in buses if b not in main_component]
print(f"Islanded buses removed: {[(b.code, b.name) for b in islanded_buses]}")
grid.delete_buses(islanded_buses, delete_associated=True)

# The zone/island filtering above cuts the only swing bus in the full grid
# (7098 WADSWORTH 3, zone "Far West"), leaving Laredo with no reference bus.
# Promote its largest generator (4026 CHRISTINE 2, PG=408.9 MW) to swing.
swing_bus = next(b for b in grid.get_buses() if b.code == "4026")
swing_bus.is_slack = True

print(f"Buses kept: {grid.get_bus_number()}")
print(f"Lines: {len(grid.get_lines())}")
print(f"Transformers2w: {len(grid.get_transformers2w())}")
print(f"Generators: {len(grid.get_generators())}")
print(f"Loads: {len(grid.get_loads())}")
print(f"Controllable shunts: {len(grid.get_controllable_shunts())}")
print(f"Shunts: {len(grid.get_shunts())}")

vg.save_file(grid, dst_name)
print(f"Saved to {dst_name}")
