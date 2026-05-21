import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np


def test_spen_west():

    grid = vge.open_file('data/grids/test_reduced_spen_v10.dgs')

    pf_options = PowerFlowOptions(control_taps_modules=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options)

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

    assert np.allclose(np.abs(res_pf.voltage[11]), DUNH0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[47]), WHLL0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[45]), TWEN0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[40]), SNQR0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[37]), SAKN0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[0]), AFTO0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[49]), WNDR0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[33]), NOKY0B, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[32]), NOKY0A, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[42]), SOKY0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[17]), ENHI0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[8]), DESA0G, atol=1e-4)
    assert np.allclose(np.abs(res_pf.voltage[6]), BLKS0G, atol=1e-4)


def test_spen_north():

    v_powerfactory = np.array([
        1.024555, 1.015524, 1.015895, 1.034784, 1.031238, 1.024810, 1.074590, 1.074605,
        1.081009, 1.000000, 1.000000, 1.016668, 1.016677, 1.075665, 1.072288, 1.076095,
        1.076068, 1.073081, 1.073386, 1.013502, 1.013502, 1.019082, 1.035745, 1.045892,
        1.037262, 1.011622, 1.011622, 1.027771, 1.039984, 1.066080, 1.076443, 1.076417,
        1.069907, 1.062895, 1.062901, 1.062887, 1.062893, 1.039789, 1.035278, 1.026786,
        1.063884, 1.041257, 1.072647, 1.071983, 1.064949, 1.064959, 1.068474, 1.068977,
        1.067204, 1.067174, 1.017362, 1.017362, 1.034540, 1.034540, 1.066432, 1.068037,
        1.048957, 1.069123, 1.058824, 1.058825, 1.064842, 1.064842, 1.076505, 1.042604,
        1.055452, 1.055880, 1.027097, 1.041610, 1.031120, 1.039729, 1.069974, 1.069989,
        1.056466, 1.072150, 1.024699, 1.066100, 1.071983, 1.056445, 1.072119, 1.024692,
        1.066099, 1.071952, 1.014495, 1.041119, 1.073394, 1.073351, 1.077001, 1.076958,
        1.072863, 1.077061, 1.076995, 1.069653, 1.069653, 1.066460, 1.076297, 1.065425,
        1.078088, 1.068658, 1.066911, 1.067005, 1.031147, 1.037378, 1.000000, 1.000000,
        1.064828, 1.057504, 1.057500, 1.066129, 1.000000, 1.025350, 1.045269, 1.076485,
        1.076460, 1.071684, 1.072658, 1.072657, 1.029825, 1.023753, 1.029852, 1.023776,
        1.076153, 1.066183, 1.064769, 1.064770, 1.066460, 1.066421, 1.072099, 1.068079,
        1.072089, 1.068081, 1.066239, 1.066249, 1.072030, 1.061188, 1.071999, 1.061157,
        1.076307, 1.076306
    ], dtype=float)

    assert v_powerfactory.size == 138

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    grid = vge.open_file('data/grids/SPTL_11_05.dgs')

    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=False,
                                  limit_i_vsc=False,
                                  control_taps_modules=False,  # keeps taps fixed → limited support behaves like basic
                                  control_taps_phase=False,
                                  use_stored_guess=True,
                                  verbose=0)
    res_pf = vge.power_flow(grid=grid, options=pf_options)

    v_veragrid = np.abs(res_pf.voltage[0:138])

    assert v_veragrid.size == 138

    assert np.allclose(v_veragrid, v_powerfactory, atol=1e-3)