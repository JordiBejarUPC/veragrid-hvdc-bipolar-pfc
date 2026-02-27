# ==============================================================================
# GENERALIZED EMT BERGERON LINE MODEL & STANDALONE DEMO
#
# This script contains the generalized N-phase implicit Bergeron Line Model
# intended for integration into `emt_line.py` and `emt_problem_dae.py`.
# It decouple nodes via local conductances and history current sources.
#
# Following the model definition, a standalone demo is provided to validate
# the wave propagation physics (open circuit and matched load) using
# the JitAdSolver, directly importing the generalized model.
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt

# VeraGridEngine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod

class GenericEmtProblem(EmtProblemTemplate):
    pass

# ==============================================================================
# 1. GENERALIZED BERGERON MODEL (For emt_line.py)
# ==============================================================================
class BergeronLineModel:
    """
    Generalized N-phase implicit Bergeron Line Model.
    Designed to be instantiated in EmtProblemDae and solved via JitAdSolver.
    """

    def __init__(self, name: str, Gc: np.ndarray, H: np.ndarray, tau: float, h: float):
        self.name = name
        self.Gc = np.asarray(Gc, dtype=np.float64)
        self.H = np.asarray(H, dtype=np.float64)
        self.num_phases = self.Gc.shape[0]
        self.n_delay = max(1, int(round(tau / h)))

        # Circular buffers for history tracking
        self.buf_vf = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_vt = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_if = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_it = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)

        self.Ih_f = [Var(f"Ih_f_{name}_ph{i}") for i in range(self.num_phases)]
        self.Ih_t = [Var(f"Ih_t_{name}_ph{i}") for i in range(self.num_phases)]

        # DAE Block: Map event parameters to initial Const(0.0)
        event_dict = {}
        for var in self.Ih_f + self.Ih_t:
            event_dict[var] = Const(0.0)

        self.block = Block(
            name=f"Bergeron_{name}",
            event_dict=event_dict
        )

    def get_nodal_injections(self, v_f_vars: list, v_t_vars: list):
        """
        Returns symbolic KCL current injections for the From and To buses.
        """
        self.v_f_vars = v_f_vars
        self.v_t_vars = v_t_vars

        i_f_exprs = []
        i_t_exprs = []

        for i in range(self.num_phases):
            # i_branch = Gc * V_local + I_hist
            # Note: No instantaneous coupling with the remote node
            i_f = sum(self.Gc[i, j] * self.v_f_vars[j] for j in range(self.num_phases)) + self.Ih_f[i]
            i_t = sum(self.Gc[i, j] * self.v_t_vars[j] for j in range(self.num_phases)) + self.Ih_t[i]

            i_f_exprs.append(i_f)
            i_t_exprs.append(i_t)

        return i_f_exprs, i_t_exprs

    def setup_indices(self, problem: GenericEmtProblem, vprms_offset: int = 0):
        """Maps symbolic UIDs to numerical array indices for the solver."""
        self.idx_vf = [problem.uid2idx_vars[v.uid] for v in self.v_f_vars]
        self.idx_vt = [problem.uid2idx_vars[v.uid] for v in self.v_t_vars]
        self.idx_hf = [problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_f]
        self.idx_ht = [problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_t]

    def update_history(self, step_counter: int, x_prev: np.ndarray, full_params: np.ndarray):
        """Evaluates history equations right before the Newton iteration."""
        k_curr = step_counter % (self.n_delay + 1)
        k_delay = (step_counter - self.n_delay) % (self.n_delay + 1)

        # 1. Read converged voltages from t_{n-1}
        v_f_now = x_prev[self.idx_vf]
        v_t_now = x_prev[self.idx_vt]

        self.buf_vf[k_curr, :] = v_f_now
        self.buf_vt[k_curr, :] = v_t_now

        # 2. Reconstruct branch currents at t_{n-1} using history applied at that step
        hf_vals = np.array([full_params[idx] for idx in self.idx_hf])
        ht_vals = np.array([full_params[idx] for idx in self.idx_ht])

        i_f_now = self.Gc @ v_f_now + hf_vals
        i_t_now = self.Gc @ v_t_now + ht_vals

        self.buf_if[k_curr, :] = i_f_now
        self.buf_it[k_curr, :] = i_t_now

        # 3. Retrieve delayed state (t_{n-1} - tau)
        v_f_tau = self.buf_vf[k_delay, :]
        v_t_tau = self.buf_vt[k_delay, :]
        i_f_tau = self.buf_if[k_delay, :]
        i_t_tau = self.buf_it[k_delay, :]

        # 4. Bergeron matrix math (Incident and reflected waves)
        X_f = -self.Gc @ v_t_tau - i_t_tau
        Y_f = -self.Gc @ v_f_tau - i_f_tau
        X_t = -self.Gc @ v_f_tau - i_f_tau
        Y_t = -self.Gc @ v_t_tau - i_t_tau

        I_mat = np.eye(self.num_phases)
        I_hist_f = 0.5 * ((I_mat + self.H) @ X_f + (I_mat - self.H) @ Y_f)
        I_hist_t = 0.5 * ((I_mat + self.H) @ X_t + (I_mat - self.H) @ Y_t)

        # 5. Inject updated history into full_params array for the upcoming Newton step
        for i in range(self.num_phases):
            full_params[self.idx_hf[i]] = I_hist_f[i]
            full_params[self.idx_ht[i]] = I_hist_t[i]


# ==============================================================================
# 2. STANDALONE DEMO (Validation test)
# ==============================================================================
def create_test_system(R_load: float):
    """
    Creates a test grid: Ideal Voltage Source (Step) -> Line -> Resistive Load
    """
    # EMT Physical Parameters
    Zc = 350.0  # Ohms
    tau = 0.005  # Seconds (5 ms travel time)
    h = 1e-4  # Time step
    V_step = 100.0  # Source voltage step

    # Setup generalized model for 1-phase test
    Gc_mat = np.array([[1.0 / Zc]])
    H_mat = np.array([[1.0]])  # Lossless ideal line

    # Instantiate the generalized line model
    line = BergeronLineModel("L1", Gc=Gc_mat, H=H_mat, tau=tau, h=h)

    # Nodal Variables
    v_f = Var("v_f")
    v_t = Var("v_t")

    # Get symbolic current injections from the generalized model
    i_f_exprs, i_t_exprs = line.get_nodal_injections([v_f], [v_t])
    i_f_line = i_f_exprs[0]
    i_t_line = i_t_exprs[0]

    # KCL Node F (Ideal voltage source V = V_step)
    kcl_f = v_f - V_step

    # KCL Node T (Line + Load to ground = 0)
    if R_load > 1e6:
        kcl_t = i_t_line  # Open circuit
    else:
        kcl_t = i_t_line + (v_t / R_load)

    # DAE Root Block
    sys_block = Block(
        name="TestGrid",
        algebraic_vars=[v_f, v_t],
        algebraic_eqs=[kcl_f, kcl_t]
    )
    sys_block.add(line.block)

    return sys_block, line, h, tau, v_f, v_t


def run_test(case_name: str, R_load: float):
    """Executes a single test case using JitAdSolver."""
    print(f"\n--- Running Test: {case_name} (R_load = {R_load} ohm) ---")

    sys_block, line, h, tau, v_f_var, v_t_var = create_test_system(R_load)
    sys_block.unify_blocks()
    glob_time = Var("t_glob")

    problem = GenericEmtProblem(sys_block=sys_block, glob_time=glob_time)

    # Setup index mapping (Offset is 0 for JitAdSolver event params)
    line.setup_indices(problem, vprms_offset=0)

    # Boundary update closure
    step_counter = [0]

    def boundary_update(t_curr, x_prev, full_params):
        line.update_history(step_counter[0], x_prev, full_params)
        step_counter[0] += 1

    # Solver Execution
    solver = JitAdSolver(
        problem=problem,
        t0=0.0,
        t_end=0.03,  # Simulate 30 ms
        h=h,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False
    )

    x0 = problem.get_x0()
    dx0 = np.zeros(problem.get_all_vars_number())
    params0 = problem._event_params_values

    t_arr, y_arr = solver.simulate(
        x0=x0,
        dx0=dx0,
        params0=params0,
        boundary_update_fn=boundary_update
    )

    idx_vf = problem.get_var_idx(v_f_var)
    idx_vt = problem.get_var_idx(v_t_var)

    v_f_sol = y_arr[:, idx_vf]
    v_t_sol = y_arr[:, idx_vt]

    return t_arr, v_f_sol, v_t_sol, tau


def main():
    # Scenario 1: Infinite impedance
    t1, vf1, vt1, tau = run_test("Open Circuit", R_load=1e9)

    # Scenario 2: Matched impedance (Zc)
    t2, vf2, vt2, _ = run_test("Matched Load", R_load=350.0)

    # Plotting
    plt.figure(figsize=(11, 6))
    plt.plot(t1 * 1000, vf1, 'k--', alpha=0.7, label="V_From (Ideal Source: 100V)")
    plt.plot(t1 * 1000, vt1, 'r-', linewidth=2, label="V_To (Open -> Total Reflection 200V)")
    plt.plot(t2 * 1000, vt2, 'b-', linewidth=2, label=r"V_To (Matched $Z_L = Z_c$ -> Stable 100V)")

    plt.axvline(x=tau * 1000, color='gray', linestyle=':', label=r"Wave Arrival (Multiples of $\tau$)")
    plt.axvline(x=3 * tau * 1000, color='gray', linestyle=':')
    plt.axvline(x=5 * tau * 1000, color='gray', linestyle=':')

    plt.title("EMT Architecture Validation: Generalized Implicit Bergeron DAE", fontsize=14, fontweight='bold')
    plt.xlabel("Time [ms]", fontsize=12)
    plt.ylabel("Node Voltage [V]", fontsize=12)
    plt.legend(loc="lower right")
    plt.grid(True, which='both', linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()