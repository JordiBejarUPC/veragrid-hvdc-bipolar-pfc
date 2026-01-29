# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Scalability Limit Test: Massive Sparse System Simulation.

Objective:
Verify that BlockSolver can handle large-scale systems (N > 1000 states)
by utilizing Sparse Linear Algebra and JIT Batch Compilation.

System:
A 1D Wave Equation discretized as N coupled masses (Harmonic Oscillators).
- State Vector Size: 2 * N_MASSES (Position + Velocity per mass).
- Topology: Sparse Tridiagonal (each mass connected to neighbors).

This serves as the empirical proof for the "Scalability" section in the documentation.
"""

import time
import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

def create_massive_chain(n_masses=1000):
    """
    Constructs a massive chain of oscillators.
    Returns: Block: The system block
    """
    print(f" > Constructing Symbolic Graph for {n_masses} masses ({2 * n_masses} states)...")
    t0 = time.perf_counter()

    # 1. Create all variables first (vectorized-like creation)
    pos_vars = [Var(f"x_{i}") for i in range(n_masses)]
    vel_vars = [Var(f"v_{i}") for i in range(n_masses)]

    k = Const(1000.0)  # High stiffness
    c = Const(0.1)  # Small damping

    state_vars = []
    state_eqs = []

    # 2. Build Equations (The Sparse Network)
    for i in range(n_masses):
        x_i = pos_vars[i]
        v_i = vel_vars[i]

        # Neighbor interactions
        x_left = pos_vars[i - 1] if i > 0 else Const(0.0)
        x_right = pos_vars[i + 1] if i < n_masses - 1 else Const(0.0)

        # Force: Hooke's Law from both sides
        force = k * (x_left - x_i) + k * (x_right - x_i) - c * v_i

        state_vars.extend([x_i, v_i])
        state_eqs.extend([v_i, force])

    system = Block(
        name=f"MassiveChain_N{n_masses}",
        state_vars=state_vars,
        state_eqs=state_eqs,
        parameters={}
    )

    print(f"   [Done] Graph built in {time.perf_counter() - t0:.3f}s")
    return system


def run_scalability_test():
    print("==================================================================")
    print("   SCALABILITY STRESS TEST: SPARSE JIT ENGINE")
    print("==================================================================")

    # TARGET SIZE: 500 Masses = 1000 State Variables
    N_MASSES = 500
    N_STATES = 2 * N_MASSES

    # 1. Setup
    system_block = create_massive_chain(N_MASSES)
    glob_time = Var("t_glob")

    print(f" > Initializing BlockSolver (Compiling JIT Kernels)...")

    #TODO(OPTIMIZATION): IMPLEMENT SPARSE FORWARD-MODE AD (ELIMINATE O(N^2) SETUP)

    t_compile_start = time.perf_counter()
    solver = BlockSolver(system_block, glob_time)

    # 2. Initial Conditions
    y0 = np.zeros(N_STATES)
    y0[0] = 1.0  # Impulse on first mass

    # 3. Simulation
    print(f" > Compiling JIT Kernel & Simulating Transient...")
    t_sim_start = time.perf_counter()

    # We force 'dense_threshold=100' so that for N=1000 it USES SPARSE SOLVER.
    # If N <= 100, it uses dense. Here 1000 > 100 -> Sparse.
    t_arr, y_arr = solver.simulate_unified(
        t0=0.0, t_end=0.2, h=0.001,  # 200 steps
        x0=y0, dx0=None, params0=None,
        method=DynamicIntegrationMethod.Trapezoid,
        dense_threshold=100,
        verbose=True  # Must be true to see internal JIT/Sparse logs
    )

    t_total_sim = time.perf_counter() - t_sim_start
    t_setup = t_sim_start - t_compile_start
    steps = len(t_arr)

    # 4. Sparsity Analysis
    # Theoretical Non-Zeros (NNZ):
    # dx/dt = v (1 non-zero per row)
    # dv/dt = k*x_L + k*x_R - 2k*x - c*v (4 non-zeros per row)
    # Total NNZ approx 5 * N_MASSES = 2500
    # Total Elements = (2*N)^2 = 1,000,000
    expected_nnz = 5 * N_MASSES
    total_elements = N_STATES ** 2
    sparsity = 1.0 - (expected_nnz / total_elements)

    print(f"\n==================================================================")
    print(f"   PERFORMANCE METRICS (N={N_STATES})")
    print(f"==================================================================")
    print(f"   1. Setup Time (Symbolic):     {t_setup:.4f} s")
    print(f"   2. Execution Time (Numeric):  {t_total_sim:.4f} s")
    print(f"   3. Throughput:                {t_total_sim / steps * 1000:.2f} ms/step")
    print(f"   4. System Size:               {N_STATES} Equations")
    print(f"   5. Theoretical Sparsity:      {sparsity * 100:.2f}% Zeros")
    print(f"==================================================================")
    print(f"   CONCLUSION: Solver runs at ~{t_total_sim / steps * 1000:.1f}ms per step")
    print(f"               for a 1000-variable system.")
    print("==================================================================")


if __name__ == "__main__":
    run_scalability_test()