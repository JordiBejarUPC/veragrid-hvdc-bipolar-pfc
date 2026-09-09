import os
import numpy as np
import pandas as pd
import VeraGridEngine as vg

name = '01_A-HP_0-ST_2027_INV_MAX-D_(1).raw'
fn = os.path.join('data', name)

# --- parse RAW embedded solution (bus VM, VA in degrees) ---
lines = open(fn, encoding='latin-1').read().splitlines()
start = None
recs = []
for i, l in enumerate(lines):
    if 'BEGIN BUS DATA' in l:
        start = i + 1
        continue
    if start is not None:
        if l.strip().startswith('0') and 'END OF BUS' in l.upper():
            break
        if l.strip().startswith('@'):
            continue
        parts = [p.strip() for p in l.split(',')]
        if len(parts) < 9:
            continue
        recs.append((int(parts[0]), float(parts[7]), np.deg2rad(float(parts[8]))))
raw = pd.DataFrame(recs, columns=['number', 'vm_raw', 'va_raw'])

grid = vg.open_file(fn, options=vg.FileOpenOptions(file_type=vg.FileType.PSSE_raw))
opt = vg.PowerFlowOptions(tolerance=1e-5, solver_type=vg.SolverType.NR,
                          retry_with_other_methods=False, control_q=True,
                          ignore_single_node_islands=True, initialize_angles=True)
res = vg.power_flow(grid, options=opt)
Vm = np.abs(res.voltage)
Va = np.angle(res.voltage)
codes = []
for b in grid.get_buses():
    try:
        codes.append(int(b.code))
    except (TypeError, ValueError):
        codes.append(-1)
vgdf = pd.DataFrame({'number': codes, 'vm_vg': Vm, 'va_vg': Va})
m = raw.merge(vgdf, on='number')
m['dVm'] = (m['vm_vg'] - m['vm_raw']).abs()
m['dVa'] = (m['va_vg'] - m['va_raw']).abs()

with open('cmp_out.txt', 'w') as f:
    f.write(f"converged {res.converged}\n")
    f.write(f"VG vs RAW rows {len(m)} maxdVm {m.dVm.max():.4f} maxdVa {m.dVa.max():.4f}\n")
    f.write(f"dVm>1e-3 {int((m.dVm>1e-3).sum())} dVa>1e-3 {int((m.dVa>1e-3).sum())}\n")
    f.write(f"dVm>1e-2 {int((m.dVm>1e-2).sum())} dVa>1e-2 {int((m.dVa>1e-2).sum())}\n\n")
    f.write(m.sort_values('dVm', ascending=False).head(20).to_string())
print('DONE')
