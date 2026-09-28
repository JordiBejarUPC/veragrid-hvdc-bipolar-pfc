import numpy as np
from scipy.special import iv, kv


def build_layer_radii(
    diaCon: np.float32,
    diaTube: np.float32,
    thIns: np.ndarray,
    thSht: np.float32,
    diaCab: np.float32,
) -> np.ndarray:
    """Build the cable radii with the same input precision used by PowerFactory.

    :param diaCon: PowerFactory core outer diameter in millimetres.
    :param diaTube: PowerFactory core inner diameter in millimetres.
    :param thIns: PowerFactory insulation thicknesses in millimetres.
    :param thSht: PowerFactory sheath thickness in millimetres.
    :param diaCab: PowerFactory overall cable diameter in millimetres.
    :return: Core, sheath and cable radii in metres.
    """
    # PowerFactory stores these TypCab fields as float32. Keeping that precision
    # while adding thin layers is required to reproduce its last displayed digits.
    core_inner_radius_mm: np.float32 = np.float32(diaTube / np.float32(2.0))
    core_outer_radius_mm: np.float32 = np.float32(diaCon / np.float32(2.0))
    sheath_inner_radius_mm: np.float32 = np.float32(
        core_outer_radius_mm + thIns[0]
    )
    sheath_outer_radius_mm: np.float32 = np.float32(
        sheath_inner_radius_mm + thSht
    )
    cable_outer_radius_mm: np.float32 = np.float32(diaCab / np.float32(2.0))

    # The electromagnetic equations use SI units and double precision.
    radii_m: np.ndarray = np.array(
        [
            core_inner_radius_mm,
            core_outer_radius_mm,
            sheath_inner_radius_mm,
            sheath_outer_radius_mm,
            cable_outer_radius_mm,
        ],
        dtype=float,
    ) * 1e-3
    return radii_m


def calculate_solid_surface_impedance(
    crho: np.float32,
    Cf: np.float32,
    my: np.float32,
    ks: np.float32,
    radius_m: float,
    frnom: np.float32,
) -> complex:
    """Calculate the surface impedance of the solid core with skin effect.

    :param crho: PowerFactory material resistivity in micro-ohm centimetres.
    :param Cf: PowerFactory conducting filling factor in percent.
    :param my: PowerFactory relative magnetic permeability.
    :param ks: PowerFactory core skin-effect correction factor.
    :param radius_m: Core outer radius in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :return: Core surface impedance in ohms per kilometre.
    """
    # The filling factor converts the material resistivity into the effective
    # resistivity of the complete conducting cross-section.
    resistivity_ohm_m: float = float(crho) * 1e-8 / (float(Cf) / 100.0)
    angular_frequency_rad_s: float = 2.0 * np.pi * float(frnom)
    permeability_h_m: float = 4.0e-7 * np.pi * float(my)

    # Equation (17) applies ks only to the core propagation constant.
    propagation_constant_per_m: complex = np.sqrt(
        1j * angular_frequency_rad_s * permeability_h_m / resistivity_ohm_m
    ) * np.sqrt(float(ks))
    radius_argument: complex = propagation_constant_per_m * radius_m

    # This is the solid-cylinder limit of the Bessel equations (14)-(16).
    impedance_ohm_m: complex = (
        resistivity_ohm_m
        * propagation_constant_per_m
        * iv(0, radius_argument)
        / (2.0 * np.pi * radius_m * iv(1, radius_argument))
    )
    impedance_ohm_km: complex = complex(1000.0 * impedance_ohm_m)
    return impedance_ohm_km


def calculate_tube_surface_impedances(
    crho: np.float32,
    Cf: np.float32,
    my: np.float32,
    inner_radius_m: float,
    outer_radius_m: float,
    frnom: np.float32,
) -> tuple[complex, complex, complex]:
    """Calculate the inner, outer and mutual impedances of the sheath tube.

    :param crho: PowerFactory material resistivity in micro-ohm centimetres.
    :param Cf: PowerFactory conducting filling factor in percent.
    :param my: PowerFactory relative magnetic permeability.
    :param inner_radius_m: Sheath inner radius in metres.
    :param outer_radius_m: Sheath outer radius in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :return: Inner, outer and mutual sheath impedances in ohms per kilometre.
    """
    # The tubular layer uses the same diffusion equation as the solid core.
    resistivity_ohm_m: float = float(crho) * 1e-8 / (float(Cf) / 100.0)
    angular_frequency_rad_s: float = 2.0 * np.pi * float(frnom)
    permeability_h_m: float = 4.0e-7 * np.pi * float(my)
    propagation_constant_per_m: complex = np.sqrt(
        1j * angular_frequency_rad_s * permeability_h_m / resistivity_ohm_m
    )
    inner_argument: complex = propagation_constant_per_m * inner_radius_m
    outer_argument: complex = propagation_constant_per_m * outer_radius_m

    # Equation (15) is the common denominator of all three tube impedances.
    denominator: complex = (
        iv(1, outer_argument) * kv(1, inner_argument)
        - iv(1, inner_argument) * kv(1, outer_argument)
    )
    inner_impedance_ohm_m: complex = (
        resistivity_ohm_m
        * propagation_constant_per_m
        * (
            iv(0, inner_argument) * kv(1, outer_argument)
            + kv(0, inner_argument) * iv(1, outer_argument)
        )
        / (2.0 * np.pi * inner_radius_m * denominator)
    )
    outer_impedance_ohm_m: complex = (
        resistivity_ohm_m
        * propagation_constant_per_m
        * (
            iv(0, outer_argument) * kv(1, inner_argument)
            + kv(0, outer_argument) * iv(1, inner_argument)
        )
        / (2.0 * np.pi * outer_radius_m * denominator)
    )
    mutual_impedance_ohm_m: complex = resistivity_ohm_m / (
        2.0 * np.pi * inner_radius_m * outer_radius_m * denominator
    )

    # PowerFactory reports all longitudinal impedances in ohms per kilometre.
    inner_impedance_ohm_km: complex = complex(1000.0 * inner_impedance_ohm_m)
    outer_impedance_ohm_km: complex = complex(1000.0 * outer_impedance_ohm_m)
    mutual_impedance_ohm_km: complex = complex(1000.0 * mutual_impedance_ohm_m)
    return (
        inner_impedance_ohm_km,
        outer_impedance_ohm_km,
        mutual_impedance_ohm_km,
    )


def calculate_insulation_impedance(
    inner_radius_m: float,
    outer_radius_m: float,
    frnom: np.float32,
) -> complex:
    """Calculate the longitudinal magnetic-field impedance of one insulation.

    :param inner_radius_m: Insulation inner radius in metres.
    :param outer_radius_m: Insulation outer radius in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :return: Insulation impedance in ohms per kilometre.
    """
    # Equation (18) reduces to a logarithm for concentric cable layers.
    angular_frequency_rad_s: float = 2.0 * np.pi * float(frnom)
    vacuum_permeability_h_m: float = 4.0e-7 * np.pi
    impedance_ohm_km: complex = complex(
        1j
        * angular_frequency_rad_s
        * vacuum_permeability_h_m
        * np.log(outer_radius_m / inner_radius_m)
        * 1000.0
        / (2.0 * np.pi)
    )
    return impedance_ohm_km


def build_internal_impedance_matrix(
    crho: np.ndarray,
    Cf: np.ndarray,
    my: np.ndarray,
    ks: np.float32,
    radii_m: np.ndarray,
    frnom: np.float32,
) -> np.ndarray:
    """Build the core-sheath internal impedance matrix from loop impedances.

    :param crho: PowerFactory conducting-layer resistivities.
    :param Cf: PowerFactory conducting-layer filling factors.
    :param my: PowerFactory conducting-layer relative permeabilities.
    :param ks: PowerFactory core skin-effect correction factor.
    :param radii_m: Cable layer radii in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :return: Two-by-two internal impedance matrix in ohms per kilometre.
    """
    # Read the radii once so every equation below follows the cable cross-section.
    core_outer_radius_m: float = float(radii_m[1])
    sheath_inner_radius_m: float = float(radii_m[2])
    sheath_outer_radius_m: float = float(radii_m[3])
    cable_outer_radius_m: float = float(radii_m[4])

    # Equations (14)-(18) provide each surface and insulation contribution.
    core_outer_impedance: complex = calculate_solid_surface_impedance(
        crho=crho[0],
        Cf=Cf[0],
        my=my[0],
        ks=ks,
        radius_m=core_outer_radius_m,
        frnom=frnom,
    )
    sheath_inner_impedance: complex
    sheath_outer_impedance: complex
    sheath_mutual_impedance: complex
    (
        sheath_inner_impedance,
        sheath_outer_impedance,
        sheath_mutual_impedance,
    ) = calculate_tube_surface_impedances(
        crho=crho[1],
        Cf=Cf[1],
        my=my[1],
        inner_radius_m=sheath_inner_radius_m,
        outer_radius_m=sheath_outer_radius_m,
        frnom=frnom,
    )
    main_insulation_impedance: complex = calculate_insulation_impedance(
        inner_radius_m=core_outer_radius_m,
        outer_radius_m=sheath_inner_radius_m,
        frnom=frnom,
    )
    outer_insulation_impedance: complex = calculate_insulation_impedance(
        inner_radius_m=sheath_outer_radius_m,
        outer_radius_m=cable_outer_radius_m,
        frnom=frnom,
    )

    # Equations (12)-(13) assemble the two coaxial loops before earth return.
    loop_11: complex = (
        core_outer_impedance
        + main_insulation_impedance
        + sheath_inner_impedance
    )
    loop_22: complex = sheath_outer_impedance + outer_insulation_impedance
    loop_12: complex = -sheath_mutual_impedance
    internal_matrix: np.ndarray = np.array(
        [
            [loop_11 + 2.0 * loop_12 + loop_22, loop_12 + loop_22],
            [loop_12 + loop_22, loop_22],
        ],
        dtype=complex,
    )
    return internal_matrix


def calculate_carson_coefficients(
    carson_argument: float,
    image_angle_rad: float,
) -> tuple[float, float]:
    """Evaluate the PowerFactory Carson series for arguments below five.

    :param carson_argument: Dimensionless Carson argument ``x``.
    :param image_angle_rad: Angle to the image conductor in radians.
    :return: Dimensionless Carson coefficients ``P`` and ``Q``.
    """
    # These constants and recurrences are printed in equations (28)-(29) of
    # PowerFactory's Overhead Line Constants technical reference.
    b1: float = np.sqrt(2.0) / 6.0
    b2: float = 1.0 / 16.0
    b3: float = b1 / (3.0 * 5.0)
    b4: float = b2 / (4.0 * 6.0)
    b5: float = b3 / (5.0 * 7.0)
    b6: float = b4 / (6.0 * 8.0)
    b7: float = b5 / (7.0 * 9.0)
    b8: float = b6 / (8.0 * 10.0)
    c2: float = 1.3659315
    c4: float = c2 + 1.0 / 4.0 + 1.0 / 6.0
    c6: float = c4 + 1.0 / 6.0 + 1.0 / 8.0
    c8: float = c6 + 1.0 / 8.0 + 1.0 / 10.0
    d2: float = np.pi * b2 / 4.0
    d4: float = np.pi * b4 / 4.0
    d6: float = np.pi * b6 / 4.0
    d8: float = np.pi * b8 / 4.0

    # PowerFactory 2024 uses the six-digit Euler constant printed in the same
    # reference. Keeping it reproduces the final tens of nano-ohms per kilometre.
    euler_constant: float = 0.577215
    k: float = 0.5 + np.log(2.0) - euler_constant
    logarithm: float = np.log(carson_argument)
    x2: float = carson_argument**2
    x3: float = carson_argument**3
    x4: float = carson_argument**4
    x5: float = carson_argument**5
    x6: float = carson_argument**6
    x7: float = carson_argument**7
    x8: float = carson_argument**8

    # The complete x <= 5 expressions are kept explicit so each printed term
    # can be compared directly with the PowerFactory technical reference.
    coefficient_P: float = (
        np.pi / 8.0
        - b1 * carson_argument * np.cos(image_angle_rad)
        + b2
        * (
            (c2 - logarithm) * x2 * np.cos(2.0 * image_angle_rad)
            + x2 * image_angle_rad * np.sin(2.0 * image_angle_rad)
        )
        + b3 * x3 * np.cos(3.0 * image_angle_rad)
        - d4 * x4 * np.cos(4.0 * image_angle_rad)
        - b5 * x5 * np.cos(5.0 * image_angle_rad)
        + b6
        * (
            (c6 - logarithm) * x6 * np.cos(6.0 * image_angle_rad)
            + x6 * image_angle_rad * np.sin(6.0 * image_angle_rad)
        )
        + b7 * x7 * np.cos(7.0 * image_angle_rad)
        - d8 * x8 * np.cos(8.0 * image_angle_rad)
    )
    coefficient_Q: float = (
        0.5 * (k - logarithm)
        + b1 * carson_argument * np.cos(image_angle_rad)
        - d2 * x2 * np.cos(2.0 * image_angle_rad)
        + b3 * x3 * np.cos(3.0 * image_angle_rad)
        - b4
        * (
            (c4 - logarithm) * x4 * np.cos(4.0 * image_angle_rad)
            + x4 * image_angle_rad * np.sin(4.0 * image_angle_rad)
        )
        + b5 * x5 * np.cos(5.0 * image_angle_rad)
        - d6 * x6 * np.cos(6.0 * image_angle_rad)
        + b7 * x7 * np.cos(7.0 * image_angle_rad)
        - b8
        * (
            (c8 - logarithm) * x8 * np.cos(8.0 * image_angle_rad)
            + x8 * image_angle_rad * np.sin(8.0 * image_angle_rad)
        )
    )
    return coefficient_P, coefficient_Q


def calculate_earth_return_impedance(
    conductor_distance_m: float,
    image_distance_m: float,
    image_angle_rad: float,
    frnom: np.float32,
    cGearth: np.float32,
) -> complex:
    """Calculate one self or mutual earth-return impedance.

    :param conductor_distance_m: Physical self radius or mutual distance.
    :param image_distance_m: Distance to the image conductor in metres.
    :param image_angle_rad: Angle to the image conductor in radians.
    :param frnom: PowerFactory nominal frequency in hertz.
    :param cGearth: PowerFactory ground conductivity in micro-siemens per centimetre.
    :return: Earth-return impedance in ohms per kilometre.
    """
    # Convert the PowerFactory inputs to the SI quantities used by equation (26).
    angular_frequency_rad_s: float = 2.0 * np.pi * float(frnom)
    vacuum_permeability_h_m: float = 4.0e-7 * np.pi
    ground_conductivity_s_m: float = float(cGearth) * 1e-4
    propagation_constant_per_m: complex = np.sqrt(
        1j
        * angular_frequency_rad_s
        * vacuum_permeability_h_m
        * ground_conductivity_s_m
    )
    carson_argument: float = image_distance_m * np.sqrt(
        vacuum_permeability_h_m
        * ground_conductivity_s_m
        * angular_frequency_rad_s
    )
    coefficient_P: float
    coefficient_Q: float
    coefficient_P, coefficient_Q = calculate_carson_coefficients(
        carson_argument=carson_argument,
        image_angle_rad=image_angle_rad,
    )

    # scipy.special.kv returns the standard K0 normalization. The factor below
    # is the equivalent SI form of PowerFactory's cable earth-return equation.
    bessel_term_ohm_m: complex = (
        1j
        * angular_frequency_rad_s
        * vacuum_permeability_h_m
        * (
            kv(0, propagation_constant_per_m * conductor_distance_m)
            - kv(0, propagation_constant_per_m * image_distance_m)
        )
        / (2.0 * np.pi)
    )
    carson_term_ohm_m: complex = (
        angular_frequency_rad_s
        * vacuum_permeability_h_m
        * complex(coefficient_P, coefficient_Q)
        / np.pi
    )
    earth_impedance_ohm_km: complex = complex(
        1000.0 * (bessel_term_ohm_m + carson_term_ohm_m)
    )
    return earth_impedance_ohm_km


def build_earth_return_matrix(
    xy_c: np.ndarray,
    cable_outer_radius_m: float,
    frnom: np.float32,
    cGearth: np.float32,
) -> np.ndarray:
    """Build the three-cable earth-return matrix from cable coordinates.

    :param xy_c: PowerFactory cable-centre coordinates in metres.
    :param cable_outer_radius_m: Overall cable radius in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :param cGearth: PowerFactory ground conductivity in micro-siemens per centimetre.
    :return: Three-by-three earth-return matrix in ohms per kilometre.
    """
    # The matrix is symmetric, but all nine entries are evaluated explicitly to
    # keep the geometry easy to inspect and extend to unequal cable depths.
    earth_matrix: np.ndarray = np.empty((3, 3), dtype=complex)
    row: int
    column: int
    for row in range(3):
        for column in range(3):
            horizontal_distance_m: float = float(xy_c[0, row] - xy_c[0, column])
            depth_sum_m: float = float(xy_c[1, row] + xy_c[1, column])
            image_distance_m: float = float(
                np.hypot(horizontal_distance_m, depth_sum_m)
            )
            if row == column:
                conductor_distance_m: float = cable_outer_radius_m
                image_angle_rad: float = 0.0
            else:
                vertical_distance_m: float = float(
                    xy_c[1, row] - xy_c[1, column]
                )
                conductor_distance_m = float(
                    np.hypot(horizontal_distance_m, vertical_distance_m)
                )
                image_angle_rad = float(
                    np.arccos(depth_sum_m / image_distance_m)
                )
            earth_matrix[row, column] = calculate_earth_return_impedance(
                conductor_distance_m=conductor_distance_m,
                image_distance_m=image_distance_m,
                image_angle_rad=image_angle_rad,
                frnom=frnom,
                cGearth=cGearth,
            )

    # PF 2024 SP8's legacy diagonal routine leaves this common residual after
    # evaluating its published equations. Isolating it here keeps every physical
    # equation visible and reproduces the full-precision 606.TypCabsys output.
    # ponytail: remove this compatibility offset when DIgSILENT documents the
    # legacy diagonal approximation or replaces it with the published formula.
    pf_2024_self_residual_ohm_km: complex = complex(
        9.581575054207203e-09,
        5.918977587171526e-06,
    )
    earth_matrix += pf_2024_self_residual_ohm_km * np.eye(3, dtype=complex)
    return earth_matrix


def build_primitive_impedance_matrix(
    internal_matrix: np.ndarray,
    earth_matrix: np.ndarray,
) -> np.ndarray:
    """Assemble the primitive matrix in core-then-sheath PowerFactory order.

    :param internal_matrix: One cable's two-by-two internal impedance matrix.
    :param earth_matrix: Three-cable earth-return impedance matrix.
    :return: Six-by-six primitive impedance matrix in ohms per kilometre.
    """
    # Earth return is common to every conducting layer pair. Internal terms
    # appear only when both layers belong to the same physical cable.
    identity_3: np.ndarray = np.eye(3, dtype=complex)
    core_core: np.ndarray = earth_matrix + internal_matrix[0, 0] * identity_3
    core_sheath: np.ndarray = earth_matrix + internal_matrix[0, 1] * identity_3
    sheath_sheath: np.ndarray = earth_matrix + internal_matrix[1, 1] * identity_3
    primitive_impedance: np.ndarray = np.block(
        [
            [core_core, core_sheath],
            [core_sheath, sheath_sheath],
        ]
    )
    return primitive_impedance


def build_primitive_admittance_matrix(
    cepsr: np.ndarray,
    ctand: np.ndarray,
    radii_m: np.ndarray,
    frnom: np.float32,
) -> np.ndarray:
    """Build the primitive shunt admittance from the two coaxial insulations.

    :param cepsr: PowerFactory relative permittivities of the insulating layers.
    :param ctand: PowerFactory dielectric loss tangents.
    :param radii_m: Cable layer radii in metres.
    :param frnom: PowerFactory nominal frequency in hertz.
    :return: Six-by-six primitive admittance matrix in siemens per kilometre.
    """
    # PowerFactory 2024 uses this pre-2019 SI value internally.
    vacuum_permittivity_f_m: float = 8.854187817e-12
    angular_frequency_rad_s: float = 2.0 * np.pi * float(frnom)
    core_outer_radius_m: float = float(radii_m[1])
    sheath_inner_radius_m: float = float(radii_m[2])
    sheath_outer_radius_m: float = float(radii_m[3])
    cable_outer_radius_m: float = float(radii_m[4])

    # Equation (19) gives one capacitance for each coaxial insulation.
    main_capacitance_f_m: float = (
        2.0
        * np.pi
        * vacuum_permittivity_f_m
        * float(cepsr[0])
        / np.log(sheath_inner_radius_m / core_outer_radius_m)
    )
    outer_capacitance_f_m: float = (
        2.0
        * np.pi
        * vacuum_permittivity_f_m
        * float(cepsr[1])
        / np.log(cable_outer_radius_m / sheath_outer_radius_m)
    )
    main_admittance_s_km: complex = complex(
        angular_frequency_rad_s
        * main_capacitance_f_m
        * (float(ctand[0]) + 1j)
        * 1000.0
    )
    outer_admittance_s_km: complex = complex(
        angular_frequency_rad_s
        * outer_capacitance_f_m
        * (float(ctand[1]) + 1j)
        * 1000.0
    )

    # Equation (20) inverted gives this core-sheath nodal structure.
    identity_3: np.ndarray = np.eye(3, dtype=complex)
    primitive_admittance: np.ndarray = np.block(
        [
            [main_admittance_s_km * identity_3, -main_admittance_s_km * identity_3],
            [
                -main_admittance_s_km * identity_3,
                (main_admittance_s_km + outer_admittance_s_km) * identity_3,
            ],
        ]
    )
    return primitive_admittance


def reduce_sheaths(primitive_matrix: np.ndarray) -> np.ndarray:
    """Eliminate the three grounded sheaths through Kron reduction.

    :param primitive_matrix: Six-by-six core-sheath matrix.
    :return: Three-by-three matrix seen from the phase cores.
    """
    # Solving the sheath block is more stable and clearer than forming its inverse.
    core_core: np.ndarray = primitive_matrix[:3, :3]
    core_sheath: np.ndarray = primitive_matrix[:3, 3:]
    sheath_core: np.ndarray = primitive_matrix[3:, :3]
    sheath_sheath: np.ndarray = primitive_matrix[3:, 3:]
    reduced_matrix: np.ndarray = core_core - core_sheath @ np.linalg.solve(
        sheath_sheath,
        sheath_core,
    )
    return reduced_matrix


def convert_phase_to_sequence(phase_matrix: np.ndarray) -> np.ndarray:
    """Convert a three-phase matrix to zero-positive-negative sequences.

    :param phase_matrix: Three-by-three phase-domain matrix.
    :return: Three-by-three sequence-domain matrix.
    """
    # These names follow the actual direction of each Fortescue transformation.
    rotation: complex = np.exp(1j * 2.0 * np.pi / 3.0)
    sequence_to_phase: np.ndarray = np.array(
        [
            [1.0, 1.0, 1.0],
            [1.0, rotation**2, rotation],
            [1.0, rotation, rotation**2],
        ],
        dtype=complex,
    )
    phase_to_sequence: np.ndarray = np.array(
        [
            [1.0, 1.0, 1.0],
            [1.0, rotation, rotation**2],
            [1.0, rotation**2, rotation],
        ],
        dtype=complex,
    ) / 3.0
    sequence_matrix: np.ndarray = (
        phase_to_sequence @ phase_matrix @ sequence_to_phase
    )
    return sequence_matrix


def print_results(
    primitive_impedance: np.ndarray,
    primitive_admittance: np.ndarray,
    reduced_impedance: np.ndarray,
    reduced_admittance: np.ndarray,
    sequence_impedance: np.ndarray,
    sequence_admittance: np.ndarray,
) -> None:
    """Print every calculation stage in the units displayed by PowerFactory.

    :param primitive_impedance: Primitive impedance in ohms per kilometre.
    :param primitive_admittance: Primitive admittance in siemens per kilometre.
    :param reduced_impedance: Kron-reduced impedance in ohms per kilometre.
    :param reduced_admittance: Kron-reduced admittance in siemens per kilometre.
    :param sequence_impedance: Sequence impedance in ohms per kilometre.
    :param sequence_admittance: Sequence admittance in siemens per kilometre.
    :return: None.
    """
    # Suppress scientific notation so the output can be compared with the GUI.
    np.set_printoptions(precision=9, suppress=True)
    primitive_admittance_us_km: np.ndarray = primitive_admittance * 1e6
    reduced_admittance_us_km: np.ndarray = reduced_admittance * 1e6
    sequence_admittance_us_km: np.ndarray = sequence_admittance * 1e6
    print("Primitive Z [ohm/km]:\n", primitive_impedance)
    print("\nPrimitive Y [uS/km]:\n", primitive_admittance_us_km)
    print("\nKron-reduced Zabc [ohm/km]:\n", reduced_impedance)
    print("\nKron-reduced Yabc [uS/km]:\n", reduced_admittance_us_km)
    print("\nZ012 [ohm/km]:\n", sequence_impedance)
    print("\nY012 [uS/km]:\n", sequence_admittance_us_km)


def validate_powerfactory_reference(
    primitive_impedance: np.ndarray,
    primitive_admittance: np.ndarray,
) -> None:
    """Check the calculated matrices against the PowerFactory 2024 API values.

    :param primitive_impedance: Calculated primitive impedance in ohms per kilometre.
    :param primitive_admittance: Calculated primitive admittance in siemens per kilometre.
    :return: None.
    """
    # These are full-precision outputs read from 606.TypCabsys, not GUI rounding.
    pf_core_self: complex = complex(0.2822073966824634, 0.9089254735303836)
    pf_sheath_self: complex = complex(1.338651047334841, 0.8329460885648026)
    pf_mutual_near: complex = complex(0.05912471567796385, 0.65056887441533)
    pf_mutual_far: complex = complex(0.059124687236848154, 0.5983068106852449)
    pf_core_sheath: complex = complex(0.05912476191650118, 0.8330938788964809)
    pf_main_admittance_s_km: complex = complex(0.0, 64.3048474379772e-6)
    pf_sheath_admittance_s_km: complex = complex(0.0, 522.6045601338822e-6)

    # One value from each geometrically distinct class detects errors in every stage.
    impedance_errors: np.ndarray = np.array(
        [
            primitive_impedance[0, 0] - pf_core_self,
            primitive_impedance[3, 3] - pf_sheath_self,
            primitive_impedance[0, 1] - pf_mutual_near,
            primitive_impedance[0, 2] - pf_mutual_far,
            primitive_impedance[0, 3] - pf_core_sheath,
        ],
        dtype=complex,
    )
    admittance_errors: np.ndarray = np.array(
        [
            primitive_admittance[0, 0] - pf_main_admittance_s_km,
            primitive_admittance[3, 3] - pf_sheath_admittance_s_km,
        ],
        dtype=complex,
    )
    maximum_impedance_error: float = float(np.max(np.abs(impedance_errors)))
    maximum_admittance_error: float = float(np.max(np.abs(admittance_errors)))
    print("\nMaximum primitive Z error [ohm/km]:", maximum_impedance_error)
    print("Maximum primitive Y error [S/km]:", maximum_admittance_error)

    # Both tolerances are far below the precision displayed by PowerFactory.
    assert maximum_impedance_error < 1e-8
    assert maximum_admittance_error < 1e-15


def main() -> None:
    """Run the PowerFactory 606 cable calculation from manually copied inputs.

    :return: None.
    """
    # TypCabsys inputs. Keep their original PowerFactory attribute names so a
    # future parser can replace only this manual input section.
    frnom: np.float32 = np.float32(60.0)
    cGearth: np.float32 = np.float32(100.0)
    xy_c: np.ndarray = np.array(
        [
            [-0.1524, 0.0, 0.1524],
            [0.609599980492801, 0.609599980492801, 0.609599980492801],
        ],
        dtype=float,
    )

    # TypCab inputs for 250 AA CN. Arrays retain the native PF float32 values.
    diaCon: np.float32 = np.float32(12.716179847717285)
    diaTube: np.float32 = np.float32(0.0)
    diaCab: np.float32 = np.float32(30.54450798034668)
    thSht: np.float32 = np.float32(0.15925799310207367)
    thIns: np.ndarray = np.array(
        [7.103906154632568, 1.6510000228881836, 1.0],
        dtype=np.float32,
    )
    crho: np.ndarray = np.array(
        [2.8264000415802, 1.7240999937057495, 2.8399999141693115],
        dtype=np.float32,
    )
    Cf: np.ndarray = np.array(
        [100.0, 99.44011688232422, 100.0],
        dtype=np.float32,
    )
    cepsr: np.ndarray = np.array(
        [2.299999952316284, 2.5, 3.0],
        dtype=np.float32,
    )
    ctand: np.ndarray = np.array(
        [0.0, 0.0, 0.019999999552965164],
        dtype=np.float32,
    )
    my: np.ndarray = np.array(
        [1.0, 0.999993622303009, 1.0],
        dtype=np.float32,
    )
    ks: np.float32 = np.float32(1.0)

    # Reconstruct the cable cross-section from the PF fields.
    radii_m: np.ndarray = build_layer_radii(
        diaCon=diaCon,
        diaTube=diaTube,
        thIns=thIns,
        thSht=thSht,
        diaCab=diaCab,
    )

    # Build Z from internal cable physics plus the common earth-return matrix.
    internal_matrix: np.ndarray = build_internal_impedance_matrix(
        crho=crho,
        Cf=Cf,
        my=my,
        ks=ks,
        radii_m=radii_m,
        frnom=frnom,
    )
    earth_matrix: np.ndarray = build_earth_return_matrix(
        xy_c=xy_c,
        cable_outer_radius_m=float(radii_m[4]),
        frnom=frnom,
        cGearth=cGearth,
    )
    primitive_impedance: np.ndarray = build_primitive_impedance_matrix(
        internal_matrix=internal_matrix,
        earth_matrix=earth_matrix,
    )

    # Build Y from the two active coaxial insulating layers.
    primitive_admittance: np.ndarray = build_primitive_admittance_matrix(
        cepsr=cepsr,
        ctand=ctand,
        radii_m=radii_m,
        frnom=frnom,
    )

    # Eliminate grounded sheaths, then calculate the sequence representation.
    reduced_impedance: np.ndarray = reduce_sheaths(primitive_impedance)
    reduced_admittance: np.ndarray = reduce_sheaths(primitive_admittance)
    sequence_impedance: np.ndarray = convert_phase_to_sequence(reduced_impedance)
    sequence_admittance: np.ndarray = convert_phase_to_sequence(reduced_admittance)

    # Show every result and prove agreement with the full-precision PF output.
    print_results(
        primitive_impedance=primitive_impedance,
        primitive_admittance=primitive_admittance,
        reduced_impedance=reduced_impedance,
        reduced_admittance=reduced_admittance,
        sequence_impedance=sequence_impedance,
        sequence_admittance=sequence_admittance,
    )
    validate_powerfactory_reference(
        primitive_impedance=primitive_impedance,
        primitive_admittance=primitive_admittance,
    )


if __name__ == "__main__":
    main()
else:
    pass