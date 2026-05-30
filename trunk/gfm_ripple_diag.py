# SPDX-License-Identifier: MPL-2.0
"""Diagnose the Pe/Qe ripple in the GFM EMT load-step simulation."""
import os
import sys
from typing import Any, cast

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfm_emt_droop_examples import (  # noqa: E402
    build_dc_fed_gfm_island, EVENT_TIME, R_STEP_VALUE, SIM_TIME, TIME_STEP,
    _find_name_in_block,
)
import VeraGridEngine.api as gce  # noqa: E402
from VeraGridEngine.Devices.Events.emt_event import EmtEvent  # noqa: E402
from VeraGridEngine.Devices.Events.emt_events_group import EmtEventsGroup  # noqa: E402
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions  # noqa: E402
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae  # noqa: E402
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver  # noqa: E402
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions  # noqa: E402
from VeraGridEngine.enumerations import (  # noqa: E402
    DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, SolverType,
)

USE_RL = "--rl" in sys.argv
print(f"main line model: {'symmetric RL' if USE_RL else 'Bergeron (travelling-wave)'}")
grid, vsc, load, R_A, R_B, R_C = build_dc_fed_gfm_island(
    kdp=0.05, kdq=0.05, use_rl_main_line=USE_RL)
pf = gce.power_flow(grid=grid, options=PowerFlowOptions(
    solver_type=SolverType.NR, retry_with_other_methods=True, max_iter=50, tolerance=1e-6))
assert pf.converged

eg = EmtEventsGroup(name="step")
grid.add_emt_events_group(eg)
for pr in (R_A, R_B, R_C):
    grid.add_emt_event(EmtEvent(device=load, parameter=pr, time=EVENT_TIME,
                                value=R_STEP_VALUE, group=eg))

opt = EmtOptions(time_step=TIME_STEP, simulation_time=SIM_TIME, tolerance=1e-6,
                 solver_type=EmtSolverTypes.Symbolic,
                 initialization_method=EmtInitializationMethod.Auto,
                 integration_method=DynamicIntegrationMethod.DaeBackEuler, verbose=0)
prob = EmtProblemDae(grid=grid, options=opt, pf_results_3ph=None, pf_results=pf)
prob.set_events_group(eg)
solver = JitSymbolicSolver(problem=prob, t0=0.0, t_end=SIM_TIME, h=TIME_STEP,
                           method=opt.integration_method,
                           pred_method=DynamicIntegrationMethod.OdeEuler,
                           dense_threshold=0, verbose=False)
t, y, dy, _, _ = solver.simulate(boundary_updater=cast(Any, prob))


def _find_any(name: str) -> Any:
    """Find a var anywhere in the GFM block, including in_vars."""
    v = _find_name_in_block(name, vsc.emt_model)
    if v is not None:
        return v
    for cand in getattr(vsc.emt_model, "in_vars", []):
        if cand.name == name:
            return cand
    return None


def col(name: str) -> np.ndarray:
    v = _find_any(name)
    assert v is not None, name
    return y[:, prob.get_var_idx(v)]


def col_opt(name: str):
    """Return a column if the var exists and indexes into y, else None."""
    v = _find_any(name)
    if v is None:
        return None
    try:
        return y[:, prob.get_var_idx(v)]
    except Exception:
        return None


Pe = col("Pe_GFM_VSC")
Qe = col("Qe_GFM_VSC")
iA, iB, iC = col("i_A_GFM_VSC"), col("i_B_GFM_VSC"), col("i_C_GFM_VSC")
vA, vB, vC = col_opt("v_A_GFM_VSC"), col_opt("v_B_GFM_VSC"), col_opt("v_C_GFM_VSC")
have_v = vA is not None and vB is not None and vC is not None

# Post-event steady window.
m = t > (EVENT_TIME + 0.06)
ts = t[m]
dt = float(np.mean(np.diff(ts)))

# FFT of the Qe ripple (remove mean).
q = Qe[m] - np.mean(Qe[m])
f = np.fft.rfftfreq(len(q), d=dt)
amp = np.abs(np.fft.rfft(q)) / len(q)
order = np.argsort(amp)[::-1][:5]
print("Qe ripple spectrum (top peaks):")
for k in order:
    print(f"  f = {f[k]:7.1f} Hz   amp = {amp[k]:.5e}")
print(f"Qe mean={np.mean(Qe[m]):.4f}  pk-pk={np.ptp(Qe[m]):.4f}")
print(f"Pe mean={np.mean(Pe[m]):.4f}  pk-pk={np.ptp(Pe[m]):.4f}")

# Symmetrical components of the converter current at the last sample.
a = np.exp(1j * 2 * np.pi / 3.0)


def seq(xa, xb, xc):
    pos = (xa + a * xb + a * a * xc) / 3.0
    neg = (xa + a * a * xb + a * xc) / 3.0
    zero = (xa + xb + xc) / 3.0
    return pos, neg, zero


# Build phasors over one post-event cycle via single-bin DFT at 50 Hz.
def phasor(sig):
    s = sig[m]
    n = len(s)
    tt = ts - ts[0]
    return (2.0 / n) * np.sum(s * np.exp(-1j * 2 * np.pi * 50.0 * tt))


IA, IB, IC = phasor(iA), phasor(iB), phasor(iC)
Ip, In, I0 = seq(IA, IB, IC)
print(f"\nCurrent  |I+|={abs(Ip):.4f}  |I-|={abs(In):.4f}  |I0|={abs(I0):.4f}"
      f"   neg/pos={abs(In)/abs(Ip):.3%}")
if have_v:
    VA, VB, VC = phasor(vA), phasor(vB), phasor(vC)
    Vp, Vn, V0 = seq(VA, VB, VC)
    print(f"Voltage  |V+|={abs(Vp):.4f}  |V-|={abs(Vn):.4f}  |V0|={abs(V0):.4f}"
          f"   neg/pos={abs(Vn)/abs(Vp):.3%}")
else:
    print("Voltage  (converter terminal v vars not indexable in y; skipped)")
print(f"\ndt={dt*1e6:.1f} us  -> Nyquist={0.5/dt:.0f} Hz  (2f0=100, 3f0=150)")
