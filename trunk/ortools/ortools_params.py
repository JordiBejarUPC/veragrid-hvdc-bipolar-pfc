import ortools.linear_solver as lin
from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder_helper import SolveStatus

# Create the model
model = model_builder.Model()

# Create variables
x = model.new_var(name='x', lb=0, ub=float('inf'), is_integer=False)  # x >= 0
y = model.new_var(name='y', lb=0, ub=float('inf'), is_integer=False)  # y >= 0

# Add the objective function (maximize: 2x + 3y)
model.minimize(2 * x + 3 * y)

# Add constraints
model.add(x + y <= 4)  # x + y <= 4

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
solver.set_solver_specific_parameters(params)

status = solver.solve(model)

print("status:", status)

# Check if an optimal solution is found
if status == SolveStatus.OPTIMAL:
    print('Solution:')
    print(f'x = {solver.value(x)}')
    print(f'y = {solver.value(y)}')
else:
    print('No optimal solution found.')
