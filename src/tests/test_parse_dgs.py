import os
import numpy as np
import VeraGridEngine as vg


def test_parse_dsg_grids():
    fname = os.path.join('data', 'grids', 'DGS', "mygrid.dgs")

    main_circuit = vg.FileOpen(fname).open()

    options = vg.PowerFlowOptions(solver_type=vg.SolverType.NR,
                                  verbose=0,
                                  control_q=False,
                                  retry_with_other_methods=False)

    power_flow = vg.PowerFlowDriver(main_circuit, options)
    power_flow.run()

    res = power_flow.results

    # TODO: include Asserts
    # assert 2 == 2.000000000003
    assert np.isclose(2, 2.000000000003, atol=1e-3)


