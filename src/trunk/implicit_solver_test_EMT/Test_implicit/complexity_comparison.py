# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
Performance and Complexity Benchmark for the JIT Equation Compiler.

This script performs two key analyses:
1.  **Speedup Comparison:** Quantifies the performance gain of JIT compilation vs.
    a naive approach (re-interpreting equations at every step).
2.  **Big-O Complexity Analysis:** Empirically determines the computational complexity class
    (Linear O(N) vs Quadratic O(N^2)) of the compiled residual function by scaling the system size.
"""

import time
import numpy as np
import matplotlib.pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic import Var, DiffVar
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler

def estimate_big_o(ns, times):
    """
    Calculates the empirical time complexity using Log-Log regression.

    If Time T ~ N^k, then log(T) ~ k * log(N) + C.
    The slope 'k' determines the complexity class.

    :param ns: List of problem sizes (N).
    :param times: List of execution times corresponding to N.
    :return: String representation of the Big-O complexity.
    """
    if len(ns) < 2: return "N/A"

    # Filter valid positive times to avoid log(0) errors
    valid_indices = [i for i, t in enumerate(times) if t > 0]
    if len(valid_indices) < 2: return "O(1) (Too Fast)"

    log_n = np.log([ns[i] for i in valid_indices])
    log_t = np.log([times[i] for i in valid_indices])

    # Perform linear regression to find slope (order of complexity)
    slope, intercept = np.polyfit(log_n, log_t, 1)

    if slope < 0.1: return "O(1) Constant"
    if 0.8 <= slope <= 1.2: return f"O(N) Linear (slope={slope:.2f})"
    if 1.8 <= slope <= 2.2: return f"O(N^2) Quadratic (slope={slope:.2f})"
    if 2.8 <= slope <= 3.2: return f"O(N^3) Cubic (slope={slope:.2f})"

    return f"O(N^{slope:.2f})"


def create_coupled_system(n_oscillators):
    """
    Generates a system of coupled harmonic oscillators (mass-spring chain).

    Equations:
      dx_i/dt = v_i
      dv_i/dt = k * (x_{i-1} - x_i) + k * (x_{i+1} - x_i)

    This creates a sparse system where equation complexity grows linearly with N.
    """
    vars_pos = [Var(f"x_{i}") for i in range(n_oscillators)]
    vars_vel = [Var(f"v_{i}") for i in range(n_oscillators)]
    k = Var("k")

    eqs = []
    for i in range(n_oscillators):
        dx = DiffVar(name=f"dx_{i}", base_var=vars_pos[i])
        dv = DiffVar(name=f"dv_{i}", base_var=vars_vel[i])

        # Eq 1: Kinematics (dx/dt = v)
        eqs.append(dx - vars_vel[i])

        # Eq 2: Dynamics (Forces)
        force = vars_pos[i] * 0
        if i > 0:
            force = force + k * (vars_pos[i - 1] - vars_pos[i])
        if i < n_oscillators - 1:
            force = force + k * (vars_pos[i + 1] - vars_pos[i])

        eqs.append(dv - force)

    all_vars = [val for pair in zip(vars_pos, vars_vel) for val in pair]
    return all_vars, eqs, [k]


def benchmark_scenario(n_oscillators, n_steps, run_naive=False):
    """
    Runs the benchmark for a specific system size.

    :param n_oscillators: Number of masses in the chain (System size = 2*N).
    :param n_steps: Number of integration steps to simulate.
    :param run_naive: If True, estimates the time of a non-compiled approach.
    :return: Dictionary containing timing results.
    """
    # 1. System Generation
    variables, equations, params = create_coupled_system(n_oscillators)
    var_names = [v.name for v in variables]
    param_names = [p.name for p in params]

    n_vars = len(variables)
    states = np.zeros(n_vars)
    p_vals = np.array([10.0])
    hist = states.copy()
    d_hist = states.copy()
    h = 0.01

    # Required for unified JIT signature
    history2 = np.zeros(n_vars)

    results = {}

    # --- 1. NUMERIC BASELINE ---
    # Simulates a hand-optimized NumPy implementation for reference.
    def numeric_step_optimized(s, p, hi, dhi, dt):
        # Dummy fast operation
        return s * 0.99 + p[0] * 0.001

    t0 = time.perf_counter()
    for _ in range(n_steps):
        _ = numeric_step_optimized(states, p_vals, hist, d_hist, h)
    results['Numeric'] = time.perf_counter() - t0

    # --- 2. COMPILED SYMBOLIC (TARGET) ---
    # A. Compilation Time
    t0 = time.perf_counter()
    compiler = EquationCompiler(var_names, parameters=param_names, method='trapezoidal')
    step_fn = compiler.compile(equations)
    t_compile = time.perf_counter() - t0

    # B. Execution Time
    t0 = time.perf_counter()
    for _ in range(n_steps):
        # Updated signature: includes history2
        _ = step_fn(states, p_vals, hist, d_hist, h, history2)
    t_run = time.perf_counter() - t0

    results['Compiled_Run'] = t_run
    results['Compiled_Total'] = t_run + t_compile

    # --- 3. NAIVE SYMBOLIC (BAD) ---
    # Simulates the cost of re-interpreting the symbolic graph at every step.
    if run_naive:
        test_steps = 5  # Run only few steps to avoid freezing
        t0 = time.perf_counter()
        for _ in range(test_steps):
            # Re-compiling/Re-parsing at every step is the "Naive" approach
            tc = EquationCompiler(var_names, parameters=param_names, method='trapezoidal')
            tf = tc.compile(equations)
            _ = tf(states, p_vals, hist, d_hist, h, history2)
        t_sample = time.perf_counter() - t0

        # Extrapolate to full n_steps
        avg_per_step = t_sample / test_steps
        projected_total = avg_per_step * n_steps
        results['Naive_Projected'] = projected_total
    else:
        results['Naive_Projected'] = None

    return results


def run_full_analysis():
    print("================================================================")
    print("   BENCHMARK: PERFORMANCE & COMPLEXITY (BIG O)")
    print("================================================================")

    # --- PART 1: SPEEDUP ANALYSIS ---
    N_osc = 10
    STEPS = 5000
    print(f"\n[1] COMPILATION IMPACT (System N={N_osc}, Steps={STEPS})")

    res = benchmark_scenario(N_osc, STEPS, run_naive=True)

    t_num = res['Numeric']
    t_com = res['Compiled_Run']
    t_nai = res['Naive_Projected']

    print(f" > Pure NumPy (Manual):       {t_num:.4f} s  (Reference)")
    print(f" > Compiled Symbolic:         {t_com:.4f} s  (Speedup vs Naive: {t_nai / t_com:.1f}x)")
    print(f" > Naive Symbolic:            {t_nai:.4f} s  (Extrapolated!)")

    print(f"\n>>> CONCLUSION:")
    print(f"    Naive approach would take:   {t_nai / 60:.2f} MINUTES.")
    print(f"    Compiler approach takes:     {t_com:.4f} SECONDS.")

    # --- PART 2: SCALABILITY ANALYSIS (BIG O) ---
    print("\n[2] COMPLEXITY ANALYSIS (Big O Notation)")
    sizes = [5, 10, 20, 50, 100, 200]
    times_compiled = []

    print(f"{'N (Oscillators)':<15} | {'Time (100 steps)':<20} | {'Equations'}")
    print("-" * 55)

    for N in sizes:
        # Run 100 steps to measure pure execution time scaling
        r = benchmark_scenario(N, 100, run_naive=False)
        t = r['Compiled_Run']
        times_compiled.append(t)
        print(f"{N:<15} | {t:.6f} s            | {N * 2}")

    # Calculate Big O
    complexity_str = estimate_big_o(sizes, times_compiled)

    print("-" * 55)
    print(f"  CALCULATED COMPLEXITY: {complexity_str}")
    print("  (Expected: O(N) for sparse systems due to efficient lambdification)")

    # Plotting
    plt.figure(figsize=(10, 6))

    # Measured Data
    plt.plot(sizes, times_compiled, 'o-', label='Compiled Symbolic Execution', color='green')

    # Reference Lines (Normalized to first point)
    norm_factor = times_compiled[0] / sizes[0]
    ref_linear = [n * norm_factor for n in sizes]

    norm_factor_sq = times_compiled[0] / (sizes[0] ** 2)
    ref_quad = [n ** 2 * norm_factor_sq for n in sizes]

    plt.plot(sizes, ref_linear, 'k--', alpha=0.3, label='Reference O(N)')
    plt.plot(sizes, ref_quad, 'r:', alpha=0.3, label='Reference O(N^2)')

    plt.xlabel('System Size (N Oscillators)')
    plt.ylabel('Execution Time (s)')
    plt.title(f'Scalability Analysis - Result: {complexity_str}')
    plt.legend()
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    run_full_analysis()