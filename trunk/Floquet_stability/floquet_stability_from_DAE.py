# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


from scipy.integrate import solve_ivp
from numpy.linalg import eigvals
import numpy as np
from scipy.sparse.linalg import spsolve

from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Templates.Emt.bus_emt_template import get_bus_emt_template

from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from trunk.Floquet_stability.example_floquet_template import get_exemple_floquet_emt_template


import VeraGridEngine.api as gce

grid = gce.MultiCircuit()
Sbase  =160 #VA
# Vbase = 15/np.sqrt(3)
Vbase = 15 #kV line to line voltage
Zbase = Vbase*Vbase/(Sbase*1e3) # kV*kV / kVA = ohm
Rbase = Zbase.real # ohm
f = 50 # Hz


grid.Sbase = Sbase #*1e6 # MVA

bus1 = Bus(name="Bus1", Vnom=Vbase, is_slack= True)

bus1_template = get_bus_emt_template(grid.var_factory)
bus1.emt_model.model = bus1_template.block

gen1 = Generator(name="Gen1",freq = 50, Snom=grid.Sbase)
gen1_template = get_exemple_floquet_emt_template()
gen1.emt_model.model = gen1_template.block

# load
P = 160.0
load1 = Load(name="load1", P1 =P/3 , P2 =P/3 , P3 =P/3, Q1= 0.0, Q2= 0.0, Q3= 0.0) # R in p.u.2.75

grid.add_bus(bus1)
grid.add_generator(bus=bus1, api_obj=gen1)
grid.add_load(bus=bus1, api_obj=load1)

print("grid.Sbase = ", grid.Sbase)

pf_options = PowerFlowOptions(
    solver_type=gce.SolverType.NR,
    retry_with_other_methods=False,
    verbose=0,
    initialize_with_existing_solution=True,
    tolerance=1e-6,
    max_iter=25,
    control_q=False,
    control_taps_modules=True,
    control_taps_phase=True,
    control_remote_voltage=True,
    orthogonalize_controls=True,
    apply_temperature_correction=True,
    branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
    distributed_slack=False,
    ignore_single_node_islands=False,
    trust_radius=1.0,
    backtracking_parameter=0.05,
    use_stored_guess=False,
    initialize_angles=False,
    generate_report=False,
)
power_flow = PowerFlowDriver3Ph(grid, pf_options)
power_flow.run()
res = power_flow.results

print(f"Converged: {res.converged}")
print(f"res:{res}")

options = EmtOptions(time_step=0.001,
                     simulation_time=10,
                     tolerance=1e-6,
                     integration_method=DynamicIntegrationMethod.DaeBackEuler,
                     verbose=0)

problem = EmtProblemDae(grid=grid,
                        options=options,
                        pf_results=res)


# A matrix at step 0
x0 = problem.get_x0()
dx0 = np.zeros_like(problem.get_states_number())

h = problem.get_dt()

fx = problem.get_j11(x0, dx0, h)  # ∂f/∂x
fy = problem.get_j12(x0, dx0, h)  # ∂f/∂y
gx = problem.get_j21(x0, dx0, h)  # ∂g/∂x
gy = problem.get_j22(x0, dx0, h)  # ∂g/∂y

gyx = spsolve(gy, gx)
A = fx - fy @ gyx

#TODO: this must be included in the solver...?




def fundamental_ode(t, M_flat, omega, d):
    M = M_flat.reshape((2, 2))
    dMdt = A(t, omega, d) @ M
    return dMdt.flatten()



T = 2 * np.pi / omega

M0 = np.eye(2).flatten()   # M(0) = I

sol = solve_ivp(
    fundamental_ode,
    t_span=(0.0, T),
    y0=M0,
    args=(),
    method="RK45",        # try "Radau" if stiff
    rtol=1e-9,
    atol=1e-12
)

M_T = sol.y[:, -1].reshape((2, 2))
print("Monodromy matrix C_M:")
print(M_T)

mu = eigvals(M_T)

print("\nFloquet multipliers:")
for i, val in enumerate(mu):
    print(f"μ{i+1} = {val:.6f}, |μ| = {abs(val):.6f}")

rho = np.max(np.abs(mu))

if rho < 1:
    print("\nSystem is asymptotically stable")
elif np.isclose(rho, 1.0):
    print("\nSystem is marginally stable")
else:
    print("\nSystem is unstable")









