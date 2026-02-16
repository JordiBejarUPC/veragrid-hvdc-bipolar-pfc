# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
ARCHITECTURAL VALIDATION DEMO
=============================
Validates the transition from monolithic scripts to the new PhD Normalized Architecture:
  DeviceInterface -> EmtProblemBase -> ImplicitJitSolver

Physics: DC-DC Buck Converter (Same as legacy demo).
"""

import time
import numpy as np
import matplotlib.pyplot as plt

# 1. Import Core Symbolic Elements (The Engine)
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.enumerations import (
    DynamicIntegrationMethod,
    SimulationBackend,
    JacobianBackend,
)

from VeraGridEngine.Simulations.EMT.Devices.device_interface import EmtDeviceInterface
from VeraGridEngine.Simulations.EMT.problems.emt_problem import EmtProblemBase
from VeraGridEngine.Simulations.EMT.numerical_method.implicit_jit import ImplicitJitSolver


# ==============================================================================
# LAYER 1: DEVICE DEFINITION (Physics)
# ==============================================================================
class BuckConverterDevice(EmtDeviceInterface):
    """
    Physical definition of the Buck Converter.
    Inherits from the standard DeviceInterface to enable automatic clustering.
    """

    def build_model(self):
        # 1. Define Variables
        i_L = Var("i_L")
        v_C = Var("v_C")

        # 2. Define Parameters
        self.Vin_sw = Var("Vin_sw")
        R = Var("R")
        L = Var("L")
        C = Var("C")

        # 3. Register State Equations
        # di_L/dt = (Vin - v_C) / L
        self.add_state_equation(
            diff_var=i_L,
            rhs_expr=(self.Vin_sw - v_C) / L
        )

        # dv_C/dt = (i_L - v_C/R) / C
        self.add_state_equation(
            diff_var=v_C,
            rhs_expr=(i_L - v_C / R) / C
        )

        # 4. Set Parameter Values
        self.block.parameters = {
            self.Vin_sw: Const(0.0),
            R: Const(5.0),
            L: Const(100e-6),
            C: Const(470e-6),
        }

        # Save refs for plotting later
        self.i_L_ref = i_L
        self.v_C_ref = v_C


# ==============================================================================
# LAYER 2: PROBLEM DEFINITION (Topology)
# ==============================================================================
class BuckSystem(EmtProblemBase):
    """
    The Simulation Case.
    Assembles the device into the root system.
    """

    def build_structure(self):
        # Instantiate the device
        self.buck_dev = BuckConverterDevice("Buck1")

        # Add its symbolic block to the global system root
        # (In a complex grid, TopologyAssembler would connect ports here)
        self.root_block.add(self.buck_dev.get_block())


# ==============================================================================
# LAYER 3: EXECUTION RUNNER (Numerical Method)
# ==============================================================================
def run_architectural_case(jacobian_backend: JacobianBackend, vectorized: bool = False):
    label = "VECTORIZED (PhD Engine)" if vectorized else f"Standard ({jacobian_backend.name})"
    print(f"\n[Arch-Test] Running: {label}")

    # --- Parameters ---
    V_IN = 48.0
    V_OUT_REF = 12.0
    T_SW = 1.0 / 20e3
    DUTY = V_OUT_REF / V_IN
    DT = 1e-6
    T_TOTAL = 0.020

    # 1. Instantiate the Problem (Topology Container)
    problem = BuckSystem("Buck_Validation_Case")

    # ---: Build the internal structure ---
    problem.build_structure()

    # 2. Instantiate the Driver (ImplicitJitSolver)
    driver = ImplicitJitSolver(
        system_block=problem.root_block,
        time_var=problem.t_sym,
        backend=SimulationBackend.SymbolicImplicit,
        jacobian_backend=jacobian_backend
    )

    # 3. Compile (JIT Analysis)
    driver.compile(verbose=False)

    # Enable Diagnostics (Optional)
    driver.enable_diagnostics()

    # --- Setup PWM Controller ---
    try:
        param_uid = problem.buck_dev.Vin_sw.uid
    except AttributeError:
        print("Error: buck_dev not found in problem. Did build_structure() run?")
        return None, None, None, 0.0

    engine_ref = driver._engine

    # Locate the parameter index in the flattened array of the compiled engine
    p_idx = len(engine_ref._event_parameters) + engine_ref.uid2idx_params[param_uid]

    def pwm_controller_arch(t, x, params):
        t_mod = t % T_SW
        val = V_IN if t_mod < (DUTY * T_SW) else 0.0
        params[p_idx] = val

    # --- Simulation Loop ---
    steps = int(T_TOTAL / DT)

    # Initial State Vector (Zeros)
    x_curr = np.zeros(engine_ref._n_vars)

    t_start = time.time()

    t_arr, y_arr = engine_ref.simulate_unified(
        t0=0.0,
        t_end=T_TOTAL,
        h=DT,
        x0=x_curr,
        dx0=None,
        params0=None,
        method=DynamicIntegrationMethod.Trapezoid,
        boundary_update_fn=pwm_controller_arch,
        vectorized=vectorized,
        dense_threshold=100,
        verbose=False
    )

    elapsed = time.time() - t_start

    # --- Extract Results ---
    idx_v = engine_ref.uid2idx_vars[problem.buck_dev.v_C_ref.uid]
    idx_i = engine_ref.uid2idx_vars[problem.buck_dev.i_L_ref.uid]

    sol_v = y_arr[:, idx_v]
    sol_i = y_arr[:, idx_i]

    print(f"   Steps: {steps} | Time: {elapsed:.4f}s")
    print(f"   Final V: {sol_v[-1]:.4f} V")

    return t_arr, sol_v, sol_i, elapsed


# ==============================================================================
# MAIN COMPARISON
# ==============================================================================
def main():
    print("======================================================================")
    print("   VERAGRID NEW ARCHITECTURE VALIDATION")
    print("   DeviceInterface -> ProblemBase -> ImplicitJitSolver")
    print("======================================================================")

    # 1. Run Standard AD (Baseline)
    t1, v1, i1, time1 = run_architectural_case(JacobianBackend.Automatic, vectorized=False)

    # 2. Run Vectorized PhD Engine (The Goal)
    t2, v2, i2, time2 = run_architectural_case(JacobianBackend.Automatic, vectorized=True)

    # 3. Validation
    err_max = np.max(np.abs(v1 - v2))
    print("\n----------------------------------------------------------------------")
    print(f"VALIDATION RESULT:")
    print(f"   Max Discrepancy (Vectorized vs Standard): {err_max:.6e}")

    if err_max < 1e-5:
        print("   >>> SUCCESS: The new architecture is numerically exact.")
    else:
        print("   >>> FAIL: Discrepancy detected.")

    # 4. Plot
    plt.figure(figsize=(10, 6))
    plt.subplot(2, 1, 1)

    plt.plot(t1 * 1000, v1, 'k', linewidth=4, alpha=0.3, label="Standard AD")

    plt.plot(t2 * 1000, v2, 'r--', label="New Vectorized Engine")
    plt.ylabel("Voltage [V]")
    plt.title("Architectural Consistency Check")
    plt.legend()
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(t1 * 1000, i1, 'k', linewidth=4, alpha=0.3)
    plt.plot(t2 * 1000, i2, 'r--')
    plt.ylabel("Current [A]")
    plt.xlabel("Time [ms]")
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()