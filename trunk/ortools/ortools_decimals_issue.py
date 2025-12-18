from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder_helper import SolveStatus

mps_path = "NTC test_issue_372_1 PuLP.mps"
model = model_builder.ModelBuilder()
model.import_from_mps_file(mps_path)

# Set solver-specific parameters for Highs solver
params = """
primal_residual_tolerance = 1e-8
primal_feasibility_tolerance = 1e-8
dual_feasibility_tolerance = 1e-8
mip_abs_gap = 1e-8
time_limit = 60000
"""
# Build solver with Highs solver
solver = model_builder.Solver('Highs')

# Set the solver parameters
# solver.set_solver_specific_parameters(params)

status = solver.solve(model)

print("status:", status)

# Check if an optimal solution is found
if status == SolveStatus.OPTIMAL:
    print('Solution:')
    var_dict = {v.name: v for v in model.get_variables()}
    Delta_down_0 = solver.value(var_dict['Delta_down_0'])
    ac_flow_0_10 = solver.value(var_dict['ac_flow_0_10'])
    ac_flow_0_11 = solver.value(var_dict['ac_flow_0_11'])

    # hirchof_0_0 constraint
    val = - 0.333333 * Delta_down_0 - ac_flow_0_10 - ac_flow_0_11
    err = val + 0.592887637492

    print()

else:
    print('No optimal solution found.')

print()
