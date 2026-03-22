"""Inspect the IEEE 33 bus grid to understand bus naming and existing devices."""
import sys
sys.path.insert(0, '/Users/josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce

grid = gce.open_file('/Users/josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

print("=== BUSES ===")
for i, bus in enumerate(grid.buses):
    print(f"  [{i}] name='{bus.name}', Vnom={bus.Vnom} kV, is_dc={bus.is_dc}, idtag={bus.idtag}")

print(f"\nTotal buses: {len(grid.buses)}")

print("\n=== LOADS ===")
for load in grid.loads:
    print(f"  name='{load.name}', bus='{load.bus.name}', P={load.P} MW, Q={load.Q} MVAr")

print(f"\nTotal loads: {len(grid.loads)}")

print("\n=== GENERATORS ===")
for gen in grid.generators:
    print(f"  name='{gen.name}', bus='{gen.bus.name}'")

print(f"\nTotal generators: {len(grid.generators)}")

print("\n=== VSC DEVICES ===")
for vsc in grid.vsc_devices:
    print(f"  name='{vsc.name}', bus_from='{vsc.bus_from.name}', bus_to='{vsc.bus_to.name}'")

print(f"\nTotal VSC: {len(grid.vsc_devices)}")

print("\n=== LINES ===")
for line in grid.lines:
    print(f"  name='{line.name}', from='{line.bus_from.name}', to='{line.bus_to.name}'")

print(f"\nTotal lines: {len(grid.lines)}")
