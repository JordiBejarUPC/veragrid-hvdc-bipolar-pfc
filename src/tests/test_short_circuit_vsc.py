import VeraGridEngine.api as vge
from VeraGridEngine import PowerFlowOptions, ShortCircuitOptions
from VeraGridEngine.enumerations import ConverterControlType, MethodShortCircuit
from VeraGridEngine.Simulations.PowerFlow.power_flow_options import SolverType
import numpy as np

def test_short_circuit_vsc_3buses():

    grid = vge.MultiCircuit()

    # ----------------------------------------------------------------------------------------------------------------------
    #   Buses
    # ----------------------------------------------------------------------------------------------------------------------
    bus_dc = vge.Bus(name='Bus DC', xpos=0, ypos=0, is_dc=True)
    grid.add_bus(obj=bus_dc)

    bus_ac = vge.Bus(name='Bus AC', xpos=0, ypos=300, r_fault=0.2)
    grid.add_bus(obj=bus_ac)

    bus_slack = vge.Bus(name='Bus Slack', xpos=0, ypos=600, is_slack=True)
    grid.add_bus(obj=bus_slack)

    # ----------------------------------------------------------------------------------------------------------------------
    #   Line
    # ----------------------------------------------------------------------------------------------------------------------
    line_slack_ac = vge.Line(name='AC - Slack', bus_from=bus_ac, bus_to=bus_slack, r=0.001, x=0.1, rate=20.0)
    grid.add_line(line_slack_ac)

    # ----------------------------------------------------------------------------------------------------------------------
    #   VSC
    # ----------------------------------------------------------------------------------------------------------------------
    vsc = vge.VSC(bus_from=bus_dc,
                  bus_to=bus_ac,
                  rate=10.0,
                  alpha1=0.0,
                  alpha2=0.0,
                  alpha3=0.0,
                  control1=ConverterControlType.Vm_dc,
                  control2=ConverterControlType.Qac,
                  control1_val=1.0,
                  control2_val=-5.0)
    grid.add_vsc(vsc)

    # ----------------------------------------------------------------------------------------------------------------------
    #   Generators
    # ----------------------------------------------------------------------------------------------------------------------
    generator_ac = vge.Generator(r1=0.005, x1=0.05)
    grid.add_generator(bus_slack, generator_ac)

    generator_dc = vge.Generator(P=10.0, power_factor=1.0, r1=0.005)
    grid.add_generator(bus_dc, generator_dc)

    # ----------------------------------------------------------------------------------------------------------------------
    #   DC Loads
    # ----------------------------------------------------------------------------------------------------------------------
    load_dc_power = vge.Load(P=1.0)
    grid.add_load(bus_dc, load_dc_power)

    load_dc_current = vge.Load(Ir=1.0)
    grid.add_load(bus_dc, load_dc_current)

    load_dc_admittance = vge.Load(G=1.0)
    grid.add_load(bus_dc, load_dc_admittance)

    # ----------------------------------------------------------------------------------------------------------------------
    #   Save Grid
    # ----------------------------------------------------------------------------------------------------------------------
    vge.save_file(grid=grid, filename='shortcircuit_vsc.veragrid')

    # ----------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ----------------------------------------------------------------------------------------------------------------------
    pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False,
                                    verbose=1)
    res_pf = vge.power_flow(grid=grid, options=pf_options_1)

    print('Power flow results:')
    print(abs(res_pf.voltage))

    # ----------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ----------------------------------------------------------------------------------------------------------------------
    pf_options_2 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=True,
                                    verbose=1)

    grid.add_short_circuit_event(
        vge.ShortCircuitEvent(
            device=grid.buses[1],
            method=MethodShortCircuit.sequences_vsc
        )
    )

    sc_driver = vge.ShortCircuitDriver(grid=grid,
                                       options=ShortCircuitOptions(),
                                       pf_options=pf_options_2,
                                       pf_results=res_pf,
                                       pf_results3ph=None)
    sc_driver.run()

    res_sc = sc_driver.results

    Usc_reference = np.array([
        [1.0],
        [0.79343276],
        [0.88245054]
    ])

    St_vsc_reference = np.array([
        [-7.0-3.73544573j]
    ])

    St_line_reference = np.array([
        [-307.76777399+3.73544573j]
    ])

    assert np.allclose(abs(res_sc.voltage1[:, 0]), Usc_reference, atol=1e-6)
    assert np.allclose(res_sc.vsc_St, St_vsc_reference, atol=1e-6)
    assert np.allclose(res_sc.Sf1, St_line_reference, atol=1e-6)


def test_short_circuit_vsc_14buses():

    grid = vge.open_file('data/grids/test_ieee_14_VSC.veragrid')

    # ----------------------------------------------------------------------------------------------------------------------
    #   AC/DC Power Flow under healthy conditions
    # ----------------------------------------------------------------------------------------------------------------------
    pf_options_1 = PowerFlowOptions(solver_type=SolverType.NR,
                                    retry_with_other_methods=False,
                                    limit_i_vsc=False)
    res_pf = vge.power_flow(grid=grid, options=pf_options_1)

    print(res_pf.get_voltage_df())

    # ----------------------------------------------------------------------------------------------------------------------
    #   AC/DC Short-Circuit with converter's current limitation
    # ----------------------------------------------------------------------------------------------------------------------
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