# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Set, Tuple, Callable, List, Any, Union, Optional
import numpy as np
import numba as nb
import scipy.sparse as sp
import time
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr, BinOp, UnOp, Func
from VeraGridEngine.Utils.Symbolic.jit_compiler import EquationCompiler

from VeraGridEngine.Utils.Symbolic.diagnostic import (with_newton_diagnostics, NewtonDiagnosticsConfig,
                                                       NewtonSolveContext, dense_lstsq_fallback,
                                                       sparse_lsqr_fallback, maybe_check_index1,
                                                       maybe_apply_backtracking)
from VeraGridEngine.basic_structures import Vec, Mat, IntVec, CscMat


def get_vars_in_expr(expr: Expr) -> Set[int]:
    """
    Recursively collects UIDs of all variables present in an expression.

    :param expr: The symbolic expression to analyze.
    :type expr: Expr
    :return: A set containing the unique identifiers (UIDs) of the variables.
    :rtype: Set[int]
    """
    found: Set[int] = set()
    stack: List[Expr] = list()
    visited: Set[int] = set()

    stack.append(expr)

    while stack:
        node: Expr = stack.pop()
        node_id: int = id(node)

        if node_id in visited:
            # Explicit state: The node has already been processed.
            # We do nothing to prevent infinite loops in Directed Acyclic Graphs (DAGs).
            pass
        else:
            visited.add(node_id)

            # Flat type dispatch to evaluate AST nodes.
            # This avoids deep nesting and keeps the execution path predictable.
            if isinstance(node, Var):
                found.add(node.uid)

                # Since the node is guaranteed to be a Var instance, we can safely
                # access the base_var property directly.
                if node.base_var is not None:
                    found.add(node.base_var.uid)
                else:
                    # Terminal state: The variable is a base state, no derivative to track.
                    pass

            elif isinstance(node, Func):
                stack.append(node.arg)

            elif isinstance(node, UnOp):
                stack.append(node.operand)

            elif isinstance(node, BinOp):
                stack.append(node.left)
                stack.append(node.right)

            else:
                # Terminal state: Const nodes or unknown types have no children to traverse.
                pass

    return found

class Predictor:
    """
    Computes an explicit predictor for the Newton initial guess x_iter.
    """
    __slots__ = ['n_states']

    def __init__(self,
                 n_states: int) -> None:
        self.n_states = n_states

    def predict(self,
                x_iter: Vec,
                x_prev: Vec,
                dx_prev: Vec,
                h: float,
                pred_method: Union[DynamicIntegrationMethod|None] = DynamicIntegrationMethod.DaeBackEuler) -> Vec:
        """
        Apply predictor in-place and return x_iter.
        :param x_iter: Array to be written with the predictor guess (in-place).
        :param x_prev: Previous full variable vector at time n.
        :param dx_prev: Previous derivative vector (only first n_states are meaningful).
        :param h: Time step.
        :param pred_method: Integration method enum/value at the prediction step
        :return:
        """

        # Default: no-op predictor
        x_iter[:] = x_prev

        # Dispatch per method
        if pred_method == DynamicIntegrationMethod.OdeEuler:
            return self._predict_euler_state(x_iter, x_prev, dx_prev, h)
        elif pred_method == DynamicIntegrationMethod.DaeBDF2:
            raise NotImplementedError(f"predictor method {pred_method} ")

        # Otherwise keep default x_iter = x_prev
        return x_iter

    # ---------------------------------------------------------------------
    # Predictor implementations
    # ---------------------------------------------------------------------
    def _predict_euler_state(self,
                             x_iter: Vec,
                             x_prev: Vec,
                             dx_prev: Vec,
                             h: float) -> Vec:
        """
        Explicit Euler predictor for the *state* subset:
            x_{n+1}^0 = x_n + h * dx_n   (states only)
        Algebraics remain at x_prev by default (already set in caller).
        """
        ns = self.n_states
        x_iter[:ns] = x_prev[:ns] + h * dx_prev[:ns]
        return x_iter


class BoundaryUpdateWrapper:
    """
    Interface for injecting boundary conditions and events before the Newton step.
    Users must inherit from this class to update parameters safely.
    """
    __slots__ = []  # No state allowed in the base class

    def update(self, t: float, x: Vec, params: Vec) -> None:
        """
        Updates the parameters vector in place based on the current time and state.

        :param t: The current simulation time.
        :type t: float
        :param x: The current state vector.
        :type x: Vec
        :param params: The parameter vector to be modified.
        :type params: Vec
        :rtype: None
        """
        pass  # Explicit no-op for base class

    def get_next_forced_event_time(self, t_prev: float, t_target: float) -> Optional[float]:
        """
        Return the earliest forced-alignment event time in the interval (t_prev, t_target].

        :param t_prev: Previous solver time.
        :param t_target: Nominal target time.
        :return: Earliest forced event time or None.
        """
        _unused: Tuple["BoundaryUpdateWrapper", float, float] = (self, t_prev, t_target)
        return None

class HybridJacobianEvaluator:
    """
    Evaluates the JIT-compiled Jacobian and formats it as either Dense or Sparse.
    This class replaces nested functions to ensure memory determinism and strict type safety.
    """
    __slots__ = ['kernel_jit', 'use_sparse', 'n_vars', 'alpha_mult', 'np_rows', 'np_cols']

    def __init__(self,
                 kernel_jit: Callable,
                 use_sparse: bool,
                 n_vars: int,
                 alpha_mult: float,
                 np_rows: Union[IntVec| None] = None,
                 np_cols: Union[IntVec| None] = None) -> None:
        """
        Initializes the evaluator with the compiled Numba kernel and matrix topology.

        :param kernel_jit: The compiled Numba function for the Jacobian.
        :type kernel_jit: Callable
        :param use_sparse: Flag indicating if the output should be a sparse matrix.
        :type use_sparse: bool
        :param n_vars: The number of variables (size of the N x N matrix).
        :type n_vars: int
        :param alpha_mult: The scaling factor for the integration method.
        :type alpha_mult: float
        :param np_rows: Row indices for the sparse matrix format.
        :type np_rows: IntVec
        :param np_cols: Column indices for the sparse matrix format.
        :type np_cols: IntVec
        :rtype: None
        """
        self.kernel_jit = kernel_jit
        self.use_sparse = use_sparse
        self.n_vars = n_vars
        self.alpha_mult = alpha_mult
        self.np_rows = np_rows
        self.np_cols = np_cols

    def evaluate(self, states: Vec, params: Vec, history: Vec, d_history: Vec, h: float,
                 history2: Union[Vec| None] = None) -> Mat | CscMat:
        """
        Executes the JIT kernel and constructs the resulting Jacobian matrix.

        :param states: The current state vector.
        :type states: Vec
        :param params: The parameter vector.
        :type params: Vec
        :param history: The state history vector.
        :type history: Vec
        :param d_history: The derivative history vector.
        :type d_history: Vec
        :param h: The integration time step.
        :type h: float
        :param history2: The secondary history vector (for BDF2).
        :type history2: Vec
        :return: The assembled Jacobian matrix (Dense or Sparse CSC).
        :rtype: Mat | CscMat
        """
        # Allocate a new array to append the alpha scaling factor required by the kernel
        params_with_alpha: Vec = np.empty(len(params) + 1, dtype=np.float64)
        params_with_alpha[:-1] = params
        params_with_alpha[-1] = self.alpha_mult / h

        # Execute the JIT compiled kernel to obtain the raw data values
        data: Vec = self.kernel_jit(states, params_with_alpha, history, d_history, h, history2)

        # Assemble the matrix based on the requested storage format
        if self.use_sparse:
            return sp.csc_matrix((data, (self.np_rows, self.np_cols)), shape=(self.n_vars, self.n_vars))
        else:
            return data.reshape((self.n_vars, self.n_vars))

class JitSymbolicSolver:

    __slots__ = [
        'problem', 't0', 't_end', 'h', 'method', 'pred_method', 'dense_threshold', 'verbose',
        'steps', 't', 'y', 'dy', 'jit_kernels', 'jit_jacobian_symbolic',
        'state_vars', 'algebraic_vars', 'state_eqs', 'algebraic_eqs', 'diff_vars',
        'jit_compiler', '_residual_debug_info', '_newton_diag_config'
    ]

    def __init__(self,
                 problem: EmtProblemTemplate,
                 t0: float,
                 t_end: float,
                 h: float,
                 method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal,
                 pred_method:DynamicIntegrationMethod = None,
                 dense_threshold: int = 100,
                 verbose: bool = False,
                 newton_diag_config: NewtonDiagnosticsConfig | None = None)-> None:
        """
        :param problem: The DAE problem definition.
        :param t0: Initial time.
        :param t_end: End time.
        :param h: Time step.
        :param method: DynamicIntegrationMethod (DaeTrapezoidal, DaeBackEuler, DaeBDF2).
        :param pred_method: DynamicIntegrationMethod used in the predictor step if method is explicit.
        :param dense_threshold: Threshold to switch between dense and sparse linear solvers.
        :param verbose: Print compilation and simulation timings.
        """
        self.jit_compiler = None
        self.problem = problem
        self.t0 = t0
        self.h = h
        self.method = method
        self.pred_method = pred_method
        self.dense_threshold = dense_threshold
        self.verbose = verbose
        self._newton_diag_config = newton_diag_config or NewtonDiagnosticsConfig(
            compute_dense_cond=False,
            enable_fallback=False,
            enable_index1_check=False,
            enable_backtracking=False,
        )

        self.steps = int(np.ceil((t_end - t0) / h))
        self.t: Vec = np.empty(self.steps + 1)
        self.y: Mat = np.empty((self.steps + 1, self.problem.get_all_vars_number()))
        self.dy: Mat = np.empty((self.steps + 1, self.problem.get_diff_var_number()))

        # Solver specific caches
        self.jit_kernels = dict()
        self.jit_jacobian_symbolic = dict()

        self.state_vars = self.problem.get_state_vars()
        self.algebraic_vars = self.problem.get_algebraic_vars()
        self.state_eqs = self.problem.get_state_eqs()
        self.algebraic_eqs = self.problem.get_algebraic_eqs()
        self.diff_vars  = self.problem.get_diff_vars()

        self._residual_debug_info = list()

    # ==============================================================================
    # 2. JIT IMPLICIT ENGINE (Optimized with Batching)
    # ==============================================================================

    def build_jit_kernel(self, method: DynamicIntegrationMethod)-> None:
        """
        Compiles the numerical residual function using JIT.
        It uses a batching strategy (splitting equations into chunks) to prevent
        Numba/LLVM from hanging when compiling very large non-linear systems.

        :param method: The dynamic integration method to compile for.
        :type method: DynamicIntegrationMethod
        :rtype: None
        """
        if self.verbose:
            print(f"--- [JIT] Compiling Implicit Kernel ({method}) ---")

        sorted_vars: List[Any] = list()
        sorted_vars.extend(self.state_vars)
        sorted_vars.extend(self.algebraic_vars)

        var_uid_to_global_idx: dict = dict()
        for idx, v in enumerate(sorted_vars):
            var_uid_to_global_idx[v.uid] = idx

        all_params: List[Any] = list()
        all_params.extend(self.problem.get_variable_parameters())
        all_params.extend(self.problem.get_constant_parameters())

        equations: List[Expr] = list()
        residual_debug_info: List[dict] = list()
        synthetic_diff_terms: List[Var] = [Var(name=f"d_{sv.name}", base_var=sv) for sv in self.state_vars]

        # for i, rhs in enumerate(self.state_eqs):
        #     # sv = self.state_vars[i]
        #     # d_term = Var(name=f"d_{sv.name}", base_var=sv)
        #     d_term = self.diff_vars[i]  # real associated diff_var
        #     equations.append(d_term - rhs)

        for i, rhs in enumerate(self.state_eqs):
            sv = self.state_vars[i]
            d_term = synthetic_diff_terms[i]

            equations.append(d_term - rhs)

            residual_debug_info.append({
                "kind": "STATE",
                "label": f"d_{sv.name} - rhs_{sv.name}",
                "var_name": sv.name,
                "state_idx": var_uid_to_global_idx[sv.uid],
            })

        equations.extend(self.algebraic_eqs)

        for j, eq in enumerate(self.algebraic_eqs):
            av = self.algebraic_vars[j] if j < len(self.algebraic_vars) else None

            # equations.append(eq)
            #
            if av is not None:
                residual_debug_info.append({
                    "kind": "ALG",
                    "label": f"alg for {av.name}",
                    "var_name": av.name,
                    "state_idx": var_uid_to_global_idx.get(av.uid, None),
                })
            else:
                residual_debug_info.append({
                    "kind": "ALG",
                    "label": f"ALG_EQ_{j}",
                    "var_name": f"<no algebraic var for eq {j}>",
                    "state_idx": None,
                })

        self.jit_compiler = EquationCompiler(variables=sorted_vars, parameters=all_params, method=method)

        self._residual_debug_info = residual_debug_info

        # Batch compilation strategy
        BATCH_SIZE = 100
        n_eqs = len(equations)
        batched_kernels = []

        for i in range(0, n_eqs, BATCH_SIZE):
            chunk = equations[i: i + BATCH_SIZE]
            f_name = f"jit_step_{method}_part_{i}"

            # Compile inplace: the function writes directly to the 'residuals' array
            py_func = self.jit_compiler.compile(chunk, func_name=f_name, use_cse=True, offset=i, inplace=True)
            jit_func = nb.njit(cache=True, fastmath=True)(py_func)
            batched_kernels.append(jit_func)

        if self.verbose:
            print("\n[DBG] Residual debug info order")
            for r, info in enumerate(self._residual_debug_info[:80]):
                print(
                    f"{r:>4} | "
                    f"{info['kind']:<5} | "
                    f"{(info['state_idx'] if info['state_idx'] is not None else 'None'):>4} | "
                    f"{info['var_name']}"
                )

        self.jit_kernels[method] = batched_kernels

    def _build_jit_symbolic_hybrid(self, method: DynamicIntegrationMethod, use_sparse: bool)-> None:
        """
        Compiles a Hybrid Symbolic Jacobian.
        It generates a Numba kernel that evaluates the Jacobian entries and
        returns either a Scipy CSC Matrix (Sparse mode) or a Numpy Array (Dense mode).
        """
        cache_key = f"{method}_{use_sparse}"
        if cache_key in self.jit_jacobian_symbolic:
            return
        else:
            pass

        if self.verbose:
            print(f"--- [JIT-SD] Compiling Hybrid Symbolic Jacobian ({'SPARSE' if use_sparse else 'DENSE'}) ---")
        t0 = time.time()

        sorted_vars: List[Any] = list()
        sorted_vars.extend(self.state_vars)
        sorted_vars.extend(self.algebraic_vars)

        all_params: List[Any] = list()
        all_params.extend(self.problem.get_variable_parameters())
        all_params.extend(self.problem.get_constant_parameters())

        var_uid_to_idx: dict = dict()
        for i, v in enumerate(sorted_vars):
            var_uid_to_idx[v.uid] = i

        equations: List[Expr] = list()
        synthetic_diff_terms: List[Var] = [Var(name=f"d_{sv.name}", base_var=sv) for sv in self.state_vars]

        for i, rhs in enumerate(self.state_eqs):
            d_term = synthetic_diff_terms[i]
            equations.append(d_term - rhs)
        base_var_uid_to_diff_var: dict = {sv.uid: synthetic_diff_terms[i] for i, sv in enumerate(self.state_vars)}
        equations.extend(self.algebraic_eqs)

        N = len(sorted_vars)
        n_states = len(self.state_vars)
        jac_expression: List[Expr] = list()
        rows: List[int] = list()
        cols: List[int] = list()
        alpha_sym = Var("alpha_scaling_factor")

        if use_sparse:
            nnz = 0
            for r, eq in enumerate(equations):
                dependencies = get_vars_in_expr(eq)

                if r < n_states:
                    dependencies.add(self.state_vars[r].uid)
                else:
                    pass

                for v in sorted_vars:
                    if v.uid in dependencies:

                        c = var_uid_to_idx[v.uid]
                        d_direct = eq.diff(v)

                        dv = base_var_uid_to_diff_var.get(v.uid, None)
                        d_diff = eq.diff(dv) if dv is not None else Const(0)

                        final_expr = d_direct if (isinstance(d_diff, Const) and d_diff.value == 0) else (
                                    d_direct + alpha_sym * d_diff)
                        final_expr = final_expr.simplify()

                        if not (isinstance(final_expr, Const) and final_expr.value == 0):
                            jac_expression.append(final_expr)
                            rows.append(r)
                            cols.append(c)
                            nnz += 1
                        else:
                            pass

                    else:
                        pass

            if self.verbose:
                print(f"   [JIT-SD] Topology Analysis: {nnz} non-zeros (Sparsity: {1.0 - nnz / (N ** 2):.2%})")
        else:
            for r, eq in enumerate(equations):
                for c, v in enumerate(sorted_vars):

                    d_direct = eq.diff(v)

                    dv = base_var_uid_to_diff_var.get(v.uid, None)
                    d_diff = eq.diff(dv) if dv is not None else Const(0)

                    final_expr = (d_direct + alpha_sym * d_diff).simplify()
                    jac_expression.append(final_expr)

        compile_params: List[Any] = list()
        compile_params.extend(all_params)
        compile_params.append(alpha_sym)
        compiler = EquationCompiler(variables=sorted_vars, parameters=compile_params, method=method)
        func_name = f"jac_eval_{method}_{'sparse' if use_sparse else 'dense'}"
        kernel_py = compiler.compile(jac_expression, func_name=func_name, use_cse=True)
        kernel_jit = nb.njit(cache=False, fastmath=True)(kernel_py)

        if method == DynamicIntegrationMethod.DaeTrapezoidal:
            alpha_mult = 2.0
        elif method == DynamicIntegrationMethod.DaeBDF2:
            alpha_mult = 1.5
        else:
            alpha_mult = 1.0

        np_rows: Union[IntVec | None] = np.array(rows, dtype=np.int32) if use_sparse else None
        np_cols: Union[IntVec | None] = np.array(cols, dtype=np.int32) if use_sparse else None

        evaluator_obj = HybridJacobianEvaluator(
            kernel_jit=kernel_jit,
            use_sparse=use_sparse,
            n_vars=N,
            alpha_mult=alpha_mult,
            np_rows=np_rows,
            np_cols=np_cols
        )

        self.jit_jacobian_symbolic[cache_key] = evaluator_obj
        if self.verbose:
            print(f"   [JIT-SD] Compilation finished in {time.time() - t0:.4f}s")

    def simulate(self,
                 x0: Union[Vec | None] = None,
                 dx0: Union[Vec | None] = None,
                 params0: Union[Vec | None] = None,
                 boundary_updater: BoundaryUpdateWrapper | None = None) -> Tuple[Vec, Mat, Mat]:
        """
        Main JIT simulation loop using the Symbolic Differentiation (SD) backend.
        :param x0: Initial state vector.
        :param dx0: Initial derivative vector.
        :param params0: Initial event parameters.
        :param boundary_updater: Boundary condition updater, defaults to None.
        :return: A tuple containing the time vector and the state trajectory matrix. Tuple[Vec, Mat]
        """
        t_start = time.time()
        method = self.method

        n_eqs = self.problem.get_all_vars_number()
        n_states = self.problem.get_states_number()

        use_dense_solver = (n_eqs <= self.dense_threshold)
        is_sparse = not use_dense_solver

        # Prepare main method kernels and Jacobian
        if method not in self.jit_kernels:
            self.build_jit_kernel(method)
        else:
            pass
        self._build_jit_symbolic_hybrid(method, use_sparse=is_sparse)
        jac_key_main = f"{method}_{is_sparse}"

        # Prepare BackEuler fallback kernels for initial step or events
        if method == DynamicIntegrationMethod.DaeTrapezoidal:
            if DynamicIntegrationMethod.DaeBackEuler not in self.jit_kernels:
                self.build_jit_kernel(DynamicIntegrationMethod.DaeBackEuler)
            else:
                pass
            self._build_jit_symbolic_hybrid(DynamicIntegrationMethod.DaeBackEuler, use_sparse=is_sparse)
        else:
            pass
        jac_key_be = f"{DynamicIntegrationMethod.DaeBackEuler}_{is_sparse}"

        if self.verbose:
            mode_str = "DENSE" if use_dense_solver else "SPARSE"
            print(f"   [Config] System N={n_eqs}. Using {mode_str} linear solver (Threshold={self.dense_threshold}).")
        else:
            pass

        if x0 is None:
            x0 = self.problem.get_x0()
        else:
            pass
        if dx0 is None:
            dx0 = self.problem.get_dx0()
        else:
            pass

        self.t[0] = self.t0
        self.y[0, :] = x0.copy()
        self.dy[0, :] = dx0.copy()

        x_prev = x0.copy()
        dx_prev = dx0.copy()
        x_prev2 = x0.copy()
        x_iter = x0.copy()
        trial_x = np.zeros_like(x_iter)
        trial_res = np.zeros(n_eqs, dtype=np.float64)

        static_vals = np.array([c.value for c in self.problem.get_parameters_values()])
        n_event_params = self.problem.get_variable_parameter_number()

        if params0 is not None:
            ev_params = params0.copy()
        else:
            # ev_params = np.zeros(n_event_params, dtype=np.float64)
            ev_params_list = [c for c in self.problem.event_params_values]
            ev_params = np.array([float(val) if val is not None else 0.0 for val in ev_params_list], dtype=np.float64)

        if boundary_updater is not None:
            ev_params = self.problem.def_event_params_fn(ev_params, float(self.t0))
            full_params0 = np.concatenate((ev_params, static_vals))
            boundary_updater.update(float(self.t0), x_prev, full_params0)
            ev_params[:] = full_params0[:len(ev_params)]

        trace_collector = self.problem.get_newton_trace_collector()
        diag_cfg = self._newton_diag_config
        diagnostics_enabled: bool = (
            trace_collector is not None
            or diag_cfg.compute_dense_cond
            or diag_cfg.enable_fallback
            or diag_cfg.enable_index1_check
            or diag_cfg.enable_backtracking
        )

        dense_solve = None
        sparse_solve = None

        if diagnostics_enabled:
            dense_solve = with_newton_diagnostics(
                np.linalg.solve,
                fallback_solve=dense_lstsq_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="dense",
            )
            sparse_solve = with_newton_diagnostics(
                sp.linalg.spsolve,
                fallback_solve=sparse_lsqr_fallback,
                collector=trace_collector,
                config=diag_cfg,
                solver_name="sparse",
            )

        if self.verbose:
            print(f"-> Starting JIT Simulation ({method}, {self.steps} steps)...")
        else:
            pass

        for i in range(self.steps):
            if self.verbose:
                print(f"Simulating at step {i}")
            else:
                pass

            t_step_start: float = self.t0 + i * self.h
            t_step_target: float = self.t0 + (i + 1) * self.h
            self.t[i + 1] = t_step_target

            t_local_prev: float = t_step_start
            is_first_local_step: bool = True

            while t_local_prev < (t_step_target - 1e-15):
                forced_event_time: Optional[float] = None

                if boundary_updater is None:
                    pass
                else:
                    if hasattr(boundary_updater, 'get_next_forced_event_time'):
                        forced_event_time = boundary_updater.get_next_forced_event_time(
                            t_prev=t_local_prev,
                            t_target=t_step_target
                        )
                    else:
                        pass

                if forced_event_time is None:
                    t_curr: float = t_step_target
                else:
                    t_curr = forced_event_time

                h_eff: float = t_curr - t_local_prev

                if h_eff <= 0.0:
                    raise RuntimeError(
                        f"Invalid EMT substep size h_eff={h_eff} at macro step {i}."
                    )
                else:
                    pass

                if method == DynamicIntegrationMethod.DaeBDF2 and t_curr != t_step_target:
                    raise NotImplementedError(
                        "force_step_alignment with DAE BDF2 is not implemented yet. "
                        "Use DaeTrapezoidal or implement variable-step BDF2 coefficients."
                    )
                else:
                    pass

                method_eff = method
                if i == 0 and is_first_local_step and method == DynamicIntegrationMethod.DaeTrapezoidal:
                    method_eff = DynamicIntegrationMethod.DaeBackEuler
                else:
                    pass

                kernel_list_eff = self.jit_kernels[method_eff]
                jac_key_eff = jac_key_main if method_eff == method else jac_key_be
                current_jacobian_eff = self.jit_jacobian_symbolic[jac_key_eff]

                ev_params = self.problem.def_event_params_fn(ev_params, float(t_curr))
                full_params = np.concatenate((ev_params, static_vals))

                if i == 0 and is_first_local_step and self.verbose:
                    print("\nFULL params[] ORDER (objects + values):")
                    for idx, pobj in enumerate(full_params):
                        val = full_params[idx] if idx < len(full_params) else None
                        name = getattr(pobj, "name", str(pobj))
                        uid = getattr(pobj, "uid", None)
                        print(f"{idx:3d}  {name:40s}  uid={uid}  val={val}")
                else:
                    pass

                if boundary_updater is None:
                    pass
                else:
                    boundary_updater.update(t_curr, x_prev, full_params)
                    ev_params[:] = full_params[:len(ev_params)]

                x_iter[:] = x_prev
                x_iter[:n_states] = x_prev[:n_states] + h_eff * dx_prev[:n_states]

                if i == 0 and is_first_local_step and method == DynamicIntegrationMethod.DaeTrapezoidal:
                    predictor = Predictor(n_states=n_states)
                    predictor.predict(
                        x_iter=x_iter,
                        x_prev=x_prev,
                        dx_prev=dx_prev,
                        h=h_eff,
                        pred_method=self.pred_method,
                    )

                for k in range(15):
                    ctx = NewtonSolveContext(
                        t=float(t_curr),
                        step_idx=int(i),
                        newton_iter=int(k),
                        phase="jit",
                        method=str(method)
                    )

                    res = np.zeros(n_eqs, dtype=np.float64)

                    for kn in kernel_list_eff:
                        kn(x_iter, full_params, x_prev, dx_prev, h_eff, res, x_prev2)

                    if i == 0 and self.verbose:
                        dbg = getattr(self, "_residual_debug_info", None)

                        print("\n[Residual Debug] Sizes:")
                        print(f"  n_eqs(res)       = {n_eqs}")
                        print(f"  len(debug_info)  = {len(dbg) if dbg is not None else 'None'}")
                        print(f"  n_states(vec)    = {len(x_iter)}")

                        if dbg is None:
                            print("  [WARNING] self._residual_debug_info is missing.")
                        elif len(dbg) != n_eqs:
                            print("  [WARNING] len(self._residual_debug_info) != n_eqs")
                            print("            residual table labels may be wrong.\n")

                        abs_res = np.abs(res)
                        top_indices = np.argsort(abs_res)[:][::-1]

                        W_IDX = 4
                        W_KIND = 6
                        W_STATEIDX = 8
                        W_VARNAME = 40
                        W_LABEL = 62
                        W_RES = 13
                        W_ABS = 13
                        W_XIT = 13
                        W_XPR = 13
                        W_DXPR = 13

                        def _clip(s: str, width: int) -> str:
                            s = str(s)
                            if len(s) <= width:
                                return s.ljust(width)
                            if width <= 3:
                                return s[:width]
                            return s[:width - 3] + "..."

                        def _fmt_num(x, width: int = 13) -> str:
                            if x is None:
                                return " " * width
                            try:
                                xf = float(x)
                            except Exception:
                                return str(x).rjust(width)
                            if np.isnan(xf):
                                return "nan".rjust(width)
                            return f"{xf: .6e}".rjust(width)

                        title = f">>> TOP 20 LARGEST RESIDUALS (Step {i}, Iter {k}) <<<"
                        print("\n" + title)
                        header = (
                            f"{'idx':>{W_IDX}} | "
                            f"{'kind':<{W_KIND}} | "
                            f"{'state_i':>{W_STATEIDX}} | "
                            f"{'var_name':<{W_VARNAME}} | "
                            f"{'label':<{W_LABEL}} | "
                            f"{'res':>{W_RES}} | "
                            f"{'|res|':>{W_ABS}} | "
                            f"{'x_iter':>{W_XIT}} | "
                            f"{'x_prev':>{W_XPR}} | "
                            f"{'dx_prev':>{W_DXPR}}"
                        )
                        print(header)
                        print("-" * len(header))

                        for idx in top_indices:
                            if dbg is not None and idx < len(dbg):
                                info = dbg[idx]
                                kind = info.get("kind", "UNK")
                                var_name = info.get("var_name", "<?>")
                                label = info.get("label", f"residual_{idx}")
                                state_idx = info.get("state_idx", None)
                            else:
                                kind = "UNK"
                                var_name = "<?>"
                                label = f"residual_{idx}"
                                state_idx = None

                            if state_idx is not None and 0 <= state_idx < len(x_iter):
                                x_it = x_iter[state_idx]
                                x_pr = x_prev[state_idx]
                            else:
                                x_it = np.nan
                                x_pr = np.nan

                            if kind == "STATE" and state_idx is not None and 0 <= state_idx < len(dx_prev):
                                dx_pr = dx_prev[state_idx]
                            else:
                                dx_pr = np.nan

                            row = (
                                f"{idx:>{W_IDX}d} | "
                                f"{kind:<{W_KIND}} | "
                                f"{state_idx if state_idx is not None else -1:>{W_STATEIDX}d} | "
                                f"{_clip(var_name, W_VARNAME)} | "
                                f"{_clip(label, W_LABEL)} | "
                                f"{_fmt_num(res[idx], W_RES)} | "
                                f"{_fmt_num(abs_res[idx], W_ABS)} | "
                                f"{_fmt_num(x_it, W_XIT)} | "
                                f"{_fmt_num(x_pr, W_XPR)} | "
                                f"{_fmt_num(dx_pr, W_DXPR)}"
                            )
                            print(row)

                        print("-" * len(header))
                        print("=" * len(header) + "\n")

                    if np.linalg.norm(res, np.inf) < 1e-6:
                        break
                    else:
                        pass

                    J_final = current_jacobian_eff.evaluate(
                        states=x_iter,
                        params=full_params,
                        history=x_prev,
                        d_history=dx_prev,
                        h=h_eff,
                        history2=x_prev2
                    )

                    if diagnostics_enabled:
                        maybe_check_index1(J_final, n_states, ctx=ctx, config=diag_cfg)

                    if use_dense_solver:
                        if diagnostics_enabled:
                            delta = dense_solve(J_final, -res, ctx)
                        else:
                            delta = np.linalg.solve(J_final, -res)
                    else:
                        if diagnostics_enabled:
                            delta = sparse_solve(J_final, -res, ctx)
                        else:
                            delta = sp.linalg.spsolve(J_final, -res)

                    if diag_cfg.enable_backtracking:
                        def _evaluate_trial_residual(candidate_x: Vec, out_res: Vec) -> float:
                            out_res[:] = 0.0
                            for candidate_kernel in kernel_list_eff:
                                candidate_kernel(candidate_x, full_params, x_prev, dx_prev, h_eff, out_res, x_prev2)
                            return float(np.linalg.norm(out_res, np.inf))

                        maybe_apply_backtracking(
                            x_iter,
                            delta,
                            float(np.linalg.norm(res, np.inf)),
                            trial_x,
                            trial_res,
                            evaluate_residual=_evaluate_trial_residual,
                            config=diag_cfg,
                        )
                    else:
                        x_iter += delta

                if method == DynamicIntegrationMethod.DaeTrapezoidal:
                    dx_prev[:n_states] = (
                            (2.0 / h_eff) * (x_iter[:n_states] - x_prev[:n_states])
                            - dx_prev[:n_states]
                    )
                elif method == DynamicIntegrationMethod.DaeBackEuler:
                    dx_prev[:n_states] = (
                            (x_iter[:n_states] - x_prev[:n_states]) / h_eff
                    )
                elif method == DynamicIntegrationMethod.DaeBDF2:
                    x_prev2[:] = x_prev
                    dx_prev[:n_states] = (
                                                 1.5 * x_iter[:n_states]
                                                 - 2.0 * x_prev[:n_states]
                                                 + 0.5 * x_prev2[:n_states]
                                         ) / h_eff
                else:
                    dx_prev[:n_states] = (
                            (x_iter[:n_states] - x_prev[:n_states]) / h_eff
                    )

                if method != DynamicIntegrationMethod.DaeBDF2:
                    x_prev2[:] = x_prev
                else:
                    pass

                x_prev[:] = x_iter
                t_local_prev = t_curr
                is_first_local_step = False

            self.y[i + 1, :] = x_prev
            self.dy[i + 1, :] = dx_prev

        if self.verbose:
            print(f"JIT Finished: {time.time() - t_start:.4f}s")
        else:
            pass

        return self.t, self.y, self.dy
