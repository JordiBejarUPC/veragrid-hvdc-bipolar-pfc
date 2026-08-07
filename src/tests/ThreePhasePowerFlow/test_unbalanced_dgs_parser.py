import VeraGridEngine.api as vge
from VeraGridEngine import SolverType
import numpy as np

def test_three_phase_power_delta():

    grid = vge.open_file('data/grids/DGS/ThreePhasePowerDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9961])
    Ub_reference = np.array([0.9955])
    Uc_reference = np.array([0.9958])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_three_phase_power_groundedstar():

    grid = vge.open_file('data/grids/DGS/ThreePhasePowerGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9872])
    Ub_reference = np.array([1.0023])
    Uc_reference = np.array([0.9984])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_three_phase_power_neutralstar():

    grid = vge.open_file('data/grids/DGS/ThreePhasePowerNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9930])
    Ub_reference = np.array([0.9976])
    Uc_reference = np.array([0.9973])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_two_phase_power_groundedstar():

    grid = vge.open_file('data/grids/DGS/TwoPhasePowerGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9818])
    Ub_reference = np.array([1.0055])
    Uc_reference = np.array([1.0025])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_two_phase_power_neutralstar():

    grid = vge.open_file('data/grids/DGS/TwoPhasePowerNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9931])
    Ub_reference = np.array([0.9975])
    Uc_reference = np.array([0.9995])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_two_phase_power_delta():

    grid = vge.open_file('data/grids/DGS/TwoPhasePowerDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9981])
    Ub_reference = np.array([0.9901])
    Uc_reference = np.array([0.9991])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_single_phase_power_neutralstar():

    grid = vge.open_file('data/grids/DGS/SinglePhasePowerNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9867])
    Ub_reference = np.array([1.0033])
    Uc_reference = np.array([0.9998])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_single_phase_power_groundedstar():

    grid = vge.open_file('data/grids/DGS/SinglePhasePowerGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9744])
    Ub_reference = np.array([1.0280])
    Uc_reference = np.array([0.9876])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_three_phase_current_delta():

    grid = vge.open_file('data/grids/DGS/ThreePhaseCurrentDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9788])
    Ub_reference = np.array([0.9769])
    Uc_reference = np.array([0.9783])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_three_phase_current_groundedstar():

    grid = vge.open_file('data/grids/DGS/ThreePhaseCurrentGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9402])
    Ub_reference = np.array([0.9987])
    Uc_reference = np.array([0.9969])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_three_phase_current_neutralstar():

    grid = vge.open_file('data/grids/DGS/ThreePhaseCurrentNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9657])
    Ub_reference = np.array([0.9846])
    Uc_reference = np.array([0.9860])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_two_phase_current_groundedstar():

    grid = vge.open_file('data/grids/DGS/TwoPhaseCurrentGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9100])
    Ub_reference = np.array([1.0187])
    Uc_reference = np.array([1.0188])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_two_phase_current_neutralstar():

    grid = vge.open_file('data/grids/DGS/TwoPhaseCurrentNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9664])
    Ub_reference = np.array([0.9828])
    Uc_reference = np.array([0.9973])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_two_phase_current_delta():

    grid = vge.open_file('data/grids/DGS/TwoPhaseCurrentDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9896])
    Ub_reference = np.array([0.9476])
    Uc_reference = np.array([0.9954])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_single_phase_current_neutralstar():

    grid = vge.open_file('data/grids/DGS/SinglePhaseCurrentNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9252])
    Ub_reference = np.array([1.0169])
    Uc_reference = np.array([0.9991])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-3)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=3e-4)

def test_single_phase_current_groundedstar():

    grid = vge.open_file('data/grids/DGS/SinglePhaseCurrentGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.8536])
    Ub_reference = np.array([1.1432])
    Uc_reference = np.array([0.9605])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-3)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=2e-4)

def test_three_phase_impedance_delta():

    grid = vge.open_file('data/grids/DGS/ThreePhaseImpedanceDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9792])
    Ub_reference = np.array([0.9774])
    Uc_reference = np.array([0.9788])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=1e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=1e-4)

def test_three_phase_impedance_groundedstar():

    grid = vge.open_file('data/grids/DGS/ThreePhaseImpedanceGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9442])
    Ub_reference = np.array([0.9956])
    Uc_reference = np.array([0.9977])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=3e-4)

def test_three_phase_impedance_neutralstar():

    grid = vge.open_file('data/grids/DGS/ThreePhaseImpedanceNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9676])
    Ub_reference = np.array([0.9846])
    Uc_reference = np.array([0.9858])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=3e-4)

def test_two_phase_impedance_groundedstar():

    grid = vge.open_file('data/grids/DGS/TwoPhaseImpedanceGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9158])
    Ub_reference = np.array([1.0129])
    Uc_reference = np.array([1.0206])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=3e-4)

def test_two_phase_impedance_neutralstar():

    grid = vge.open_file('data/grids/DGS/TwoPhaseImpedanceNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9693])
    Ub_reference = np.array([0.9825])
    Uc_reference = np.array([0.9973])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=3e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=3e-4)

def test_two_phase_impedance_delta():

    grid = vge.open_file('data/grids/DGS/TwoPhaseImpedanceDelta.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9900])
    Ub_reference = np.array([0.9500])
    Uc_reference = np.array([0.9954])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=4e-4)

def test_single_phase_impedance_neutralstar():

    grid = vge.open_file('data/grids/DGS/SinglePhaseImpedanceNeutralStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9399])
    Ub_reference = np.array([1.0137])
    Uc_reference = np.array([0.9990])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=4e-4)

def test_single_phase_impedance_groundedstar():

    grid = vge.open_file('data/grids/DGS/SinglePhaseImpedanceGroundedStar.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.8743])
    Ub_reference = np.array([1.1255])
    Uc_reference = np.array([0.9617])

    assert np.allclose(np.abs(res.voltage_A[0]), Ua_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_B[0]), Ub_reference, atol=4e-4)
    assert np.allclose(np.abs(res.voltage_C[0]), Uc_reference, atol=4e-4)

def test_single_phase_transformer_dd_non_auto_phase_a():

    grid = vge.open_file('data/grids/DGS/DDconnection_non_auto_phaseA.dgs')

    res = vge.power_flow3ph(grid=grid, options=vge.PowerFlowOptions(solver_type=SolverType.NR,
                                                                    retry_with_other_methods=False))

    Ua_reference = np.array([0.9911, 0.9790])
    Ub_reference = np.array([1.0032, 0.0])
    Uc_reference = np.array([0.9990, 0.0])

    assert np.allclose(np.abs(res.voltage_A[1:]), Ua_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_B[1:]), Ub_reference, atol=2e-4)
    assert np.allclose(np.abs(res.voltage_C[1:]), Uc_reference, atol=2e-4)