"""Apply min_ac_voltage = 0.85 p.u. to all VSC converters (Scenario A - No LVRT)."""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce

FILEPATH = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid'

grid = gce.open_file(FILEPATH)

for vsc in grid.vsc_devices:
    vsc.min_ac_voltage = 0.85
    print(f"  {vsc.name}: min_ac_voltage = {vsc.min_ac_voltage} p.u.")

gce.save_file(grid, FILEPATH)
print(f"\nSaved. {len(grid.vsc_devices)} VSCs updated.")
