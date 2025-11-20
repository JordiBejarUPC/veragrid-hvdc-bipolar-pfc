# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Tuple, Any, Sequence, Callable, Dict, List
import math
import numba as nb
import numpy as np
import copy
import scipy.sparse as sp
import matplotlib.pyplot as plt

import uuid

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Utils.Symbolic import BlockSolver
from VeraGridEngine.Utils.Symbolic.symbolic import _emit, _emit_one, sin, cos
from VeraGridEngine.Utils.Symbolic.block import Block, DiffBlock, Expr, Var
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType
from VeraGridEngine.basic_structures import Logger, ObjVec, BoolVec
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Expr, Const, _emit, _emit_params_eq, _heaviside, piecewise, LagVar
from VeraGridEngine.Utils.Symbolic.block_solver_comb import DiffBlockSolver



def _compile_equations(eqs: Sequence[Expr],
                       uid2sym_vars: Dict[int, str],
                       uid2sym_params: Dict[int, str],
                       add_doc_string: bool = True) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
    :param uid2sym_params:
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """

    fname = f"func{uuid.uuid4().hex}"  # random name to avoid collissions

    # Build source
    # src = f"@nb.njit()\n"
    src = f"def {fname}(vars, params):\n"
    src += f"    out = np.zeros({len(eqs)})\n"
    src += "\n".join([f"    out[{i}] = {_emit(e, uid2sym_vars, uid2sym_params)}" for i, e in enumerate(eqs)]) + "\n"
    src += f"    return out"

    exec(src)
    compiled_func = locals()[fname]

    return compiled_func


def _compile_equation(eqs: Sequence[Expr],
                      uid2sym_vars: Dict[int, str],
                      uid2sym_params: Dict[int, str],
                      add_doc_string: bool = True) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym_vars: dictionary relating the uid of a var with its array name (i.e. var[0])
    :param uid2sym_params:
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """
    # TODO: Why is there a second compile equation thing here?
    # Build source
    src = f"def _f(vars, params):\n"
    src += f"    out = np.zeros({len(eqs)})\n"
    src += "\n".join([f"    out[{i}] = {_emit_one(e, uid2sym_vars, uid2sym_params)}" for i, e in enumerate(eqs)]) + "\n"
    src += f"    return out"
    ns: Dict[str, Any] = {"math": math, "np": np}
    exec(src, ns)
    fn = nb.njit(ns["_f"], fastmath=True)

    if add_doc_string:
        fn.__doc__ = "def _f(vars)"
    return fn

def _compile_parameters_equations(eqs: Sequence[Expr],
                                  uid2sym_t: Dict[int, str],
                                  add_doc_string: bool = True) -> Callable[[float], np.ndarray]:
    """
    Compile the array of expressions to a function that returns an array of values for those expressions
    :param eqs: Iterable of expressions (Expr)
    :param uid2sym_t: dictionary relating the uid of a var with its array name (i.e. var[0])
    :param add_doc_string: add the docstring?
    :return: Function pointer that returns an array
    """

    # Build source
    src = f"def _f(glob_time):\n"
    src += f"    out = np.zeros({len(eqs)})\n"
    src += "\n".join(
        [f"    out[{i}] = {_emit_params_eq(e, uid2sym_t)}" for i, e in enumerate(eqs)]) + "\n"
    src += f"    return out"
    ns: Dict[str, Any] = {
                "math": math,
                "np": np,
                "nb": nb,
                "_heaviside": _heaviside,
            }
    exec(src, ns)
    fn = nb.njit(ns["_f"], fastmath=True)

    if add_doc_string:
        fn.__doc__ = "def _f(vars)"
    return fn

def delete_vars_from_block(block: Block, deleted_vars: List[Var]):
    deleted_vars_uid = set(var.uid for var in deleted_vars)
    for b in block.get_all_blocks():
        algebraic_vars_copy = b.algebraic_vars.copy()
        b.algebraic_vars = []
        for var in algebraic_vars_copy:
            if var.uid not in deleted_vars_uid:
                b.algebraic_vars.append(var)
            else:
                # print(f'Deleting var {var.name} from block {b.name}')
                _ = 0

def find_name_in_block(name: str, block: Block):
    for var in block.algebraic_vars + block.state_vars:
        if name == var.name:
            return var

def build_init_vars_vector(uid2idx_vars, mapping: dict[Var, float]) -> np.ndarray:
    """
    Helper function to build the initial vector
    :param uid2idx_vars:
    :param mapping: var->initial value mapping
    :return: array matching with the mapping, matching the solver ordering
    """
    x = np.zeros(len(mapping.items()))

    for key, val in mapping.items():
        if key.uid in uid2idx_vars.keys():
            i = uid2idx_vars[key.uid]
            x[i] = val
        else:
            raise ValueError(f"Missing variable {key} definition")

    return x

class SolverError(Exception):
    """Base class for all solver-related errors."""
    pass

class NaNError(SolverError):
    """Raised when NaNs or Infs appear in the solution."""
    pass

class ConvergenceError(SolverError):
    """Raised when solver fails to converge within max iterations."""
    pass

class SingularJacobianError(SolverError):
    """Raised when Jacobian is singular or ill-conditioned."""
    pass


def pseudo_transient(bus_index, region_solver, x0: np.ndarray, init_guess: dict[Var, float], res, grid: MultiCircuit, uid2idx_vars: Dict[int, int],
                     fix='V', dtau0=1, max_iter: int = 1e3, plot: bool = False, predictor: bool = False,
                     type: str = None):
    """
    :param bus_index:
    :param region_solver:
    :param x0: random init guess
    :param init_guess: init_guess for power flow vars
    :param res:
    :param grid:
    :param fix:
    :param dtau0:
    :param max_iter:
    :param plot:
    :param predictor:
    :param type:

    """

    for block in region_solver.block_system.children:
        found = False
        if getattr(block, 'pseudo_transient', False):
            for child_block in block.get_all_blocks():
                if not hasattr(child_block, 'external_mapping'):
                    continue
                if not VarPowerFlowRefferenceType.P in child_block.external_mapping.keys():
                    continue
                Pg = child_block.external_mapping[VarPowerFlowRefferenceType.P]
                Qg = child_block.external_mapping[VarPowerFlowRefferenceType.Q]
                Vm = child_block.external_mapping[VarPowerFlowRefferenceType.Vm]
                Va = child_block.external_mapping[VarPowerFlowRefferenceType.Va]
                found = True
                break

            if not found:
                continue
            bus_block = DiffBlock()

            if fix == 'P':
                delete_vars_from_block(block, [Pg, Qg])
                bus_block = DiffBlock(
                    algebraic_vars=[Vm, Va])
                bus_block.event_dict= {Pg: Const(float(np.real(res.Sbus[bus_index] / grid.Sbase))),
                                 Qg: Const(float(np.imag(res.Sbus[bus_index] / grid.Sbase)))}


            elif fix == 'V':
                delete_vars_from_block(block, [Va, Vm])
                bus_block = DiffBlock(
                    algebraic_vars=[Pg, Qg])
                bus_block.event_dict ={Vm: Const(float(np.abs(res.voltage[bus_index]))),
                                       Va: Const(float(np.angle(res.voltage[bus_index])))}

            elif fix == 'I':
                Im = Var('Im')
                Ia = Var('Ia')
                delta = find_name_in_block('delta', block)
                Id = find_name_in_block('Id', block)
                Iq = find_name_in_block('Iq', block)
                v = res.voltage[bus_index]
                Sb = res.Sbus[bus_index] / grid.Sbase

                # Current from power and voltage
                i = np.conj(Sb / v)  # ī = (p - jq) / v̄*

                bus_block = DiffBlock(
                    algebraic_eqs=[
                        Id - (-Im * sin(Ia - delta)),
                        Iq - Im * cos(Ia - delta),
                    ],
                    algebraic_vars=[Pg, Qg, Vm, Va])
                bus_block.event_dict = {Im: Const(float(np.abs(i))),
                                           Ia: Const(float(np.angle(i)))}

            elif fix == 'P&V':
                delete_vars_from_block(block, [Pg, Qg, Vm, Va])
                bus_block = DiffBlock()

                bus_block.event_dict = {Pg: Const(float(np.real(res.Sbus[bus_index] / grid.Sbase))),
                                        Qg: Const(float(np.imag(res.Sbus[bus_index] / grid.Sbase))),
                                        Vm: Const(float(np.abs(res.voltage[bus_index]))),
                                        Va: Const(float(np.angle(res.voltage[bus_index])))}


            elif fix == 'mixed':
                delete_vars_from_block(block, [Vm, Va, Pg, Qg])
                bus_block = DiffBlock(
                    algebraic_vars=[Va, Qg])
                bus_block.event_dict = {Vm: Const(float(np.abs(res.voltage[bus_index]))),
                                         Pg: Const(float(np.real(res.Sbus[bus_index] / grid.Sbase)))}

            init_block = DiffBlock(
                children=[block, bus_block]
            )
            # 2 out of [Pg, Qg, Vm, Va] need to be deleted from the algebraic vars to have a square system
            solver = DiffBlockSolver(init_block, region_solver.time)

            init_guess_copy = init_guess.copy()

            init_guess_copy.update(
                {Vm: float(np.real(res.Sbus[bus_index] / grid.Sbase)), Va: float(np.imag(res.Sbus[bus_index] / grid.Sbase))})
            x0_init_guess = build_init_vars_vector(uid2idx_vars, init_guess_copy, permissive=True)

            solved = False
            alpha = 0.9
            while not solved:
                try:
                    print(f'Trying dtau0 = {dtau0} with max_iter {max_iter}')
                    if type == 'dae':
                        x0_mdl, init_guess_mdl = solver.pseudo_transient_daes(region_solver,
                            x0_init_guess.copy(), dtau0=dtau0, max_iter=max_iter, max_tries=1e3, plot=plot,
                            predictor=predictor)
                    else:
                        x0_mdl, init_guess_mdl = solver.init_pseudo_transient_individual(region_solver,
                            x0_init_guess.copy(), dtau0=dtau0, max_iter=max_iter, max_tries=1e3, plot=plot,
                            predictor=predictor)
                    solved = True
                except NaNError as e:
                    msg = str(e).lower()
                    # print(msg)
                    dtau0 /= alpha
                except ConvergenceError as e:
                    msg = str(e).lower()
                    # print(msg)
                    dtau0 *= alpha
                except Exception as e:
                    # print(f"❌ Unexpected error: {e}")
                    raise
            for i, var in enumerate(solver._algebraic_vars):
                x0[uid2idx_vars[var.uid]] = x0_mdl[uid2idx_vars[var.uid]]

            init_guess.update(init_guess_mdl)

    # print('Pseudo-Transient ended')
    return x0, init_guess

def init_pseudo_transient_individual(region_solver: DiffBlockSolver, x0, init_guess={}, plot=True, dtau0=1e0, h=1e-3, beta=0.8, tol=1e-5,
                                     predictor=False, max_iter=8e4, max_tries=200, verbose=False):
    # Init pseudo transient method, Block only has algebraic eqs

    lag = np.zeros(len(region_solver.uid2idx_lag))
    dtau = dtau0
    dtau_max = 1e3
    dtau_min = 1e-7
    init_guess_uid = [var.uid for var in init_guess.keys()]
    region_solver.compile_implicit_predictor()

    for var in region_solver._algebraic_vars:
        if not var.uid in init_guess_uid:
            continue
        idx = region_solver.uid2idx_vars[var.uid]
        x0[idx] = init_guess[var]
    for i in range(len(x0)):
        if x0[i] == 0:
            _ = 0
            x0[i] = 0.1 + 0.5 * np.random.rand()
    for i in range(len(lag)):
        base_var = region_solver._lag_vars[i].base_var
        try:
            lag[i] = x0[region_solver.uid2idx_vars[base_var.uid]]
        except:
            lag[i] = 0.2
        if lag[i] == 0:
            lag[i] += 0.21 + np.random.rand()

    y = np.empty((5, region_solver._n_vars))
    step_idx = 0
    x_new = x0.copy()
    tries = 0
    current_time = 0
    params_current = region_solver._params_fn(float(current_time))

    # We set dt = 1
    params_current[-1] = 1
    params_outer = params_current.copy()

    dx_error = 1
    residual = 10
    old_residual = 10
    old_dx_error = 10

    # history containers
    dtau_hist = []
    dx_error_hist = []
    residual_hist = []
    x_hist = []
    dx_hist = []

    x_old_iter = np.r_[x_new, lag]
    while step_idx < max_iter:
        tries += 1
        xn = y[-1]
        params_current[-2] = 0.001

        xn_lags = np.r_[xn, lag]
        xnew_lags = np.r_[x_new, lag]
        rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
        if verbose:
            print(f'Pseudo transient step started with max_iter {max_iter} and step idx {step_idx} and try {tries}')
        # if (tries == 1 or (tries < 10 and predictor)) and False:
        if step_idx < 2 and tries == 1 and False:
            x_predicted, x_feasible = region_solver.predictor(x_old=x_old_iter, max_step=5e3, params=params_current)
            for i in range(0):
                _ = 0
                x_corrected, x_feasible = region_solver.corrector(region_solver, x_predicted, x_old_iter, x_feasible, params_current)
                x_predicted = x_corrected

            xnew_lags[:len(x_feasible)] = x_feasible

            # 1 Handle first-order derivatives first
            for i, var in enumerate(region_solver._diff_vars):
                if var.diff_order != 1:
                    continue
                base_var_uid = region_solver.uid2idx_vars[var.base_var.uid]
                xnew_lags[base_var_uid] = x_predicted[i]

            # 2 Sort differential variables by diff_order before building lags
            diff_vars_sorted = sorted(region_solver._diff_vars, key=lambda v: v.diff_order)

            # 3 Build lag variables in increasing order of diff_order
            for i, var in enumerate(diff_vars_sorted):
                if var.diff_order <= 1:
                    continue

                origin_var = var.origin_var
                diff_order = var.diff_order

                # Previous lag (order-1)
                prev_lag = LagVar.get_or_create(
                    name=f"{origin_var.name}_lag{diff_order - 1}",
                    base_var=origin_var,
                    lag=diff_order - 1,
                )
                prev_lag_uid = region_solver.uid2idx_vars[prev_lag.uid]

                # Current lag
                lag_var = LagVar.get_or_create(
                    name=f"{origin_var.name}_lag{diff_order}",
                    base_var=origin_var,
                    lag=diff_order,
                )
                lag_uid = region_solver.uid2idx_vars[lag_var.uid]

                # Recursive lag update: x_lag_n = x_lag_(n-1) − h * x^(n)
                xnew_lags[lag_uid] = xnew_lags[prev_lag_uid] - params_current[-1] * x_predicted[i]

            print(f'xnew_lags is {xnew_lags}')
            rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
            Jf = region_solver.jacobian_implicit(xnew_lags, params_current, dtau)
            dx_previous = region_solver.compute_dx(xnew_lags[:region_solver._n_alg], lag, dtau)
            residual_dx = np.linalg.norm(dx_previous)
            residual = np.linalg.norm(rhs)
            x_new = xnew_lags[:len(x_new)]
            xnew_lags = np.r_[x_new, lag]
            print(f'xnew_lags is {xnew_lags}')

            if verbose:
                print(f'residual is {residual}')
            if residual_dx < tol and residual < tol:
                x_new = xnew_lags[:region_solver._n_alg]
                dx = region_solver.compute_dx(xnew_lags[:region_solver._n_alg], lag, 1e-3)
                residual_dx = np.linalg.norm(dx)
        else:
            rhs = region_solver.rhs_pseudo_transient(xnew_lags, xn_lags, params_current, 1, dtau)
            Jf = region_solver.jacobian_pseudo_transient(xnew_lags, params_current, dtau)
            residual = np.linalg.norm(rhs)

            try:
                delta = sp.linalg.spsolve(Jf, -rhs)
            except Exception as e:
                raise SingularJacobianError(f"Linear solver failed at try {tries}: {e}")
            if not np.all(np.isfinite(delta)) or not np.all(np.isfinite(delta)):
                print(f'x_new is {x_new}')
                print(f'rhs is {rhs}')
                print(f'residual is {np.linalg.norm(rhs)} try is {tries} and step is {step_idx}')
                raise NaNError(
                    f"Newton step failed at try {tries} and step {step_idx}: delta has NaN/Inf values with dtau {dtau}")
            x_new += delta
            xnew_lags = np.r_[x_new, lag]
            rhs = region_solver.rhs_pseudo_transient(xnew_lags, xn_lags, params_current, 1, dtau)

        if step_idx == 0 and tries % 10 == 1:
            i = np.argmax(rhs)

        newton_residual = np.linalg.norm(rhs, np.inf)
        converged = (tries % 10 == 9) or (tries < 10) or True
        if verbose:
            _ = 0
            print(f'residual is {newton_residual}, step is {step_idx} try is {tries}')
            print(f'dtau is {dtau}')

        if converged:
            step_idx += 1
            tries = 0
            y = np.roll(y, shift=-1, axis=0)
            alpha = 1.0
            if step_idx > 2:
                y[-1] = alpha * x_new + (1 - alpha) * y[-1]
            else:
                y[-1] = alpha * x_new
            x_new = y[-1]

            dx = region_solver.compute_dx(x_new, lag, dtau)
            dx_error = np.linalg.norm(dx)
            rhs = region_solver.rhs_pseudo_transient(xnew_lags, xn_lags, params_current, 1, dtau)
            residual = np.linalg.norm(rhs)

            # save history
            dtau_hist.append(dtau)
            dx_error_hist.append(dx_error)
            residual_hist.append(residual)
            x_hist.append(x_new.copy())
            dx_hist.append(dx.copy())

            if residual < 1e-5 and dx_error < 1e-5:
                break

            print(
                f'Convergence achieved for dtau={dtau:.2e}, ||dx||={dx_error:.2e}, residual={residual:.2e}, step {step_idx}')

            eps = 1e-14
            avg_residual = 0.8 * old_residual + 0.2 * residual
            ratio = (avg_residual + eps) / residual
            ratio = (old_residual + eps) / residual

            # Default scaling factor
            beta = ratio
            if beta > 1.0:
                beta = 2
            elif beta < 1.0:
                beta = 0.5

            # Residual increased → reduce time step
            if dx_error < tol and residual > tol:
                print(f"Residual too big → reducing dtau and dx_error is {dx_error}")
                dtau = 1
                beta = 0.8
            elif abs(1 - ratio) < 1e-5 and step_idx > 100 and False:
                # beta = 1.5
                print("System stalled → increasing dtau ")
            elif len(dtau_hist) > 2 and abs(1 - dtau_hist[-1] / dtau_hist[-2]) < 1e-3 and dtau_hist[
                -1] < dtau_max and step_idx > 100 and False:
                # beta = 1.5
                print("System stalled → increasing dtau ")
            elif residual < tol:
                beta = 5
                print("Residual already small → increasing dtau ")
            else:
                # beta = np.clip(ratio, 0.5, 2.0)
                _ = 0

            if residual < tol and dx_error < tol:
                beta = 2
                if np.abs(1 - dtau / h) < 1e-1:
                    break
                elif (dtau * beta - h) * (beta - h) < 0:
                    dtau = h
                elif (dtau / beta - h) * (beta - h) < 0:
                    dtau = h
                elif dtau > h:
                    dtau /= beta
                else:
                    dtau *= beta
                beta = 1

            # beta = ratio
            print(f'Updating dtau: {dtau} * {beta}')
            beta = min(max(0.5, beta), 2)
            if residual < tol:
                beta = 2
                print("Residual already small → increasing dtau ")

            print(f'Updating dtau: {dtau} * {beta}')
            if dtau > 0:
                dtau = min(dtau_max, max(dtau_min, dtau * beta))
            else:
                dtau = -min(dtau_max, max(dtau_min, -dtau * beta))
            print(f'Updated dtau: {dtau}')

            # update lags
            for i, lag_var in enumerate(region_solver._lag_vars):
                if lag_var.lag == 0:
                    uid = lag_var.base_var.uid
                    idx = region_solver.uid2idx_vars[uid]
                    lag[i] = x_new[idx]
                elif step_idx + 1 - (lag_var.lag - 1) >= 0:
                    uid = lag_var.base_var.uid
                    idx = region_solver.uid2idx_vars[uid]
                    lag[i] = y[-1 - lag_var.lag, idx]
                else:
                    lag_name = lag_var.base_var.name + '_lag_' + str(lag_var.lag - 1)
                    next_lag_var = LagVar.get_or_create(lag_name, base_var=lag_var.base_var, lag=lag_var.lag - 1)
                    uid = next_lag_var.uid
                    idx = region_solver.uid2idx_lag[uid]
                    lag[i] = lag[idx]
            old_residual = residual
            old_dx_error = dx_error
            x_old_iter = np.r_[x_new, lag]

        elif tries > max_tries:
            print(f'failed with dtau = {dtau}')
            raise ConvergenceError(f"Max tries reached at dtau={dtau:.2e}, residual={residual:.2e}")

    init_guess = {var: x_new[region_solver.uid2idx_vars[var.uid]] for var in region_solver._algebraic_vars}

    if not plot:
        return x_new, init_guess
    # --- Plotting section ---
    fig, axs = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    axs[0].semilogy(dx_error_hist, label="||dx||")
    axs[0].set_ylabel("dx error (log)")
    axs[0].legend()

    axs[1].semilogy(residual_hist, label="Residual norm")
    axs[1].set_ylabel("Residual (log)")
    axs[1].legend()

    axs[2].semilogy(dtau_hist, label="dtau")
    axs[2].set_ylabel("dtau")
    axs[2].set_xlabel("Step index")
    axs[2].legend()

    # --- Plot actual variables ---
    x_hist = np.array(x_hist)  # shape: (n_steps, n_vars)
    dx_hist = np.array(dx_hist)  # shape: (n_steps, n_vars)

    nvars = len(region_solver._algebraic_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)

    # if there’s only one subplot, axs won’t be a list
    if nplots == 1:
        axs = [axs]
    if x_hist.ndim == 1:
        # print('Pseudo Transient finished')
        return x_new, init_guess

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._algebraic_vars[start:end]:
            axs[i].plot(x_hist[:, region_solver.uid2idx_vars[var.uid]], label=var.name)
        axs[i].set_ylabel("Value")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")

    nvars = len(region_solver._diff_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)
    if nplots == 1:
        axs = [axs]

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._diff_vars[start:end]:
            axs[i].plot(dx_hist[:, region_solver.uid2idx_diff[var.uid]], label=f"d{var.base_var.name}")
        axs[i].set_ylabel("dx")
        axs[i].set_yscale("symlog")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")
    plt.tight_layout()
    plt.show()
    # print('Pseudo Transient finished')

    return x_new, init_guess

def pseudo_transient_daes(region_solver, x0, init_guess={}, plot=True, dtau0=1e0, h=1e-3, beta=0.8, tol=1e-5,
                          predictor=False, max_iter: float = 8e4, max_tries=200, verbose=False):
    # Init pseudo transient method, Block only has algebraic eqs
    lag = np.zeros(len(region_solver.uid2idx_lag))
    dtau = dtau0
    init_guess_uid = [var.uid for var in init_guess.keys()]

    for var in region_solver._algebraic_vars:
        if not var.uid in init_guess_uid:
            continue
        idx = region_solver.uid2idx_vars[var.uid]
        x0[idx] = init_guess[var]
    for i in range(len(x0)):
        if x0[i] == 0:
            _ = 0
            x0[i] = 0.1 + 0.5 * np.random.rand()
    for i in range(len(lag)):
        base_var = region_solver._lag_vars[i].base_var
        lag[i] = x0[region_solver.uid2idx_vars[base_var.uid]]
        if lag[i] == 0:
            lag[i] += 0.1 + np.random.rand()

    y = np.empty((5, region_solver._n_vars))
    step_idx = 0
    x_new = x0.copy()
    tries = 0
    current_time = 0
    params_current = region_solver._params_fn(float(current_time))
    params_outer = params_current.copy()
    params_outer[-1] = 1e-3
    dx_error = 1
    residual = 10
    newton_residual = 10
    old_residual = 10

    # history containers
    dtau_hist = []
    dx_error_hist = []
    residual_hist = []
    x_hist = []
    dx_hist = []

    x_old_iter = np.r_[x_new, lag]
    while step_idx < max_iter:
        xn = y[-1]
        params_current[-1] = dtau

        xn_lags = np.r_[xn, lag]
        xnew_lags = np.r_[x_new, lag]
        rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
        if verbose:
            print(f'Pseudo transient step started with max_iter {max_iter} and step idx {step_idx} and try {tries}')
        if tries > 1:
            x_predicted, x_feasible = region_solver.predictor(region_solver, x_old=xnew_lags, max_step=5e3, params=params_current)
        else:
            x_predicted, x_feasible = region_solver.predictor(region_solver, x_old=x_old_iter, max_step=5e3, params=params_current)
        for i in range(1):
            _ = 0
            if tries > 1:
                x_corrected, x_feasible = region_solver.corrector(region_solver, x_predicted, x_feasible, x_feasible, params_current)
            else:
                x_corrected, x_feasible = region_solver.corrector(region_solver, x_predicted, x_old_iter, x_feasible, params_current)
            x_predicted = x_corrected
        xnew_lags[:len(x_feasible)] = x_feasible
        # 1 Handle first-order derivatives first
        for i, var in enumerate(region_solver._diff_vars):
            if var.diff_order != 1:
                continue
            base_var_uid = region_solver.uid2idx_vars[var.base_var.uid]
            xnew_lags[base_var_uid] = x_predicted[i]

        newton_residual = np.linalg.norm(rhs)
        converged = newton_residual < tol
        if verbose:
            _ = 0
            print(f'residual is {rhs} try is {tries} and x is {x_new}')

        step_idx += 1
        y = np.roll(y, shift=-1, axis=0)
        alpha = 1.0
        if step_idx > 2:
            y[-1] = alpha * x_new + (1 - alpha) * y[-1]
        else:
            y[-1] = alpha * x_new
        x_new = y[-1]

        # save history
        rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_outer, 1, dtau)
        dtau_hist.append(dtau)
        dx_hist.append(region_solver.compute_dx(x_new, lag, dtau).copy())
        dx_error_hist.append(np.linalg.norm(dx_hist[-1]))
        residual_hist.append(np.linalg.norm(rhs))
        x_hist.append(x_new.copy())
        print(
            f'Convergence achieved for dtau={dtau:.2e}, ||dx||={dx_error:.2e}, residual={residual:.2e}, step {step_idx}')

        for i, lag_var in enumerate(region_solver._lag_vars):
            if lag_var.lag == 0:
                uid = lag_var.base_var.uid
                idx = region_solver.uid2idx_vars[uid]
                lag[i] = x_new[idx]
            elif step_idx + 1 - (lag_var.lag - 1) >= 0:
                uid = lag_var.base_var.uid
                idx = region_solver.uid2idx_vars[uid]
                lag[i] = y[-1 - lag_var.lag, idx]
            else:
                lag_name = lag_var.base_var.name + '_lag_' + str(lag_var.lag - 1)
                next_lag_var = LagVar.get_or_create(lag_name, base_var=lag_var.base_var, lag=lag_var.lag - 1)
                uid = next_lag_var.uid
                idx = region_solver.uid2idx_lag[uid]
                lag[i] = lag[idx]
        old_residual = residual
        x_old_iter = np.r_[x_new, lag]

        if converged:
            break
        elif tries > max_tries:
            raise ConvergenceError(f"Max tries reached at dtau={dtau:.2e}, residual={residual:.2e}")

    init_guess = {var: x_new[region_solver.uid2idx_vars[var.uid]] for var in region_solver._algebraic_vars}

    if not plot:
        return x_new, init_guess
    # --- Plotting section ---
    fig, axs = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    axs[0].semilogy(dx_error_hist, label="||dx||")
    axs[0].set_ylabel("dx error (log)")
    axs[0].legend()

    axs[1].semilogy(residual_hist, label="Residual norm")
    axs[1].set_ylabel("Residual (log)")
    axs[1].legend()

    axs[2].semilogy(dtau_hist, label="dtau")
    axs[2].set_ylabel("dtau")
    axs[2].set_xlabel("Step index")
    axs[2].legend()

    # --- Plot actual variables ---
    x_hist = np.array(x_hist)  # shape: (n_steps, n_vars)
    dx_hist = np.array(dx_hist)  # shape: (n_steps, n_vars)

    nvars = len(region_solver._algebraic_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)

    # if there’s only one subplot, axs won’t be a list
    if nplots == 1:
        axs = [axs]
    if x_hist.ndim == 1:
        # print('Pseudo Transient finished')
        return x_new, init_guess

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._algebraic_vars[start:end]:
            axs[i].plot(x_hist[:, region_solver.uid2idx_vars[var.uid]], label=var.name)
        axs[i].set_ylabel("Value")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")

    nvars = len(region_solver._diff_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)
    if nplots == 1:
        axs = [axs]

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._diff_vars[start:end]:
            axs[i].plot(dx_hist[:, region_solver.uid2idx_diff[var.uid]], label=f"d{var.base_var.name}")
        axs[i].set_ylabel("dx")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")
    plt.tight_layout()
    plt.show()
    # print('Pseudo Transient finished')

    return x_new, init_guess

def pseudo_transient_explicit(region_solver, x0, init_guess={}, plot=True, dtau0=1e0, h=1e-3, beta=0.8, tol=1e-5,
                              predictor=False, max_iter=8e4, max_tries=200, verbose=False):
    # Init pseudo transient method, Block only has algebraic eqs
    if region_solver._n_state == 0:
        raise ('System is not in explicit form')
    lag = np.zeros(len(region_solver.uid2idx_lag))
    dtau = dtau0
    init_guess_uid = [var.uid for var in init_guess.keys()]

    for var in region_solver._algebraic_vars:
        if not var.uid in init_guess_uid:
            continue
        idx = region_solver.uid2idx_vars[var.uid]
        x0[idx] = init_guess[var]
    for i in range(len(x0)):
        if x0[i] == 0:
            _ = 0
            x0[i] = 0.1 + 0.5 * np.random.rand()
    for i in range(len(lag)):
        base_var = region_solver._lag_vars[i].base_var
        lag[i] = x0[region_solver.uid2idx_vars[base_var.uid]]
        if lag[i] == 0:
            lag[i] += 0.1 + np.random.rand()

    y = np.empty((5, region_solver._n_vars))
    step_idx = 0
    x_new = x0.copy()
    tries = 0
    current_time = 0
    params_current = region_solver._params_fn(float(current_time))
    params_outer = params_current.copy()
    params_outer[-1] = 1e-3
    dx_error = 1
    residual = 10
    newton_residual = 10
    old_residual = 10

    # history containers
    dtau_hist = []
    dx_error_hist = []
    residual_hist = []
    x_hist = []
    dx_hist = []

    x_old_iter = np.r_[x_new, lag]
    while step_idx < max_iter:
        xn = y[-1]
        params_current[-1] = dtau

        xn_lags = np.r_[xn, lag]
        xnew_lags = np.r_[x_new, lag]
        rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
        if verbose:
            print(f'Pseudo transient step started with max_iter {max_iter} and step idx {step_idx} and try {tries}')
        if tries > 1:
            x_predicted, x_feasible = region_solver.predictor(region_solver, x_old=xnew_lags, max_step=5e3, params=params_current)
        else:
            x_predicted, x_feasible = region_solver.predictor(region_solver, x_old=x_old_iter, max_step=5e3, params=params_current)
        for i in range(1):
            _ = 0
            if tries > 1:
                x_corrected, x_feasible = region_solver.corrector(region_solver, x_predicted, x_feasible, x_feasible, params_current)
            else:
                x_corrected, x_feasible = region_solver.corrector(region_solver, x_predicted, x_old_iter, x_feasible, params_current)
            x_predicted = x_corrected
        xnew_lags[:len(x_feasible)] = x_feasible
        # 1 Handle first-order derivatives first
        for i, var in enumerate(region_solver._diff_vars):
            if var.diff_order != 1:
                continue
            base_var_uid = region_solver.uid2idx_vars[var.base_var.uid]
            xnew_lags[base_var_uid] = x_predicted[i]

        newton_residual = np.linalg.norm(rhs)
        converged = newton_residual < tol
        if verbose:
            _ = 0
            print(f'residual is {rhs} try is {tries} and x is {x_new}')

        step_idx += 1
        y = np.roll(y, shift=-1, axis=0)
        alpha = 1.0
        if step_idx > 2:
            y[-1] = alpha * x_new + (1 - alpha) * y[-1]
        else:
            y[-1] = alpha * x_new
        x_new = y[-1]

        # save history
        rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_outer, 1, dtau)
        dtau_hist.append(dtau)
        dx_hist.append(region_solver.compute_dx(x_new, lag, dtau).copy())
        dx_error_hist.append(np.linalg.norm(dx_hist[-1]))
        residual_hist.append(np.linalg.norm(rhs))
        x_hist.append(x_new.copy())
        print(
            f'Convergence achieved for dtau={dtau:.2e}, ||dx||={dx_error:.2e}, residual={residual:.2e}, step {step_idx}')

        for i, lag_var in enumerate(region_solver._lag_vars):
            if lag_var.lag == 0:
                uid = lag_var.base_var.uid
                idx = region_solver.uid2idx_vars[uid]
                lag[i] = x_new[idx]
            elif step_idx + 1 - (lag_var.lag - 1) >= 0:
                uid = lag_var.base_var.uid
                idx = region_solver.uid2idx_vars[uid]
                lag[i] = y[-1 - lag_var.lag, idx]
            else:
                lag_name = lag_var.base_var.name + '_lag_' + str(lag_var.lag - 1)
                next_lag_var = LagVar.get_or_create(lag_name, base_var=lag_var.base_var, lag=lag_var.lag - 1)
                uid = next_lag_var.uid
                idx = region_solver.uid2idx_lag[uid]
                lag[i] = lag[idx]
        old_residual = residual
        x_old_iter = np.r_[x_new, lag]

        if converged:
            break
        elif tries > max_tries:
            raise ConvergenceError(f"Max tries reached at dtau={dtau:.2e}, residual={residual:.2e}")

    init_guess = {var: x_new[region_solver.uid2idx_vars[var.uid]] for var in region_solver._algebraic_vars}

    if not plot:
        return x_new, init_guess
    # --- Plotting section ---
    fig, axs = plt.subplots(3, 1, figsize=(8, 10), sharex=True)

    axs[0].semilogy(dx_error_hist, label="||dx||")
    axs[0].set_ylabel("dx error (log)")
    axs[0].legend()

    axs[1].semilogy(residual_hist, label="Residual norm")
    axs[1].set_ylabel("Residual (log)")
    axs[1].legend()

    axs[2].semilogy(dtau_hist, label="dtau")
    axs[2].set_ylabel("dtau")
    axs[2].set_xlabel("Step index")
    axs[2].legend()

    # --- Plot actual variables ---
    x_hist = np.array(x_hist)  # shape: (n_steps, n_vars)
    dx_hist = np.array(dx_hist)  # shape: (n_steps, n_vars)

    nvars = len(region_solver._algebraic_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)

    # if there’s only one subplot, axs won’t be a list
    if nplots == 1:
        axs = [axs]
    if x_hist.ndim == 1:
        # print('Pseudo Transient finished')
        return x_new, init_guess

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._algebraic_vars[start:end]:
            axs[i].plot(x_hist[:, region_solver.uid2idx_vars[var.uid]], label=var.name)
        axs[i].set_ylabel("Value")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")

    nvars = len(region_solver._diff_vars)
    vars_per_plot = 5
    nplots = (nvars + vars_per_plot - 1) // vars_per_plot

    fig, axs = plt.subplots(nplots, 1, figsize=(10, 2.5 * nplots), sharex=True)
    if nplots == 1:
        axs = [axs]

    for i in range(nplots):
        start = i * vars_per_plot
        end = min((i + 1) * vars_per_plot, nvars)
        for var in region_solver._diff_vars[start:end]:
            axs[i].plot(dx_hist[:, region_solver.uid2idx_diff[var.uid]], label=f"d{var.base_var.name}")
        axs[i].set_ylabel("dx")
        axs[i].legend(loc="best", fontsize="x-small", ncol=2, frameon=False)
    axs[-1].set_xlabel("Step index")
    plt.tight_layout()
    plt.show()
    # print('Pseudo Transient finished')

    return x_new, init_guess

def compile_implicit_predictor(region_solver):

    uid2sym_diffvars = dict()
    uid2sym_vars = region_solver.uid2sym_vars.copy()
    uid2sym_params = region_solver.uid2sym_params.copy()
    uid2sym_params_predictor = region_solver.uid2sym_params.copy()

    i = 0
    j = len(uid2sym_params)
    for ep in region_solver._diff_vars:
        uid2sym_diffvars[ep.uid] = f"vars[{i}]"
        uid2sym_params[ep.uid] = f"params[{j}]"
        i += 1
        j += 1

    j = len(uid2sym_params_predictor)
    for ep in region_solver._algebraic_vars:
        uid2sym_params_predictor[ep.uid] = f"params[{j}]"
        j += 1

    region_solver._rhs_predictor = _compile_equations(eqs=region_solver._algebraic_eqs, uid2sym_vars=uid2sym_vars,
                                             uid2sym_params=uid2sym_params)

    region_solver._Jf_predictor = region_solver._get_jacobian(eqs=region_solver._algebraic_eqs, variables=region_solver._diff_vars,
                                            uid2sym_vars=uid2sym_diffvars,
                                            uid2sym_params=uid2sym_params_predictor, dt=region_solver.dt, substitute=False)

    region_solver._algebraic_eqs_stable = []
    region_solver._diff_eq_index = []
    for i, eq in enumerate(region_solver._algebraic_eqs):
        eq_save = eq
        for diff_var in region_solver._diff_vars:
            eq = eq.subs({diff_var: Const(0)})
        if str(eq_save) != str(eq):
            continue
        eq = eq.simplify()
        region_solver._algebraic_eqs_stable.append(eq)
        region_solver._diff_eq_index.append(i)

    print(len(region_solver._algebraic_eqs_stable))
    region_solver._Jf_feasible = region_solver._get_jacobian(eqs=region_solver._algebraic_eqs_stable, variables=region_solver._algebraic_vars,
                                           uid2sym_vars=region_solver.uid2sym_vars,
                                           uid2sym_params=region_solver.uid2sym_params, dt=region_solver.dt, substitute=False)
    region_solver._rhs_feasible = _compile_equations(eqs=region_solver._algebraic_eqs_stable, uid2sym_vars=region_solver.uid2sym_vars,
                                            uid2sym_params=region_solver.uid2sym_params)

    def rhs_predictor(x_new, x_old, params):
        dt = params[-1]
        dx = np.zeros(len(region_solver._diff_vars))
        x_aux = np.zeros(len(region_solver.uid2sym_vars))
        x_aux[:len(x_old)] = x_old
        for i, var in enumerate(region_solver._diff_vars):
            id = region_solver.uid2idx_vars[var.origin_var.uid]
            if var.base_var.uid == var.origin_var.uid:
                dx[i] = (x_new[i] - x_old[id]) / dt
            else:
                xold_expression, _ = var.approximation_expr(dt, lag_can_be_0=False)
                vars_to_substitute = [var.origin_var]
                vars_to_substitute += [LagVar.get_or_create(name='a', base_var=var.origin_var, lag=i) for i in
                                       range(1, var.diff_order + 1)]
                subs = {}
                for var_to_sub in vars_to_substitute:
                    var_idx = region_solver.uid2idx_vars[var_to_sub.uid]
                    subs[var_to_sub] = Const(x_old[var_idx])
                xold_value = xold_expression.subs(subs).simplify().value
                dx[i] = (x_new[i] - xold_value) / dt

        params = np.r_[params, dx]
        rhs = region_solver._rhs_predictor(x_aux, params)
        return rhs

    def Jf_predictor(x_new, x_old, params):
        dt = params[-1]
        dx = np.zeros(len(region_solver._diff_vars))
        for i, var in enumerate(region_solver._diff_vars):
            id = region_solver.uid2idx_vars[var.origin_var.uid]
            if var.base_var.uid == var.origin_var.uid:
                dx[i] = (x_new[i] - x_old[id]) / dt
            else:
                xold_expression, _ = var.approximation_expr(dt, lag_can_be_0=False)
                vars_to_substitute = [var.origin_var]
                vars_to_substitute += [LagVar.get_or_create(name='a', base_var=var.origin_var, lag=i) for i in
                                       range(1, var.diff_order + 1)]
                subs = {}
                for var_to_sub in vars_to_substitute:
                    var_idx = region_solver.uid2idx_vars[var_to_sub.uid]
                    subs[var_to_sub] = Const(x_old[var_idx])
                xold_value = xold_expression.subs(subs).simplify().value
                dx[i] = (x_new[i] - xold_value) / dt

        x_old = x_old[:region_solver._n_alg]
        params = np.r_[params, x_old]
        Jf = region_solver._Jf_predictor(dx, params) * (1 / dt)
        return Jf

    def rhs_corrector(x_new, x_mid, x_old, params):
        dt = params[-1]
        dx = np.zeros(len(region_solver._diff_vars))
        x_aux = np.zeros(len(region_solver.uid2sym_vars))
        x_aux[:len(x_mid)] = x_mid
        for i, var in enumerate(region_solver._diff_vars):
            id = region_solver.uid2idx_vars[var.origin_var.uid]
            if var.base_var.uid == var.origin_var.uid:
                dx[i] = (x_new[i] - x_old[id]) / dt
            else:
                xold_expression = var.approximation_expr(dt)
                vars_to_substitute = [var.origin_var]
                vars_to_substitute += [LagVar.get_or_create(base_var=var.origin_var, lag=i) for i in
                                       range(1, var.diff_order + 1)]
                subs = {}
                for var_to_sub in vars_to_substitute:
                    var_idx = region_solver.uid2idx_vars[var_to_sub.uid]
                    subs[var_to_sub] = x_old[var_idx]
                xold_value = xold_expression.subs(subs).simplify()
                dx[i] = (x_new[i] - xold_value) / dt

        params = np.r_[params, dx]
        rhs = region_solver._rhs_predictor(x_aux, params)
        return rhs

    def Jf_corrector(x_new, x_mid, x_old, params):
        dt = params[-1]
        dx = np.zeros(len(region_solver._diff_vars))
        for i, var in enumerate(region_solver._diff_vars):
            id = region_solver.uid2idx_vars[var.origin_var.uid]
            if var.base_var.uid == var.origin_var.uid:
                dx[i] = (x_new[i] - x_old[id]) / dt
            else:
                xold_expression = var.approximation_expr(dt)
                vars_to_substitute = [var.origin_var]
                vars_to_substitute += [LagVar.get_or_create(base_var=var.origin_var, lag=i) for i in
                                       range(1, var.diff_order + 1)]
                subs = {}
                for var_to_sub in vars_to_substitute:
                    var_idx = region_solver.uid2idx_vars[var_to_sub.uid]
                    subs[var_to_sub] = x_old[var_idx]
                xold_value = xold_expression.subs(subs).simplify()
                dx[i] = (x_new[i] - xold_value) / dt

        x_mid = x_mid[:region_solver._n_alg]
        params = np.r_[params, x_mid]
        Jf = region_solver._Jf_predictor(dx, params) * (1 / dt)
        return Jf

    def Jf_feasible(x, params):
        x_aux = np.zeros(len(region_solver.uid2sym_vars))
        x_aux[:len(x)] = x
        Jf = region_solver._Jf_feasible(x_aux, params)
        return Jf

    def rhs_feasible(x, params):
        x_aux = np.zeros(len(region_solver.uid2sym_vars))
        x_aux[:len(x)] = x
        rhs = region_solver._rhs_feasible(x_aux, params)
        return rhs

    def Jf_with_fix_x(x, params, fix_idx):
        # Create an auxiliary array (same length as the full set of variables)
        fix_idx = np.array(fix_idx)
        x_aux = np.zeros(len(region_solver.uid2sym_vars))
        x_aux[:len(x)] = x  # Fill with the given values of x

        # Compute the full Jacobian
        Jf = region_solver._Jf_feasible(x_aux, params)

        # Sparse case → mask unwanted columns
        Jf = Jf.tocsc()
        mask = np.ones(Jf.shape[1], dtype=bool)
        mask[fix_idx] = False

        # Keep only the non-fixed columns
        Jf_reduced = Jf[:, mask]

        return Jf_reduced

    region_solver.rhs_predictor = rhs_predictor
    region_solver.Jf_predictor = Jf_predictor
    region_solver.Jf_feasible = Jf_feasible
    region_solver.rhs_feasible = rhs_feasible
    region_solver.Jf_corrector = Jf_corrector
    region_solver.rhs_corrector = rhs_corrector
    region_solver.Jf_feasible_fixed_x = Jf_with_fix_x

    # print("Predictor-Corrector Compiled")
    return

def find_feasible_point(region_solver, xn, params, x0=None, max_steps=2e3, tol=1e-4):
    residual = 10
    h = 1e-3
    dt = params[-1]
    j = 0
    if len(xn) == region_solver._n_diff:
        if x0 is None:
            print('xo is random.')
            xaux = np.random.rand(region_solver._n_alg)
        else:
            xaux = x0
            # 1 Handle first-order derivatives first
            for i, var in enumerate(region_solver._diff_vars):
                if var.diff_order != 1:
                    continue
                base_var_uid = region_solver.uid2idx_vars[var.base_var.uid]
                xaux[base_var_uid] = xn[i]

            # 2 Sort differential variables by diff_order before building lags
            diff_vars_sorted = sorted(region_solver._diff_vars, key=lambda v: v.diff_order)

            # 3 Build lag variables in increasing order of diff_order
            for i, var in enumerate(diff_vars_sorted):
                if var.diff_order <= 1:
                    continue

                origin_var = var.origin_var
                diff_order = var.diff_order

                # Previous lag (order-1)
                prev_lag = LagVar.get_or_create(
                    name=f"{origin_var.name}_lag{diff_order - 1}",
                    base_var=origin_var,
                    lag=diff_order - 1,
                )
                prev_lag_uid = region_solver.uid2idx_vars[prev_lag.uid]

                # Current lag
                lag_var = LagVar.get_or_create(
                    name=f"{origin_var.name}_lag{diff_order}",
                    base_var=origin_var,
                    lag=diff_order,
                )
                lag_uid = region_solver.uid2idx_vars[lag_var.uid]

                # Recursive lag update: x_lag_n = x_lag_(n-1) − h * x^(n)
                xaux[lag_uid] = xaux[prev_lag_uid] - params[-1] * xn[i]

            xn = xaux
    elif len(xn) == region_solver._n_alg:
        _ = 0
    else:
        raise Exception('Length of xn is not n_diff or n_alg')

    for i in range(len(xn)):
        if xn[i] == 0:
            xn[i] += 0.2 * np.random.rand()
    if not hasattr(region_solver, 'Jf_feasible'):
        region_solver.compile_implicit_predictor(region_solver)

    alpha = 1
    step = 0
    while residual > tol and step < max_steps:
        x_old = xn
        j += 1
        lags = np.random.rand(len(region_solver._lag_vars))
        x = np.r_[xn, lags]
        # print(f'x is {x}')
        rhs = region_solver.rhs_feasible(x, params)
        Jf = region_solver.Jf_feasible(x, params)
        delta = sp.linalg.lsqr(Jf, -rhs)[0]
        # print(f'delta is {len(delta)}')
        xn += delta
        xn = alpha * xn + (1 - alpha) * x_old
        rhs = region_solver.rhs_feasible(x, params)
        residual = np.linalg.norm(rhs)
        ##print(f'residual is {residual}, step is {step}')
        step += 1

    if residual < tol:
        print(f'Feasible point found')
    else:
        print(f'Feasible solver failed')

    xn_aux = np.zeros(region_solver._n_vars)
    xn_aux[:len(xn)] = xn
    for i, var in enumerate(region_solver._diff_vars):
        if var.diff_order > 1:
            continue
        id = region_solver.uid2idx_vars[var.origin_var.uid]
        xn_aux[id] = xn[id]
    for lag_var in region_solver._lag_vars:
        lag_id = region_solver.uid2idx_lag[lag_var.uid]
        var_id = region_solver.uid2idx_vars[lag_var.base_var.uid]
        lags[lag_id] = xn[var_id]

    xn_aux = np.r_[xn_aux, lags]
    rhs = region_solver.rhs_implicit(xn_aux, xn_aux, params, 0, 1e-3)
    residual_implicit = np.linalg.norm(rhs)
    # print(f'End of feasible point residual is {residual}, implicit res is {residual_implicit} x_new_compl is of length {len(xn)}')
    return xn

def build_x_y(region_solver, x, y):
    diff_base_var_uids = [diff_var.base_var.uid for diff_var in region_solver._diff_vars]
    res = np.zeros(len(x) + len(y))
    i_x = 0
    i_y = 0
    for var in region_solver._algebraic_vars:
        var_id = region_solver.uid2idx_vars[var.uid]
        if var.uid in diff_base_var_uids:
            res[var_id] = x[i_x]
            i_x += 1
        else:
            res[var_id] = y[i_y]
            i_y += 1

    return res

def find_feasible_given_x(region_solver, x, x_old, params, max_steps=5e3, tol=1e-3):
    residual = 10
    h = 1e-3
    j = 0
    diff_base_vars = [diff_var.origin_var for diff_var in region_solver._diff_vars]
    diff_base_vars_uid = [diff_var.base_var.uid for diff_var in region_solver._diff_vars]
    x_index = [region_solver.uid2idx_vars[var.uid] for var in diff_base_vars]
    y_index = [i for i in range(region_solver._n_alg) if i not in x_index]

    y = np.ones(region_solver._n_alg - len(x))
    i_xold = 0
    for var in region_solver._algebraic_vars:
        if var.uid in diff_base_vars_uid:
            continue
        var_id = region_solver.uid2idx_vars[var.uid]
        y[i_xold] = x_old[var_id]
        i_xold += 1

    if not hasattr(region_solver, 'Jf_feasible'):
        region_solver.compile_implicit_predictor()

    alpha = 1
    step = 0
    scale = False
    regularize = False
    while residual > tol and step < max_steps:
        j += 1
        x_y = region_solver.build_x_y(region_solver, x, y)
        rhs = region_solver.rhs_feasible(x_y, params)
        Jf = region_solver.Jf_feasible(x_y, params)
        delta = sp.linalg.lsmr(Jf, -rhs)[0]
        x += 0.1 * delta[x_index]
        y += delta[y_index]
        residual = np.linalg.norm(rhs)

        # print(f'residual is {residual}, rhs is {rhs}, step is {step}, delta is {Jf}')
        step += 1

    if step == max_steps:
        raise Exception('Convergence algorithm failed in the allowed number of steps.')
    else:
        _ = 0
        print(f'Found feasible y(x)')
    return x_y

def predictor(region_solver, x_old, params, max_step=1e3, tol=1e-4):
    x_new = np.random.rand(len(region_solver._diff_vars))
    residual = 10
    step = 0
    if not hasattr(region_solver, 'rhs_predictor'):
        region_solver.compile_implicit_predictor()

    x_feasible = region_solver.find_feasible_point(region_solver, x_old[:region_solver._n_alg], params, x0=x_old[:region_solver._n_alg])
    x_old[:len(x_feasible)] = x_feasible
    for i, var in enumerate(region_solver._diff_vars):
        id = region_solver.uid2idx_vars[var.origin_var.uid]
        x_new[i] = x_feasible[id]

    rhs = region_solver.rhs_predictor(x_new, x_old, params)
    residual = np.linalg.norm(rhs)
    while residual > tol and step < max_step:
        step += 1
        rhs = region_solver.rhs_predictor(x_new, x_old, params)
        Jf = region_solver.Jf_predictor(x_new, x_old, params)
        delta = sp.linalg.lsqr(Jf, -rhs)[0]
        x_new += delta
        residual = np.linalg.norm(rhs)
        ##print(f'Loop Predictor residual is {residual} for step {step}')

    lags = np.zeros(len(region_solver._lag_vars))
    lags1 = lags.copy()
    lags2 = lags.copy()
    x_aux = x_old.copy()[:region_solver._n_alg]

    for i, var in enumerate(region_solver._diff_vars):
        id = region_solver.uid2idx_vars[var.origin_var.uid]
        x_feasible[id] = x_new[i]
    try:
        x_y = region_solver.find_feasible_given_x(region_solver, x_new, x_feasible, params, max_steps=1e4)
        x_y_comp = np.r_[x_y, lags]
        rhs1 = region_solver.rhs_implicit(x_y_comp, x_y, params, 0, 1e-3)
        residual1 = np.linalg.norm(rhs1)
        # print(f'End of predictor residual is {residual1}, x_y is of length {len(x_y_comp)}')
    except:
        # print(f'Find feasible x failed')
        _ = 0

    for var in region_solver._diff_vars:
        base_var_id = region_solver.uid2idx_vars[var.origin_var.uid]
        diff_var_id = region_solver.uid2idx_diff[var.uid]
        x_aux[base_var_id] = x_new[diff_var_id]
    for lag_var in region_solver._lag_vars:
        lag_id = region_solver.uid2idx_lag[lag_var.uid]
        var_id = region_solver.uid2idx_vars[lag_var.base_var.uid]
        lags[lag_id] = x_old[var_id]
        lags2[lag_id] = x_aux[var_id]

    x_new_comp = np.r_[x_aux, lags]
    # x_new = x_new_comp
    # print(f'End of predictor residual is {residual2}, x_new_compl is of length {len(x_new_comp)}')
    return x_new, x_feasible

def corrector(region_solver, x_predicted, x_old, x_feasible, params, max_step=10, tol=1e-3):
    x_new = np.zeros(len(region_solver._diff_vars))
    residual = 10
    x_old = x_old[:region_solver._n_alg]
    step = 0
    x_old_limited = np.zeros(len(region_solver._diff_vars))
    for var in region_solver._diff_vars:
        base_var_id = region_solver.uid2idx_vars[var.origin_var.uid]
        diff_var_id = region_solver.uid2idx_diff[var.uid]
        x_old_limited[diff_var_id] = x_old[base_var_id]

    try:
        x_predicted = region_solver.find_feasible_given_x(region_solver, x_predicted, x_feasible, params)
    except Exception as e:
        msg = str(e)
        print(msg)
        print('given x failed')
        x_predicted = region_solver.find_feasible_point(region_solver, x_predicted, params, x0=x_feasible)
    try:
        x_old = region_solver.find_feasible_given_x(region_solver, x_old_limited, x_feasible, params)
    except:
        print('given x failed')
        x_old = region_solver.find_feasible_point(region_solver, x_old_limited, params, x0=x_feasible)
    for i, var in enumerate(region_solver._diff_vars):
        id = region_solver.uid2idx_vars[var.base_var.uid]
        x_new[i] = x_predicted[id]

    alpha = 1.0
    x_mid = alpha * (x_predicted) + (1 - alpha) * x_old
    lags = np.zeros(len(region_solver._lag_vars))
    for lag_var in region_solver._lag_vars:
        lag_id = region_solver.uid2idx_lag[lag_var.uid]
        var_id = region_solver.uid2idx_vars[lag_var.base_var.uid]
        lags[lag_id] = x_old[var_id]

    x_predicted_withlags = np.r_[x_predicted, lags]
    rhs = region_solver.rhs_implicit(x_predicted_withlags, x_predicted, params, 0, 1e-3)
    residual = np.linalg.norm(rhs)

    ##print(f'x_predicted of length {len(x_predicted)}')
    # print(f'Initial corrector {residual}, x_new is of length {len(x_new)}')
    while residual > tol and step < max_step:
        rhs = region_solver.rhs_corrector(x_new, x_mid, x_old, params)
        Jf = region_solver.Jf_corrector(x_new, x_mid, x_old, params)
        delta = sp.linalg.lsqr(Jf, -rhs)[0]
        x_new += delta

        residual = np.linalg.norm(rhs)
        step += 1
        # print(f'Corrector Loop residual is {residual} for step {step} delta_norrm is {np.linalg.norm(delta)}, rhs is {rhs}')

    if residual > tol:
        _ = 0
        print('Corrector failed')
        return x_new, x_mid
    else:
        print('Corrector Succeeded')

    for i, var in enumerate(region_solver._diff_vars):
        idx = region_solver.uid2idx_vars[var.origin_var.uid]
        x_mid[idx] = x_new[i]

    return x_new, x_mid

def fixed_point_finder(region_solver, x0=None, tol=1e-4):
    states = set()
    states = {var.base_var for var in region_solver._diff_vars}
    region_solver.states = list(states)
    region_solver.n_states = len(states)
    if x0 is None:
        xstart = np.random.rand(len(region_solver._lag_vars))
    else:
        xstart = np.zeros(len(region_solver._lag_vars))
        for lag in region_solver._lag_vars:
            base_var = lag.base_var
            base_var_idx = region_solver.uid2idx_vars[base_var.uid]
            xstart[region_solver.uid2idx_lag[lag.uid]] = x0[base_var_idx]

    params_current = region_solver._params_fn(float(0))
    T_operator = region_solver.T_operator(region_solver, params_current)
    residual = 10
    alpha = 0.05
    x = xstart.copy()
    while residual > tol:
        x_new = (alpha) * x + (1 - alpha) * T_operator(region_solver, x)
        residual = np.linalg.norm(x_new - x)
        x = x_new
    return x

def T_operator(region_solver, params_current):

    def operator(lags, h=1e-3):
        residual = 10
        x_n = np.zeros(region_solver._n_vars)
        dtau = 1e-6
        for lag in region_solver._lag_vars:
            base_var = lag.base_var
            base_var_idx = region_solver.uid2idx_vars[base_var.uid]
            x_n[base_var_idx] = lags[region_solver.uid2idx_lag[lag.uid]] + 2 * np.random.rand()

        x_new = x_n.copy()

        while residual > 1e-4:
            xn_lags = np.r_[x_n, lags]
            xnew_lags = np.r_[x_new, lags]
            params_current[-1] = dtau

            rhs = region_solver.rhs_implicit(xnew_lags, xn_lags, params_current, 1, dtau)
            Jf = region_solver.jacobian_implicit(xnew_lags, params_current, dtau)
            delta = sp.linalg.spsolve(Jf, -rhs)

            if np.isnan(delta).any() or np.isinf(delta).any():
                delta = sp.linalg.lsqr(Jf, -rhs)[0]

            x_new += delta
            residual = np.linalg.norm(rhs)
            # print(f'residual is {residual}')
        x_states = np.zeros(len(region_solver._lag_vars))

        # We project onto the state variables
        # TODO: return should also be lags
        for lag in region_solver._lag_vars:
            base_var = lag.base_var
            base_var_idx = region_solver.uid2idx_vars[base_var.uid]
            if lag.lag == 1:
                x_states[region_solver.uid2idx_lag[lag.uid]] = x_new[base_var_idx]
            else:
                lag_var = LagVar.get_or_create('name', base_var=base_var, lag=lag.lag - 1)
                x_states[region_solver.uid2idx_lag[lag.uid]] = lags[region_solver.uid2idx_lag[lag_var.uid]]

        return x_states

    return operator





def compose_system_block(time: Var, grid: MultiCircuit,
                          power_flow_results: PowerFlowResults, vars2device:Dict[int, PhysicalDevice], vars_glob_name2uid: Dict[str, int]) -> Tuple[Var, Block, Dict[Tuple[int, str], float]]:

    """
    Compose all RMS models
    :param time: time of the simulation
    :param grid:
    :param power_flow_results:
    :param vars2device: dictionary relating uid of vars with the device they belong to
    :param vars_glob_name2uid: dictionary relating global name of the variable and uid (used when showing results)
    :return: System block and initial guess dictionary
    """
    # already computed grid power flow
    res = power_flow_results

    Sf = res.Sf / grid.Sbase
    St = res.St / grid.Sbase

    # create the system block
    sys_block = Block(children=[], in_vars=[])

    sys_block.vars2device = vars2device
    sys_block.vars_glob_name2uid = vars_glob_name2uid

    # initialize containers
    init_guess: Dict[Tuple[int, str], float] = {}
    sys_vars: list[Tuple[int, str]] = []
    seen_vars: set[Tuple[int, str]] = set()

    uid2sym_vars: Dict[int, str] = {}
    uid2idx_vars: Dict[int, int] = {}
    uid2sym_t: Dict[int, str] = dict()
    uid2idx_t: Dict[int, int] = dict()

    # fill uid2sym_t and uid2idx_t dicts
    array_index_t = 0
    uid2sym_t[time.uid] = f"glob_time"
    uid2idx_t[time.uid] = array_index_t



    array_index = 0

    # buses
    for i, elm in enumerate(grid.buses):

        # get model and model vars
        mdl = elm.rms_model.model
        mdl_vars = mdl.state_vars + mdl.algebraic_vars

        # fill system variables list
        for var in mdl_vars:
            key = (var.uid, var.name)
            if key not in seen_vars:
                sys_vars.append(key)
                seen_vars.add(key)

        # fill uid2sym and uid2idx dicts
        for v in mdl_vars:
            uid2sym_vars[v.uid] = f"vars[{array_index}]"
            uid2idx_vars[v.uid] = array_index
            array_index += 1

        # fill init_guess
        # TODO: initialization from power injections of PFlows results needs
        #  to be addressed when multiple devices are connected to the same bus.
        # (Shunt Load, for the benchmark case, two generators,...)
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Vm].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Vm].name)] = float(np.abs(res.voltage[i]))
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Va].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Va].name)] = float(np.angle(res.voltage[i]))
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.P].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.P].name)] = float(np.real(res.Sbus[i] / grid.Sbase))
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Q].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Q].name)] = float(np.imag(res.Sbus[i] / grid.Sbase))

        sys_block.add(mdl)

    # branches
    for i, elm in enumerate(grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True)):
        mdl = elm.rms_model.model
        mdl_vars = mdl.state_vars + mdl.algebraic_vars

        # fill system variables list
        for var in mdl_vars:
            key = (var.uid, var.name)
            if key not in seen_vars:
                sys_vars.append(key)
                seen_vars.add(key)

        # fill uid2sym and uid2idx dicts
        for v in mdl_vars:
            uid2sym_vars[v.uid] = f"vars[{array_index}]"
            uid2idx_vars[v.uid] = array_index

            array_index += 1

        # fill init_guess
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Pf].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Pf].name)] = Sf[i].real
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Qf].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Qf].name)] = Sf[i].imag
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Pt].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Pt].name)] = St[i].real
        init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Qt].uid,
                    mdl.external_mapping[VarPowerFlowRefferenceType.Qt].name)] = St[i].imag

        sys_block.add(mdl)

    # injections

    # initialize with pseudo_transient
    ## iterate through buses and constuct local system_solver

    bus_regions_dict = grid.get_injection_devices_grouped_by_bus()

    for bus, region in bus_regions_dict.items():
        region_time  = Var('region_time')
        uid2idx_region_vars: Dict[int, int] = dict()
        init_guess_region: Dict[Var, float] = dict()
        vars: List[Var] = list()
        bus_index = grid.buses.index(bus)
        region_system = DiffBlock()
        region_dev_list = list()
        for dev_type, dev_list in region.items():
            for dev in dev_list:
                region_dev_list.append(dev)
        for dev in region_dev_list:
            region_system.children.append(dev.rms_model.model)
            for var in dev.rms_model.model.state_vars:
                vars.append(var)
                init_guess_region[var] = np.random.rand()
            for var in dev.rms_model.model.algebraic_vars:
                vars.append(var)
                init_guess_region[var] = np.random.rand()
        region_array_index = 0
        for var in vars:
            uid2idx_region_vars[var.uid] = array_index
            region_array_index += 1
        x0 = build_init_vars_vector(uid2idx_region_vars, init_guess_region)

        region_solver = DiffBlockSolver(region_system, region_time)

        x0_pst, init_guess_pst = pseudo_transient(bus_index, region_solver, x0, init_guess_region, res, grid)
        for var, value in init_guess_pst:
            init_guess.update({[var.uid, var.name], value})
        sys_block.add(region_system)







    # initialize uid2sym_params dict

    # uid2sym_params: Dict[int, str] = {}
    # uid2idx_params: Dict[int, int] = {}
    #
    # # already known variables:
    #
    # for elm in grid.get_injection_devices_iter():
    #     bus_rms_mdl = elm.bus.rms_model.model
    #     mdl = elm.rms_model.model
    #
    #
    #     init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.P].uid, mdl.external_mapping[VarPowerFlowRefferenceType.P].name)] = init_guess[(bus_rms_mdl.external_mapping[VarPowerFlowRefferenceType.P].uid, bus_rms_mdl.external_mapping[VarPowerFlowRefferenceType.P].name)]
    #     init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Q].uid, mdl.external_mapping[VarPowerFlowRefferenceType.Q].name)] = init_guess[(bus_rms_mdl.external_mapping[VarPowerFlowRefferenceType.Q].uid, bus_rms_mdl.external_mapping[VarPowerFlowRefferenceType.Q].name)]
    #
    #     mdl_vars = mdl.state_vars + mdl.algebraic_vars
    #
    #     for var in mdl_vars:
    #         key = (var.uid, var.name)
    #         if key not in seen_vars:
    #             sys_vars.append(key)
    #             seen_vars.add(key)
    #
    #     for v in mdl_vars:
    #         if v.uid not in uid2sym_vars:
    #             uid2sym_vars[v.uid] = f"vars[{array_index}]"
    #             uid2idx_vars[v.uid] = array_index
    #             array_index += 1
    #
    #     params_array_index = 0
    #
    #     for param in mdl.event_dict.keys():
    #         if param.uid not in uid2sym_params:
    #             uid2sym_params[param.uid] = f"params[{params_array_index}]"
    #             uid2idx_params[param.uid] =params_array_index
    #             params_array_index += 1
    #
    #
    #     # initialize array for model variables
    #     x = np.zeros(len(sys_vars))
    #
    #     # assign initial guesses for known variables
    #     for uid, name in sys_vars:
    #         key = (uid, name)
    #         if key in init_guess:
    #             x[uid2idx_vars[uid]] = init_guess[key]
    #
    #     # initialize array for model params
    #     params_array = np.zeros(len(mdl.event_dict.keys()))
    #
    #     # compute and assign parameters value
    #     for param in mdl.event_dict.keys():
    #         eq = mdl.event_dict[param]
    #         eq_fn = _compile_parameters_equations([eq], uid2sym_t)
    #         param_val = float(eq_fn(0.0))
    #         params_array[uid2idx_params[param.uid]] = param_val

        # initialize missing values with pseudo transient method
        #

        # compute and assign missing init_vars
        #
        # for var in mdl.init_eqs.keys():
        #     key = (var.uid, var.name)
        #     if key in init_guess:
        #         x[uid2idx_vars[var.uid]] = init_guess[key]
        #     else:
        #         eq = mdl.init_eqs[var]
        #         eq_fn = _compile_equation([eq], uid2sym_vars, uid2sym_params)
        #         init_val = float(eq_fn(x, params_array))
        #         init_guess[key] = init_val
        #         x[uid2idx_vars[var.uid]] = init_val
        # # TODO: change model to generator, exciter and governor separated and remove this
        # for var in mdl.fix_vars:
        #     eq = mdl.fix_vars_eqs[var.uid]
        #     eq_fn = _compile_equation([eq], uid2sym_vars, uid2sym_params)
        #     init_val = float(eq_fn(x, params_array))
        #     var.value = init_val
        # sys_block.add(mdl)

    # del buses P, Q
    for i, elm in enumerate(grid.buses):
            mdl = elm.rms_model.model
            del init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.P].uid,
                        mdl.external_mapping[VarPowerFlowRefferenceType.P].name)]
            del init_guess[(mdl.external_mapping[VarPowerFlowRefferenceType.Q].uid,
                        mdl.external_mapping[VarPowerFlowRefferenceType.Q].name)]

    return time, sys_block, init_guess


def setP(P: ObjVec, P_used: BoolVec, k: int, val: object):
    if not P_used[k]:
        P[k] = val
        P_used[k] = 1
    else:
        P[k] += val


def setQ(Q: ObjVec, Q_used: BoolVec, k: int, val: object):
    if not Q_used[k]:
        Q[k] = val
        Q_used[k] = 1
    else:
        Q[k] += val


def initialize_rms(grid: MultiCircuit, power_flow_results, logger: Logger = Logger()):
    """
    Initialize all RMS models
    """

    # create time variable

    time = Var("time")

    # instantiate vars2device  and vars_glob_name2uid dicts

    vars2device:Dict[int, PhysicalDevice] = dict()
    vars_glob_name2uid: Dict[str, int] = dict()
    # find events
    rms_events = grid.rms_events

    # already computed grid power flow

    bus_dict = dict()

    # balance equation arrays
    n = len(grid.buses)
    P: ObjVec = np.zeros(n, dtype=object)
    Q: ObjVec = np.zeros(n, dtype=object)
    P_used = np.zeros(n, dtype=int)
    Q_used = np.zeros(n, dtype=int)



    # initialize buses
    for i, elm in enumerate(grid.buses):
        elm.initialize_rms()
        bus_dict[elm] = i
        for state_var in elm.rms_model.model.state_vars:
            vars2device[state_var.uid] = elm
            vars_glob_name2uid[state_var.name + elm.name] = state_var.uid
        for algeb_var in elm.rms_model.model.algebraic_vars:
            vars2device[algeb_var.uid] = elm
            vars_glob_name2uid[algeb_var.name + elm.name] = algeb_var.uid

    # initialize branches
    for elm in grid.get_branches_iter(add_vsc=True, add_hvdc=True, add_switch=True):
        elm.initialize_rms()
        mdl = elm.rms_model.model
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        # add variable to conservation equations of the bus to which the element is connected
        setP(P, P_used, f, -mdl.E(VarPowerFlowRefferenceType.Pf))
        setP(P, P_used, t, -mdl.E(VarPowerFlowRefferenceType.Pt))
        setQ(Q, Q_used, f, -mdl.E(VarPowerFlowRefferenceType.Qf))
        setQ(Q, Q_used, t, -mdl.E(VarPowerFlowRefferenceType.Qt))

        for state_var in elm.rms_model.model.state_vars:
            vars2device[state_var.uid] = elm
            vars_glob_name2uid[state_var.name + elm.name] = state_var.uid
        for algeb_var in elm.rms_model.model.algebraic_vars:
            vars2device[algeb_var.uid] = elm
            vars_glob_name2uid[algeb_var.name + elm.name] = algeb_var.uid

    # initialize injections
    for elm in grid.get_injection_devices_iter():
        elm.initialize_rms()
        # create dictionary for collecting events of the same parameter

        if elm.rms_model.model.event_dict is not None:
            collect_events = {
                key: {"times": [], "values": []}
                for key in elm.rms_model.model.event_dict.keys()
            }
            # find out if there are events affecting the device parameters
            rms_evts = [rms_evt for rms_evt in rms_events if rms_evt.device_idtag == elm.idtag]
            if len(rms_evts) !=0:
                for rms_evt in rms_evts:
                    collect_events[rms_evt.parameter]["times"].append(rms_evt.time)
                    collect_events[rms_evt.parameter]["values"].append(rms_evt.value)
                    # TODO: implement the function in block: apply_event
                for param, events_info in collect_events.items():
                    default_value = copy.deepcopy(elm.rms_model.model.event_dict[param])
                    elm.rms_model.model.event_dict[param] = piecewise(time, np.array(events_info["times"]),
                                                                  np.array(events_info["values"]), default_value)


        # after applying the events the model has to be "build"
        mdl = elm.rms_model.model
        # add variable to conservation equations of the bus to which the element is connected
        k = bus_dict[elm.bus]
        setP(P, P_used, k, mdl.E(VarPowerFlowRefferenceType.P))
        setQ(Q, Q_used, k, mdl.E(VarPowerFlowRefferenceType.Q))

        for state_var in elm.rms_model.model.state_vars:
            vars2device[state_var.uid] = elm
            vars_glob_name2uid[state_var.name + elm.name] = state_var.uid
        for algeb_var in elm.rms_model.model.algebraic_vars:
            vars2device[algeb_var.uid] = elm
            vars_glob_name2uid[algeb_var.name + elm.name] = algeb_var.uid

    # add the nodal balance equations
    for i, elm in enumerate(grid.buses):
        mdl = elm.rms_model.model
        if len(mdl.algebraic_eqs) == 0:
            if P_used[i] == 0 and Q_used[i] == 0:
                logger.add_error("Isolated bus", value=i)
            else:
                mdl.algebraic_eqs.append(P[i])
                mdl.algebraic_eqs.append(Q[i])

    return compose_system_block(time, grid, power_flow_results, vars2device, vars_glob_name2uid)
