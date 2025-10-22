import VeraGridEngine.api as gce
from VeraGridEngine import WindingType, ShuntConnectionType, SolverType
import numpy as np


def test_impedance_groundedstar_3ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.6,
                        B2=0.45,
                        G3=0.5,
                        B3=0.4)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_632,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(XFM_1)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0j, 0.90207824 - 0.04158922j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.48710729 - 0.77306215j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.4372112 + 0.81472313j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_floatingstar_3ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.6,
                        B2=0.45,
                        G3=0.5,
                        B3=0.4)
    load_634.conn = ShuntConnectionType.FloatingStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_632,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(XFM_1)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Un_reference = np.array(
        [0.07318343 - 0.02992788j]
    )

    Ua_reference = np.array(
        [1 + 0j, 0.91048917 - 0.04147616j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.47968669 - 0.77307996j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.43080248 + 0.81455613j])

    assert np.allclose(res.load_Vn, Un_reference, atol=1e-4)
    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_neutralstar_3ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=4.16, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.6,
                        B2=0.45,
                        G3=0.5,
                        B3=0.4)
    load_634.conn = ShuntConnectionType.NeutralStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Line
    # ----------------------------------------------------------------------------------------------------------------------
    z_nabc = np.array([
        [0.2735 + 1j * 0.8143, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509],
        [0.0173 + 1j * 0.0509, 0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
        [0.0173 + 1j * 0.0509, 0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
        [0.0173 + 1j * 0.0509, 0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
    ], dtype=complex) / 1.60934  # Ω/km

    y_nabc = np.array([
        [1j * 6.1541, -1j * 1.8918, -1j * 2.0022, -1j * 2.2602],
        [-1j * 1.8918, 1j * 6.2998, -1j * 1.9958, -1j * 1.2595],
        [-1j * 2.0022, -1j * 1.9958, 1j * 5.9597, -1j * 0.7417],
        [-1j * 2.2602, -1j * 1.2595, -1j * 0.7417, 1j * 5.6386]
    ], dtype=complex) / (10 ** 6) / 1.60934  # S/km

    configuration = gce.create_known_abc_overhead_template(name='4 wire line',
                                                           z_nabc=z_nabc,
                                                           ysh_nabc=y_nabc,
                                                           phases=np.array([0, 1, 2, 3]),
                                                           Vnom=4.16,
                                                           frequency=60)
    grid.add_overhead_line(configuration)

    line = gce.Line(bus_from=bus_632,
                    bus_to=bus_634,
                    length=2000 * 0.0003048)
    line.apply_template(configuration, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0.j, 0.96704514 - 0.016661j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.51101077 - 0.83803284j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.47984984 + 0.85244212j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_delta_3ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.6,
                        B2=0.45,
                        G3=0.5,
                        B3=0.4)
    load_634.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_632,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(XFM_1)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0j, 0.91678499 - 0.04164258j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.48340674 - 0.76670763j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.43337825 + 0.80835022j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_delta_2ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_634.conn = ShuntConnectionType.Delta
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_632,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(XFM_1)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0j, 0.96253052 - 0.05125713j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.46253242 - 0.81477074j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.5 + 0.8660254j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_groundedstar_1ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=0.48, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_634.conn = ShuntConnectionType.GroundedStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Transformer
    # ----------------------------------------------------------------------------------------------------------------------
    XFM_1 = gce.Transformer2W(name='XFM-1',
                              bus_from=bus_632,
                              bus_to=bus_634,
                              HV=4.16,
                              LV=0.48,
                              nominal_power=0.5,
                              rate=0.5,
                              r=1.1 * 2,
                              x=2 * 2)
    XFM_1.conn_f = WindingType.GroundedStar
    XFM_1.conn_t = WindingType.GroundedStar
    grid.add_transformer2w(XFM_1)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0j, 0.90207824 - 0.04158922j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.5 - 0.8660254j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.5 + 0.8660254j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)


def test_impedance_neutralstar_1ph():
    '''
    This test executes a three-phase power flow with neutral into a three-phase load connected in GroundedStar.
    The obtained results are compared against the ones obtained in OpenDSS.
    '''

    logger = gce.Logger()
    grid = gce.MultiCircuit()
    grid.fBase = 60

    # ----------------------------------------------------------------------------------------------------------------------
    # Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_632 = gce.Bus(name='Bus632', Vnom=4.16, xpos=0, ypos=0)
    bus_632.is_slack = True
    grid.add_bus(obj=bus_632)
    gen = gce.Generator(vset=1.0)
    grid.add_generator(bus=bus_632, api_obj=gen)

    bus_634 = gce.Bus(name='Bus634', Vnom=4.16, xpos=200 * 5, ypos=0)
    grid.add_bus(obj=bus_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Load
    # ----------------------------------------------------------------------------------------------------------------------
    load_634 = gce.Load(G1=0.7,
                        B1=0.5,
                        G2=0.0,
                        B2=0.0,
                        G3=0.0,
                        B3=0.0)
    load_634.conn = ShuntConnectionType.NeutralStar
    grid.add_load(bus=bus_634, api_obj=load_634)

    # ----------------------------------------------------------------------------------------------------------------------
    # Line
    # ----------------------------------------------------------------------------------------------------------------------
    z_nabc = np.array([
        [0.2735 + 1j * 0.8143, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509, 0.0173 + 1j * 0.0509],
        [0.0173 + 1j * 0.0509, 0.3465 + 1j * 1.0179, 0.1560 + 1j * 0.5017, 0.1580 + 1j * 0.4236],
        [0.0173 + 1j * 0.0509, 0.1560 + 1j * 0.5017, 0.3375 + 1j * 1.0478, 0.1535 + 1j * 0.3849],
        [0.0173 + 1j * 0.0509, 0.1580 + 1j * 0.4236, 0.1535 + 1j * 0.3849, 0.3414 + 1j * 1.0348]
    ], dtype=complex) / 1.60934  # Ω/km

    y_nabc = np.array([
        [1j * 6.1541, -1j * 1.8918, -1j * 2.0022, -1j * 2.2602],
        [-1j * 1.8918, 1j * 6.2998, -1j * 1.9958, -1j * 1.2595],
        [-1j * 2.0022, -1j * 1.9958, 1j * 5.9597, -1j * 0.7417],
        [-1j * 2.2602, -1j * 1.2595, -1j * 0.7417, 1j * 5.6386]
    ], dtype=complex) / (10 ** 6) / 1.60934  # S/km

    configuration = gce.create_known_abc_overhead_template(name='4 wire line',
                                                           z_nabc=z_nabc,
                                                           ysh_nabc=y_nabc,
                                                           phases=np.array([0, 1, 2, 3]),
                                                           Vnom=4.16,
                                                           frequency=60)
    grid.add_overhead_line(configuration)

    line = gce.Line(bus_from=bus_632,
                    bus_to=bus_634,
                    length=2000 * 0.0003048)
    line.apply_template(configuration, grid.Sbase, grid.fBase, logger)
    grid.add_line(obj=line)

    # ----------------------------------------------------------------------------------------------------------------------
    # Run power flow
    # ----------------------------------------------------------------------------------------------------------------------
    res = gce.power_flow(grid=grid, options=gce.PowerFlowOptions(three_phase_unbalanced=True,
                                                                 solver_type=SolverType.NR,
                                                                 retry_with_other_methods=False))

    # ----------------------------------------------------------------------------------------------------------------------
    # Results
    # ----------------------------------------------------------------------------------------------------------------------
    Ua_reference = np.array(
        [1 + 0j, 0.95515256 - 0.02854518j])

    Ub_reference = np.array(
        [-0.5 - 0.8660254j, -0.52030794 - 0.87981365j])

    Uc_reference = np.array(
        [-0.5 + 0.8660254j, -0.51784639 + 0.85547383j])

    assert np.allclose(res.voltage_A, Ua_reference, atol=1e-4)
    assert np.allclose(res.voltage_B, Ub_reference, atol=1e-4)
    assert np.allclose(res.voltage_C, Uc_reference, atol=1e-4)
