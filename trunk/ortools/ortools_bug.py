from ortools.linear_solver.python import model_builder
from ortools import __version__
print(__version__)

# Create a new model
model = model_builder.Model()

# Create variables
Delta_down_0 = model.new_var(name='Delta_down_0', lb=0, ub=float('inf'), is_integer=False)
ac_flow_0_10 = model.new_var(name='ac_flow_0_10', lb=0, ub=float('inf'), is_integer=False)
ac_flow_0_11 = model.new_var(name='ac_flow_0_11', lb=0, ub=float('inf'), is_integer=False)

# += or -= produce a doubling of some vars
expr1 = -0.333333 * Delta_down_0
expr1 -= ac_flow_0_10
expr1 -= ac_flow_0_11

# Add the constraint,
cst = model.add(expr1 == -0.592888)

print("expr1", expr1)

# This will be handled properly
expr2 = -0.333333 * Delta_down_0
expr2 = expr2 - ac_flow_0_10
expr2 = expr2 - ac_flow_0_11

# Add the constraint
cst2 = model.add(expr2 == -0.592888)

print("expr2", expr2)
