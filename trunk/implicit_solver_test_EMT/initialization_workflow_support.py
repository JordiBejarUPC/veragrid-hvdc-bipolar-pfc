import numpy as np
from typing import Tuple

import VeraGridEngine.api as gce
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.emt_options import EmtOptions
from VeraGridEngine.Simulations.EMT.problems.emt_problem_dae import EmtProblemDae
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowOptions
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver_3ph import PowerFlowDriver3Ph
from VeraGridEngine.Utils.Symbolic.bus_emt_template import get_bus_emt_template
from VeraGridEngine.Templates.Emt.load_RLC_emt_template import get_shunt_r_emt_template
from VeraGridEngine.Templates.Emt.load_zip_emt_template import get_load_ZIP_emt_template
from VeraGridEngine.Templates.Emt.pi_line_emt_template import get_pi_line_emt_template
from VeraGridEngine.Templates.Emt.thevenin_equivalent_emt_generator_template import get_generator_thevenin_rl_emt_template_with_ref
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicVector
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Expr, Var
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_emt_model
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtInitializationMethod, EmtSolverTypes, ShuntConnectionType


class GenericEmtProblem(EmtProblemTemplate):
    """
    Minimal EMT problem implementation used by initialization workflow tests.
    """

    __slots__ = []


class SimpleInitializationContext:
    """
    Typed container for the tiny EMT initialization test problems.
    """

    __slots__ = ["_x_var", "_y_var", "_dx_var"]

    def __init__(self, x_var: Var, y_var: Var, dx_var: Var) -> None:
        """
        Build one simple initialization context.

        :param x_var: State variable.
        :param y_var: Algebraic variable.
        :param dx_var: Differential variable.
        :return: None
        """
        self._x_var: Var = x_var
        self._y_var: Var = y_var
        self._dx_var: Var = dx_var

    def get_x_var(self) -> Var:
        """
        Return the state variable.

        :return: State variable.
        """
        return self._x_var

    def get_y_var(self) -> Var:
        """
        Return the algebraic variable.

        :return: Algebraic variable.
        """
        return self._y_var

    def get_dx_var(self) -> Var:
        """
        Return the differential variable.

        :return: Differential variable.
        """
        return self._dx_var


class TwoBusRealEmtContext:
    """
    Typed container for the real two-bus EMT benchmark case.
    """

    __slots__ = ["_grid", "_bus0", "_bus1", "_line0", "_load", "_gen0", "_gen_mdl", "_line_mdl", "_load_mdl", "_pf_results"]

    def __init__(
            self,
            grid: gce.MultiCircuit,
            bus0: gce.Bus,
            bus1: gce.Bus,
            line0: gce.Line,
            load: gce.Load,
            gen0: gce.Generator,
            gen_mdl: Block,
            line_mdl: Block,
            load_mdl: Block,
            pf_results: object,
    ) -> None:
        """
        Build one real-case context bundle.

        :param grid: Multi-circuit container.
        :param bus0: Slack bus.
        :param bus1: Load bus.
        :param line0: EMT line.
        :param load: EMT load.
        :param gen0: EMT generator.
        :param gen_mdl: Generator EMT block.
        :param line_mdl: Line EMT block.
        :param load_mdl: Load EMT block.
        :param pf_results: Power-flow results object.
        :return: None
        """
        self._grid: gce.MultiCircuit = grid
        self._bus0: gce.Bus = bus0
        self._bus1: gce.Bus = bus1
        self._line0: gce.Line = line0
        self._load: gce.Load = load
        self._gen0: gce.Generator = gen0
        self._gen_mdl: Block = gen_mdl
        self._line_mdl: Block = line_mdl
        self._load_mdl: Block = load_mdl
        self._pf_results: object = pf_results

    def get_grid(self) -> gce.MultiCircuit:
        """
        Return the grid object.

        :return: Grid object.
        """
        return self._grid

    def get_pf_results(self) -> object:
        """
        Return the power-flow results object.

        :return: Power-flow results.
        """
        return self._pf_results


def build_single_state_single_algebraic_problem() -> Tuple[GenericEmtProblem, SimpleInitializationContext]:
    """
    Build a tiny EMT problem where explicit initialization resolves the state and
    consistent initialization resolves one algebraic variable.

    :return: Problem instance and variable lookup.
    """
    var_factory: VarFactory = VarFactory()
    x_var: Var = var_factory.add_var("x")
    y_var: Var = var_factory.add_var("y")
    dx_var: Var = var_factory.add_diff_var(name="d_x", base_var=x_var)

    block = Block(
        name="SingleStateSingleAlgebraicInit",
        state_vars=[x_var],
        diff_vars=[dx_var],
        state_eqs=[y_var - x_var],
        algebraic_vars=[y_var],
        algebraic_eqs=[y_var - Const(2.0)],
        init_eqs={x_var: Const(2.0)},
    )
    problem = GenericEmtProblem(sys_block=block, glob_time=var_factory.add_var("t_glob_init_0"))
    context = SimpleInitializationContext(x_var=x_var, y_var=y_var, dx_var=dx_var)
    return problem, context


def build_unresolved_state_problem() -> Tuple[GenericEmtProblem, SimpleInitializationContext]:
    """
    Build a tiny EMT problem where one state is left unresolved and must be solved
    from the steady-state condition.

    :return: Problem instance and variable lookup.
    """
    var_factory: VarFactory = VarFactory()
    x_var: Var = var_factory.add_var("x_eq")
    y_var: Var = var_factory.add_var("y_eq")
    dx_var: Var = var_factory.add_diff_var(name="d_x_eq", base_var=x_var)

    block = Block(
        name="UnresolvedStateEquilibriumInit",
        state_vars=[x_var],
        diff_vars=[dx_var],
        state_eqs=[y_var - x_var],
        algebraic_vars=[y_var],
        algebraic_eqs=[y_var - Const(3.0)],
    )
    problem = GenericEmtProblem(sys_block=block, glob_time=var_factory.add_var("t_glob_init_1"))
    context = SimpleInitializationContext(x_var=x_var, y_var=y_var, dx_var=dx_var)
    return problem, context


def evaluate_algebraic_residual_inf(problem: EmtProblemTemplate) -> float:
    """
    Evaluate the infinity norm of the algebraic residual at the current stored
    initialization point.

    :param problem: EMT problem to evaluate.
    :return: Algebraic residual infinity norm.
    """
    algebraic_eqs: list[Expr] = problem.get_algebraic_eqs()
    if len(algebraic_eqs) == 0:
        return 0.0
    else:
        residual_fn = SymbolicVector(
            eqs=algebraic_eqs,
            compiler_names_dict=problem._compiler_names_dict,
            alias_names_dict=problem._alias_names_dict,
            VARS_NAME=problem.VARS_NAME,
            DIFF_NAME=problem.DIFF_NAME,
            EVENT_PARAMS_NAME=problem.VARIABLE_PARAMS_NAME,
            PARAMS_NAME=problem.CONSTANT_PARAMS_NAME,
        )
        x0: np.ndarray = problem.get_x0()
        dx0: np.ndarray = problem.get_dx0()
        runtime_params: np.ndarray = problem.event_params_values.copy()
        runtime_params = problem.def_event_params_fn(runtime_params, 0.0)
        constant_params: np.ndarray = np.asarray([float(item.value) for item in problem.get_parameters_values()], dtype=np.float64)
        residual: np.ndarray = residual_fn(x0, dx0, runtime_params, constant_params)
        return float(np.max(np.abs(residual)))


def build_two_bus_real_emt_case(
        zip_load: bool = True,
        initialization_method: EmtInitializationMethod = EmtInitializationMethod.Auto,
) -> Tuple[EmtProblemDae, TwoBusRealEmtContext]:
    """
    Build the standard real EMT two-bus benchmark case used by snapshot and
    initialization tests.

    :param zip_load: Whether to use the ZIP load model instead of the resistive load.
    :param initialization_method: EMT initialization workflow to request.
    :return: EMT problem and contextual objects.
    """
    grid = gce.MultiCircuit(Sbase=2.0, fbase=50.0)

    vnom: float = 10.0
    bus0 = gce.Bus(name="Bus0", Vnom=vnom, is_slack=True)
    bus1 = gce.Bus(name="Bus1", Vnom=vnom)
    grid.add_bus(bus0)
    grid.add_bus(bus1)

    line0 = gce.Line(name="line0", bus_from=bus0, bus_to=bus1, length=10, rate=900.0)


    tower = gce.OverheadLineType(name="Tower", Vnom=vnom)
    wire = gce.Wire(
        name="Panther 30/7 ACSR",
        diameter=21.0,
        diameter_internal=9.0,
        is_tube=True,
        r=0.1363,
        max_current=1,
    )
    tower.add_wire_relationship(wire=wire, xpos=-12.65, ypos=27.5, phase=1)
    tower.add_wire_relationship(wire=wire, xpos=0.0, ypos=27.5, phase=2)
    tower.add_wire_relationship(wire=wire, xpos=12.65, ypos=27.5, phase=3)
    tower.compute()
    line0.apply_template(tower, grid.Sbase, grid.fBase)

    r_ph: float = 100.0
    v_ph: float = vnom / (3.0 ** 0.5)
    p_ph: float = (v_ph ** 2) / r_ph
    load = gce.Load(name="load", P1=p_ph, P2=p_ph, P3=p_ph, Q1=0.0, Q2=0.0, Q3=0.0)
    load.conn = ShuntConnectionType.GroundedStar

    gen0 = gce.Generator(name="Gen0", vset=1.0, Snom=grid.Sbase, freq=50, r1=0.001, x1=1.7)

    grid.add_line(line0)
    grid.add_generator(bus=bus0, api_obj=gen0)
    grid.add_load(bus=bus1, api_obj=load)

    for bus in grid.buses:
        get_bus_emt_template(grid, bus)

    gen_mdl = get_generator_thevenin_rl_emt_template_with_ref(vf = grid.var_factory).block
    line_mdl = get_pi_line_emt_template(vf=grid.var_factory, line=line0).block
    if zip_load:
        load_mdl = get_load_ZIP_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block
    else:
        load_mdl = get_shunt_r_emt_template(vf=grid.var_factory, phA=True, phB=True, phC=True).block

    set_emt_model(device=gen0, model=gen_mdl, var_factory=grid.var_factory)

    set_emt_model(device=line0, model=line_mdl, var_factory=grid.var_factory)

    set_emt_model(device=load, model=load_mdl, var_factory=grid.var_factory)

    pf_options = PowerFlowOptions(
        solver_type=gce.SolverType.NR,
        retry_with_other_methods=False,
        verbose=0,
        initialize_with_existing_solution=True,
        tolerance=1e-6,
        max_iter=25,
        control_q=False,
        control_taps_modules=True,
        control_taps_phase=True,
        control_remote_voltage=True,
        orthogonalize_controls=True,
        apply_temperature_correction=True,
        branch_impedance_tolerance_mode=gce.BranchImpedanceMode.Specified,
        distributed_slack=False,
        ignore_single_node_islands=False,
        trust_radius=1.0,
        backtracking_parameter=0.05,
        use_stored_guess=False,
        initialize_angles=False,
        generate_report=False,
    )
    power_flow = PowerFlowDriver3Ph(grid, pf_options)
    power_flow.run()
    pf_results = power_flow.results

    options = EmtOptions(
        time_step=5e-6,
        simulation_time=2e-4,
        tolerance=1e-6,
        solver_type=EmtSolverTypes.StructuralCompiled,
        integration_method=DynamicIntegrationMethod.DaeTrapezoidal,
        initialization_method=initialization_method,
        verbose=0,
    )
    problem = EmtProblemDae(grid=grid, options=options, pf_results_3ph=pf_results, pf_results=None)

    context = TwoBusRealEmtContext(
        grid=grid,
        bus0=bus0,
        bus1=bus1,
        line0=line0,
        load=load,
        gen0=gen0,
        gen_mdl=gen_mdl,
        line_mdl=line_mdl,
        load_mdl=load_mdl,
        pf_results=pf_results,
    )
    return problem, context
