import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit, ConverterFaultControlType
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np


def test_short_circuit_vsc_3buses():
    grid = vge.MultiCircuit()

    # ------------------------------------------------------------------------------------------------------------------
    #   Buses
    # ------------------------------------------------------------------------------------------------------------------
    bus_dc = vge.Bus(name='Bus DC', Vnom=20.0, xpos=0, ypos=0, is_dc=True, is_slack=True)
    grid.add_bus(obj=bus_dc)

    bus_wt = vge.Bus(name='Bus WT', Vnom=20.0, xpos=0, ypos=300)
    grid.add_bus(obj=bus_wt)

    bus_ac = vge.Bus(name='Bus AC', Vnom=20.0, xpos=0, ypos=600, r_fault=15)  # Rf = 60 ohm
    grid.add_bus(obj=bus_ac)

    bus_slack = vge.Bus(name='Bus Slack', Vnom=20.0, xpos=0, ypos=1200, is_slack=True)
    grid.add_bus(obj=bus_slack)

    # ------------------------------------------------------------------------------------------------------------------
    #   Line
    # ------------------------------------------------------------------------------------------------------------------
    line_wt_ac = vge.Line(name='Line WT-AC', bus_from=bus_wt, bus_to=bus_ac, r=1, x=10, rate=2.5)
    grid.add_line(line_wt_ac)

    line_slack_ac = vge.Line(name='Line AC-Slack', bus_from=bus_ac, bus_to=bus_slack, r=1, x=10, rate=2.5)
    grid.add_line(line_slack_ac)

    # ------------------------------------------------------------------------------------------------------------------
    #   VSC
    # ------------------------------------------------------------------------------------------------------------------
    vsc = vge.VSC(bus_from=bus_dc,
                  bus_to=bus_wt,
                  rate=2.0,
                  alpha1=0.0,
                  alpha2=0.0,
                  alpha3=0.0,
                  control1=ConverterControlType.Pac,
                  control2=ConverterControlType.Qac,
                  control1_val=-2.0,
                  control2_val=-0.0,
                  fault_control=ConverterFaultControlType.WECC_WT_Type_4B)
    grid.add_vsc(vsc)

    # ------------------------------------------------------------------------------------------------------------------
    #   Generators
    # ------------------------------------------------------------------------------------------------------------------
    generator_dc = vge.Generator()
    grid.add_generator(bus_dc, generator_dc)

    generator_ac = vge.Generator(r1=0.1, x1=1)
    grid.add_generator(bus_slack, generator_ac)

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=False,
                                  limit_i_vsc=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options)

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ------------------------------------------------------------------------------------------------------------------
    grid.add_short_circuit_event(
        vge.ShortCircuitEvent(
            device=grid.buses[2],
            method=MethodShortCircuit.sequences_vsc,
        )
    )

    sc_driver = vge.ShortCircuitDriver(grid=grid,
                                       options=ShortCircuitOptions(),
                                       pf_options=pf_options,
                                       pf_results=res_pf,
                                       pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    Usc_reference = np.array([1.0, 0.8588555, 0.84927272, 0.98754222])

    assert np.allclose(abs(res_sc.voltage1[:, 0]), Usc_reference, atol=1e-6)


def test_short_circuit_vsc_14buses():
    grid = vge.open_file('data/grids/test_ieee_14_VSC.veragrid')

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options_1)

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ------------------------------------------------------------------------------------------------------------------
    pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False)

    grid.add_short_circuit_event(
        vge.ShortCircuitEvent(
            device=grid.buses[9],
            method=MethodShortCircuit.sequences_vsc,
        )
    )

    sc_driver = vge.ShortCircuitDriver(grid=grid,
                                       options=ShortCircuitOptions(),
                                       pf_options=pf_options_2,
                                       pf_results=res_pf,
                                       pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    Usc_reference = np.array(
        [0.99999646, 0.91623742, 0.8343526, 0.84994944, 0.86575979, 0.80622333, 0.80935283, 0.78726428, 0.77192103,
         0.74351305, 0.80790032, 0.79696124, 0.7823984, 0.94797783, 0.86826011, 0.84541255, 0.84725015, 0.81377177,
         0.84692126, 0.83635092, 0.82205093, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

    assert np.allclose(abs(res_sc.voltage1[:, 0]), Usc_reference, atol=1e-6)


def test_short_circuit_vsc_14buses_disconnection():
    grid = vge.open_file('data/grids/ieee14_voltage_disconnection.veragrid')

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False,
                                    verbose=1)
    res_pf = vge.power_flow(grid=grid, options=pf_options_1)

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ------------------------------------------------------------------------------------------------------------------
    pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False,
                                    verbose=1,
                                    max_iter=150,
                                    tolerance=1e-6)

    sc_driver = vge.ShortCircuitDriver(grid=grid,
                                       options=ShortCircuitOptions(),
                                       pf_options=pf_options_2,
                                       pf_results=res_pf,
                                       pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    Usc_reference = np.array(
        [0.999995, 0.889860, 0.784740, 0.795609, 0.817928, 0.707190, 0.715203, 0.678870, 0.674796, 0.685194, 0.686982,
         0.661633, 0.580896,
         0.885126, 0.781599, 0.709719, 0.717729, 0.678525, 0.690968, 0.667667, 0.580896,
         1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])

    assert np.allclose(abs(res_sc.voltage1[:, 1]), Usc_reference, atol=1e-6)


def test_ieee14_droop_vsc():
    grid = vge.open_file('data/grids/test_ieee14_droop_vsc.veragrid')

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options_1)

    power_factory = np.array([
        1.000000, 0.956300, 0.902994, 0.929376, 0.940030, 0.925800, 0.916305, 0.903538, 0.906176, 0.911815, 0.931089, 0.920778, 0.908115,
        0.982396, 0.962955, 0.971214, 0.967765, 0.964102, 0.973142, 0.969388, 0.964802,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0
    ], dtype=float)

    assert np.allclose(np.abs(res_pf.voltage), power_factory, atol=1e-6)


def test_dgs_parse_droop_vsc():
    grid = vge.open_file('data/grids/test_droop_vsc.dgs')

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ------------------------------------------------------------------------------------------------------------------
    pf_options = PowerFlowOptions(solver_type=SolverType.NR,
                                  retry_with_other_methods=False,
                                  limit_i_vsc=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options)

    # ------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ------------------------------------------------------------------------------------------------------------------
    grid.buses[1].r_fault = 6.0 / (33 ** 2 / 100)

    grid.add_short_circuit_event(
        vge.ShortCircuitEvent(
            device=grid.buses[1],
            method=MethodShortCircuit.sequences_vsc,
        )
    )

    sc_driver = vge.ShortCircuitDriver(grid=grid,
                                       options=ShortCircuitOptions(),
                                       pf_options=pf_options,
                                       pf_results=res_pf,
                                       pf_results3ph=None)
    sc_driver.run()
    res_sc = sc_driver.results

    power_factory = np.array([1.0, 0.70796575, 1.0])

    assert np.allclose(np.abs(res_sc.voltage1[:,0]), power_factory, atol=1e-6)