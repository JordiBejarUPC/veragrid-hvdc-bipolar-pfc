import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
from VeraGridEngine.Simulations.PowerFlow.Formulations.pf_full_acdc_with_negative_poles import PfAcDcWithNegativePoles
from VeraGridEngine.Simulations.PowerFlow.NumericalMethods.newton_raphson_fx import newton_raphson_fx
import numpy as np


def solve_with_autodiff(grid, pf_options):
    """
    Solve the AC/DC power flow forcing the finite-difference Jacobian.
    """
    logger = vge.Logger()
    nc = vge.compile_numerical_circuit_at(grid, t_idx=None,
                                          use_stored_guess=pf_options.use_stored_guess,
                                          control_taps_modules=pf_options.control_taps_modules,
                                          control_taps_phase=pf_options.control_taps_phase,
                                          control_remote_voltage=pf_options.control_remote_voltage,
                                          consider_grounded_buses=len(grid.vsc_devices) > 0)
    Qmax, Qmin = nc.get_reactive_power_limits()
    problem = PfAcDcWithNegativePoles(V0=nc.bus_data.Vbus.copy(),
                                      S0=nc.get_power_injections_pu(),
                                      I0=nc.get_current_injections_pu(),
                                      Y0=-nc.get_admittance_injections_pu(),
                                      Qmin=Qmin, Qmax=Qmax,
                                      nc=nc, options=pf_options, logger=logger)
    problem.use_autodiff_jacobian = True

    return newton_raphson_fx(problem=problem,
                             tol=pf_options.tolerance,
                             max_iter=pf_options.max_iter,
                             trust=pf_options.trust_radius,
                             verbose=pf_options.verbose,
                             logger=logger)


def test_spen_west():

    grid = vge.open_file('data/grids/DGS/test_reduced_spen_v10.dgs',
                         options=vge.FileOpenOptions(
                             dgs_use_vsc_for_injections=True
                         ))

    pf_options = PowerFlowOptions(control_taps_modules=False)
    res_pf = solve_with_autodiff(grid, pf_options)
    assert res_pf.converged

    DUNH0G = 1.0177
    WHLL0G = 1.0174
    TWEN0G = 1.0182
    SNQR0G = 1.0108
    SAKN0G = 1.0013
    AFTO0G = 1.0159
    WNDR0G = 1.0024
    NOKY0B = 1.0087
    NOKY0A = 1.0087
    SOKY0G = 1.0091
    ENHI0G = 1.0086
    DESA0G = 1.0089
    BLKS0G = 1.0189

    assert np.allclose(np.abs(res_pf.V[11]), DUNH0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[47]), WHLL0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[45]), TWEN0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[40]), SNQR0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[37]), SAKN0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[0]), AFTO0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[49]), WNDR0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[33]), NOKY0B, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[32]), NOKY0A, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[42]), SOKY0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[17]), ENHI0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[8]), DESA0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.V[6]), BLKS0G, atol=1e-4)