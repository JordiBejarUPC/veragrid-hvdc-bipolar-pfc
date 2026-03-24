import unittest
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

# Assuming these modules are in the correct fully qualified path as per eRoots rules
from PolynomialMatrixBuilder import PolynomialMatrixBuilder
from MTI_problem import MTI_Problem


class StabilityResult(object):
    """
    Lightweight class to store stability results.
    Replaces the use of generic tuples or dictionaries for data passing.
    """
    __slots__: List[str] = ["eigenvalues", "is_stable", "margin"]

    def __init__(self, evals: np.ndarray, stable: bool, margin: float) -> None:
        """
        Initializes the result container.

        :param evals: Numpy array with calculated eigenvalues.
        :type evals: np.ndarray
        :param stable: Boolean indicating if the system is stable.
        :type stable: bool
        :param margin: Real value of the stability margin.
        :type margin: float
        """
        self.eigenvalues: np.ndarray = evals
        self.is_stable: bool = stable
        self.margin: float = margin


class TestPolynomialStability(unittest.TestCase):
    """
    Test suite to validate the stability of polynomial systems using
    the iMTI / CPN representation builder.
    """
    # Final class with no persistent internal state between tests
    __slots__: List[str] = list()

    def test_unstable_20x20_system(self) -> None:
        """
        Test 1: Large-Scale Linear State-Space System.
        Validates the parsing, matrix allocation, and eigenvalue computation for a
        20-dimensional linear system. Ensures that the underlying sparse matrix builders
        correctly identify a naturally unstable system with a margin of 0.489.

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            '-xp1 + 0.3440*x10 + 0.4474',
            '-xp2 + 0.0038*x2 + 0.6549*x10 + 0.7845*x13 + 0.0040*x14 + 0.2282*x19 + 0.9734',
            '-xp3 + 0.6267*u5 + 0.0651*x12 + 0.3473*x16 + 0.8588',
            '-xp4 + 0.0598*u5 + 0.2887*x17 + 0.0327*x18 + 0.8685',
            '-xp5 + 0.0831*u4 + 0.38984*x15 + 0.1381*x18 + 0.2472',
            '-xp6 + 0.4737*x8 + 0.0856*x16 + 0.2286*x18 + 1.6085',
            '-xp7 + 0.0838*u5 + 0.2301*x11 + 0.2002*x12 + 0.8884',
            '-xp8 + 0.0998*u5 + 0.66*x9 + 0.0515*x10 + 0.5883',
            '-xp9 + 0.6785*u2 + 0.0110*x7 + 0.4883*x9 + 0.2754*x12 + 0.6573',
            '-xp10 + 0.0276*x1 + 0.2263*x19 + 0.3483',
            '-xp11 + 0.0549*u2 + 0.2598*x3 + 0.2733*x12 + 0.0994*x16 + 0.1905*x20 + 1.9020',
            '-xp12 + 0.0732*u5 + 0.0466*u6 + 0.8391',
            '-xp13 + 0.1264*u1 + 0.5706*x5 + 0.0839*x13 + 0.2854*x20 + 1.4471',
            '-xp14 + 0.4188*x8 + 0.4638',
            '-xp15 + 0.7539*u1 + 0.4065*x15 + 0.5479',
            '-xp16 + 0.0105*u2 + 0.1236*x1 + 0.1916*x4 + 0.0859*x6 + 0.1613*x18 + 1.0436',
            '-xp17 + 0.2431*u3 + 0.0820',
            '-xp18 + 0.0578*x2 + 0.0867*x4 + 0.0267*x5 + 0.0526*x8 + 2.5279',
            '-xp19 + 0.2644*u5 + 0.4517*x12 + 1.1073',
            '-xp20 + 0.5101*u4 + 0.3917'
        ])

        xOP: np.ndarray = np.array([-0.1668, -0.459, 0.5462, -1.3023, -0.4115, -0.5401, 1.3665, 0.7068, 0.6076, 0.9198,
                                    0.8994, 0.0327, -1.4159, -1.6809, 0.0378, 1.6635, 0.831, 1.0477, 1.7938, -0.4851])
        uOP: np.ndarray = np.array([-0.6336, 1.1019, -0.7170, 2.2000, 0.8906, -0.6354])

        # Initialize dictionary properly
        v_dict: Dict[str, float] = dict()

        # Populate operational point variables
        i: int
        for i in range(20):
            v_dict[f'x{i + 1}'] = float(xOP[i])
            v_dict[f'xp{i + 1}'] = 0.0
            v_dict[f'dx{i + 1}'] = 0.0

        j: int
        for j in range(len(uOP)):
            v_dict[f'u{j + 1}'] = float(uOP[j])

        # Instantiate compiler and builder
        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(
            problem=math_problem,
            verbose=False
        )

        builder.linearize(v_dict)
        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()

        stable: bool = res[4]
        margin: float = res[5]

        # Explicit evaluation of states
        if stable:
            self.fail("The system should be evaluated as unstable.")
        else:
            self.assertAlmostEqual(margin, 0.489, places=3, msg="Mismatch in stability margin.")

    def test_stable_nonlinear_5x5_system(self) -> None:
        """
        Test 2: Nonlinear Differential-Algebraic System (3 DAEs + 2 Algebraic).
        Validates the handling of mixed state and algebraic equations with complex
        float coefficients. Ensures the generalized eigenvalue solver correctly
        processes algebraic constraints to find a stable margin of -0.00584.

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            '-xp1 + (x3 + 0.2732*1/3*((-2*u1+u2+u3)*x2 + 1.73205081*(u2-u3)*x1) + 314.159265)*(-y2)',
            '-xp2 + (x3 + 0.2732*1/3*((-2*u1+u2+u3)*x2 + 1.73205081*(u2-u3)*x1) + 314.159265)*y1',
            '-xp3 + (0.022508948*1/3*((-2*u1+u2+u3)*x2 + 1.73205081*(u2-u3)*x1))',
            'y1 - x1',
            'y2 - x2'
        ])

        xOP: np.ndarray = np.array([-0.5737, -0.8193, -0.1597])
        uOP: np.ndarray = np.array([-100.6109, -217.5716, 318.1824])
        yOP: np.ndarray = np.array([-0.5737, -0.8193])

        v_dict: Dict[str, float] = dict()

        i: int
        for i in range(len(xOP)):
            v_dict[f'x{i + 1}'] = float(xOP[i])
            v_dict[f'xp{i + 1}'] = 0.0
            v_dict[f'dx{i + 1}'] = 0.0

        j: int
        for j in range(len(uOP)):
            v_dict[f'u{j + 1}'] = float(uOP[j])

        k: int
        for k in range(len(yOP)):
            v_dict[f'y{k + 1}'] = float(yOP[k])

        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)
        builder.linearize(v_dict)

        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
        stable: bool = res[4]
        margin: float = res[5]

        if not stable:
            self.fail("The system should be evaluated as stable.")
        else:
            self.assertLess(margin, 0, msg="Stable system must have a negative margin.")
            self.assertAlmostEqual(margin, -0.00584, places=4, msg="Mismatch in stability margin.")

    def test_nonlinear_unstable_manual_system(self) -> None:
        """
        Test 3: Implicit Descriptor System (State-Dependent E-Matrix).
        Verifies the builder's capability to handle implicit formulations where the
        state derivative is multiplied by an algebraic variable (e.g., dx1*y1).
        This tests the proper assembly of a non-identity E matrix.
        Expects an unstable margin of 0.400.

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            "3*dx1*y1 + 6*(1/2+1/2*z1)*(2/3-1/3*u1)*x1",
            "y1 - dx1"
        ])
        v_dict: Dict[str, float] = dict({
            'xp1': 1.0,
            'x1': 2.0,
            'u1': 3.0,
            'y1': 4.0,
            'z1': 5.0
        })

        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)

        builder.linearize(v_dict)
        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
        stable: bool = res[4]
        margin: float = res[5]

        if stable:
            self.fail("Expected the implicit system to be unstable based on the eigenvalues.")
        else:
            self.assertAlmostEqual(margin, 0.400, places=3, msg=f"Expected stability margin 0.4, got {margin:.3f}")

    def test_quadratic_system(self) -> None:
        """
        Test 4: Quadratic System (Multilinear Lifting of Powers).
        Validates that the algorithm correctly parses the Python power operator (**2),
        triggers the automatic multilinear lifting process, and successfully
        augments the matrices without truncating equations.
        Expects an unstable margin of 3.436.

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            "xp1 - x1**2 - x2",
            "xp2 - x1*x2 - 1"
        ])
        v_dict: Dict[str, float] = dict({
            'xp1': 0.0,
            'xp2': 0.0,
            'x1': 1.0,
            'x2': 3.5
        })

        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)

        builder.linearize(v_dict)
        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
        stable: bool = res[4]
        margin: float = res[5]

        if stable:
            self.fail("Expected the quadratic system to be unstable based on the eigenvalues.")
        else:
            self.assertAlmostEqual(margin, 3.436, places=3, msg=f"Expected stability margin 3.436, got {margin:.3f}")

    def test_inverse_system(self) -> None:
        """
        Test 5: Inverse Nonlinear System (Fractional Lifting).
        Verifies the automatic handling of inverse states (e.g., 1/x2). Tests if the
        builder correctly generates the internal multiplier auxiliary variables and
        their algebraic coupling constraints (x2 * y1 - 1 = 0) to yield a stable
        margin of -1.000.

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            "xp1 + x1 - y1",
            "xp2 + x2 - 2",
            "y1 - 1/x2"
        ])
        v_dict: Dict[str, float] = dict({
            'xp1': -1.0,
            'xp2': 1.0,
            'x1': 2.0,
            'x2': 1.0
        })

        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)

        builder.linearize(v_dict)
        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
        stable: bool = res[4]
        margin: float = res[5]

        if not stable:
            self.fail("Expected the fractional system to be stable based on the eigenvalues.")
        else:
            self.assertAlmostEqual(margin, -1.000, places=3, msg=f"Expected stability margin -1.0, got {margin:.3f}")


    def test_sqrt(self) -> None:
        """
        Test 6:

        :return: None
        :rtype: None
        """
        eqs: List[str] = list([
            "sqrt(x1) + x1*y1+1",
            "2*xp1+x1",
            "y1-x1**2-1"
        ])
        v_dict: Dict[str, float] = dict({
            'xp1': 0.5,
            'x1': 1.0
        })

        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)

        builder.linearize(v_dict)
        res: Tuple[Any, Any, Any, Any, bool, float] = builder.compute_stability()
        stable: bool = res[4]
        margin: float = res[5]

        if not stable:
            self.fail("Expected the fractional system to be stable based on the eigenvalues.")
        else:
            self.assertAlmostEqual(margin, -0.500, places=3, msg=f"Expected stability margin -0.5, got {margin:.3f}")

    def test_imti_paper_nonlinear_rl_circuit(self) -> None:
        """
        Test 7: Non-linear RL Circuit with Magnitude Feedback (iMTI Paper inspired).

        This test implements a physical use-case modeled after the iMTI CPN
        methodology described in the Small-Signal Stability paper.
        It evaluates a 2-state system where the algebraic magnitude of the
        states feeds back into the derivatives, requiring exact analytic
        linearization of the non-polynomial 'sqrt' function to find the
        true system eigenvalues.

        :return: None
        :rtype: None
        """
        # 1. ALGORITHM: Define the system equations
        # Eq 1 & 2: Differential equations (dx/dt) with cross-coupled non-linear feedback
        # Eq 3: The algebraic constraint for the magnitude (Euclidean norm)
        eqs: List[str] = list([
            "xp1 + x1 + 0.1*y1 - 3.5",
            "xp2 + x2 - 0.2*y1 - 3.0",
            "y1 - sqrt(x1**2 + x2**2)"
        ])

        # 2. ALGORITHM: Define the exact steady-state operating point
        # We use a 3-4-5 Pythagorean triple to ensure clean, rational analytics.
        # sqrt(3^2 + 4^2) = 5.0
        v_dict: Dict[str, float] = dict({
            'x1': 3.0,
            'x2': 4.0,
            'y1': 5.0,
            'xp1': 0.0,
            'xp2': 0.0
        })

        # 3. Build the mathematical problem mapping
        math_problem: MTI_Problem = MTI_Problem(eqs_str=eqs, v_dict=v_dict)

        # 4. Instantiate the builder enforcing the eRoots multilinear lifting rules
        builder: PolynomialMatrixBuilder = PolynomialMatrixBuilder(problem=math_problem, verbose=False)

        # 5. Execute the analytic iMTI linearization
        builder.linearize(v_dict)

        # Retrieve stability results: (evals, evecs_left, evecs_right, participation, is_stable, max_real)
        res: Tuple[Optional[Any], Optional[Any], Optional[Any], Optional[Any], bool, Optional[
            float]] = builder.compute_stability()

        stable: bool = res[4]
        margin: Optional[float] = res[5]
        print(res[0])
        # 6. ALGORITHM: Assertions based on the analytic Jacobian
        # The theoretical characteristic equation for this point is L^2 + 1.9L + 0.9 = 0
        # The true eigenvalues are exactly -0.9 and -1.0.
        # The maximum real part (stability margin) is therefore -0.9.
        if not stable:
            self.fail("Expected the non-linear magnitude-feedback system to be stable.")
        else:
            pass

        if margin is not None:
            self.assertAlmostEqual(
                margin,
                -0.900,
                places=3,
                msg=str(f"Expected stability margin -0.9, got {margin:.3f}")
            )
        else:
            self.fail("Margin was None, eigenvalue computation failed.")


if __name__ == "__main__":
    # Standard unittest execution
    unittest.main()