"""Inspect DER generators and VSC ratings to understand current setup."""
import sys
sys.path.insert(0, '/Users/josep/Desktop/VeraGrid/src')

import VeraGridEngine.api as gce

grid = gce.open_file('/Users/josep/Desktop/VeraGrid/trunk/flexdis/ieee33_flexdis.veragrid')

total_load = sum(l.P for l in grid.loads)
print(f"Total active load: {total_load:.4f} MW")

print("\n=== DER Generators (on DC buses) ===")
for gen in grid.generators:
    print(f"  name='{gen.name}', bus='{gen.bus.name}', P={gen.P} MW, "
          f"Pmin={gen.Pmin}, Pmax={gen.Pmax}, Snom={gen.Snom}, "
          f"vset={gen.Vset}, is_controlled={gen.is_controlled}")

print("\n=== VSC Devices ===")
for vsc in grid.vsc_devices:
    print(f"  name='{vsc.name}'")
    print(f"    bus_from(DC)='{vsc.bus_from.name}'  bus_to(AC)='{vsc.bus_to.name}'")
    print(f"    rate={vsc.rate} MVA, Snom={getattr(vsc, 'Snom', 'N/A')}")
    print(f"    control1={vsc.control1}={vsc.control1_val}, control2={vsc.control2}={vsc.control2_val}")
    print(f"    min_ac_voltage={vsc.min_ac_voltage}")

# Compute current penetration
vsc_p_total = 0.0
for gen in grid.generators:
    if gen.bus.is_dc:
        vsc_p_total += gen.P
print(f"\nCurrent DER generation: {vsc_p_total:.4f} MW")
print(f"Current penetration: {100*vsc_p_total/total_load:.2f}%")
print(f"For 75% penetration: {0.75*total_load:.4f} MW")
print(f"Scale factor needed: {0.75*total_load/vsc_p_total:.4f}x")
