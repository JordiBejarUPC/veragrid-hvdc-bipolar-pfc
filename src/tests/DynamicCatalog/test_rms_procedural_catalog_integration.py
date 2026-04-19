from __future__ import annotations

import numpy as np

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import get_powerfactory_basic_catalog_descriptor_by_typ_id
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog import load_powerfactory_basic_catalog_template
from VeraGridEngine.Utils.procedural_logic import build_boundary_updater_from_block
from VeraGridEngine.Utils.Symbolic.symbolic import Var


def test_rms_update_variable_params_applies_catalog_procedural_logic() -> None:
    descriptor = get_powerfactory_basic_catalog_descriptor_by_typ_id()["504"]
    template = load_powerfactory_basic_catalog_template(descriptor, VarFactory())
    problem = RmsProblemDae.__new__(RmsProblemDae)
    runtime_parameters = list(template.block.event_dict.keys()) + list(template.block.mode_dict.keys())
    ordered_vars = list()

    for candidate in template.block.in_vars + template.block.out_vars + template.block.algebraic_vars + template.block.state_vars:
        if candidate.uid not in {var.uid for var in ordered_vars}:
            ordered_vars.append(candidate)
        else:
            pass

    problem.sys_block = template.block
    problem._glob_time = Var("glob_time")
    problem._uid2idx_vars = {var.uid: idx for idx, var in enumerate(ordered_vars)}
    problem._uid2idx_event_params = {var.uid: idx for idx, var in enumerate(runtime_parameters)}
    problem._variable_parameters = runtime_parameters
    problem._parameters_values = list()
    problem._constant_params = np.zeros(0, dtype=float)
    problem._variable_parameters_values = np.array([1.0, 0.0], dtype=float)
    problem._event_params_fn = lambda values, _: values
    problem._block_boundary_updater = build_boundary_updater_from_block(problem)

    RmsProblemDae.update_variable_params(problem, t=0.0, x_snapshot=np.zeros(len(ordered_vars), dtype=float))

    assert problem._variable_parameters_values[0] == 1.0
    assert problem._variable_parameters_values[1] == 1.0
