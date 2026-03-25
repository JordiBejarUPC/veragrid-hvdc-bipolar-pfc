import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import MethodShortCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

grid = vge.open_file('ieee14_svs.dgs')

# ------------------------------------------------------------------------------------------------------------------
#   AC/DC Power Flow under healthy conditions
# ------------------------------------------------------------------------------------------------------------------
pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                              retry_with_other_methods=False,
                              limit_i_vsc=False)
res_pf = vge.power_flow(grid=grid, options=pf_options)

print(res_pf.get_voltage_df())

# ---------------------------------------------------------------------------------------------------------
#   No Control
# ---------------------------------------------------------------------------------------------------------
tcrmax = 5 # Maximum limit TCR
qmin = -10.0 # TSC reactive power [MVAr], it is < 0 and the reactive power of the TCS at 1 pu voltage
nncap = 1.0 # Actual number of capacitors
nxcap = 1.0 # Maximum number of capacitors
tcrqact = 3.0 # Actual Value of TCR [MVAr]
nfixcap = 0.0 # Number of capacitors MSC
Qfixcap = 0.0 # Q per capacitor MSC
usetp = 1.0 # Voltage setpoint [pu]

usvs = 0.926691 * np.exp(1j * -10.2621 * np.pi/180) # Bus voltage measurement [pu]
usvs = 0.897381 * np.exp(1j * -9.866362 * np.pi/180) # Bus voltage measurement [pu]

ysvs = qmin * nncap + tcrqact + Qfixcap * nfixcap # Fixed admittance based on 1 MVA / Ub^2

# SVS Range
ymin = qmin * nxcap + Qfixcap * nfixcap
ymax = tcrmax + Qfixcap * nfixcap
ysvs = max(min(ysvs, ymax), ymin)

Q = np.abs(usvs**2) * np.conj(ysvs) # Reactive power injection of the SVS [MVAr]
print('Q =', Q, 'MVAr')

# ---------------------------------------------------------------------------------------------------------
#   Voltage Control (no droop)
# ---------------------------------------------------------------------------------------------------------
usetp = 1.0 # Voltage setpoint [pu]

Uac = usetp

# ---------------------------------------------------------------------------------------------------------
#   Voltage Control (with droop)
# ---------------------------------------------------------------------------------------------------------
Srated = 10 # Rated reactive power [MVAr]
ddroop = 5 # Droop [%]
usetp = 1.0 # Voltage setpoint [pu]

usvs = 0.940699 * np.exp(1j * -10.4564 * np.pi/180) # Bus voltage measurement [pu]

Qdroop = Srated / ddroop * 100
Q = Qdroop * (np.abs(usvs) - usetp) # Reactive power injection of the SVS [MVAr]
print('Q =', Q, 'MVAr')

# ---------------------------------------------------------------------------------------------------------
#   Reactive Power Control
# ---------------------------------------------------------------------------------------------------------
qsetp = -10 # Reactive power setpoint [MVAr]

Q = qsetp