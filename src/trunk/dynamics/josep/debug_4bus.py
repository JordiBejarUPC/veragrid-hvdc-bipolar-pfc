import numpy as np

# VeraGrid numbers
Vm1 = 1.03
Vm2 = 1.0285519395448224
Va1 = 0.0
Va2 = -0.0031464150423922005

# Andes numbers
# Vm1 = 1.03
# Vm2 = 1.0285518954483353
# Va1 = 0.0
# Va2 = -0.003146427608909906


dPfbranch1_dVm1 = -600 * Vm2 * np.sin(Va1 - Va2)
dQfbranch1_dVm1 = -1200 * Vm1 + 600 * Vm2 * np.cos(Va1 - Va2)
dPtbranch1_dVm1 = 600 * Vm2 * np.sin(Va1 - Va2)
dQtbranch1_dVm1 = 600 * Vm2 * np.cos(Va1 - Va2)

print(f"dPfbranch1_dVm1 = {dPfbranch1_dVm1}")
print(f"dQfbranch1_dVm1 = {dQfbranch1_dVm1}")
print(f"dPtbranch1_dVm1 = {dPtbranch1_dVm1}")
print(f"dQtbranch1_dVm1 = {dQtbranch1_dVm1}")