"""Inspect bus positions to place DC buses correctly."""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce

grid = gce.open_file('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

print("=== Bus Positions ===")
for bus in grid.buses:
    print(f"  {bus.name:15s}  x={bus.x:8.1f}  y={bus.y:8.1f}  is_dc={bus.is_dc}")

print("\n=== VSC Positions ===")
for vsc in grid.vsc_devices:
    print(f"  {vsc.name:20s}  x={vsc.x:8.1f}  y={vsc.y:8.1f}")
