from ortools.linear_solver.python import model_builder
from ortools.linear_solver.python.model_builder_helper import SolveStatus

model = model_builder.Model()

# Create decision variables
DeltaSL_down_0 = model.new_var(0, 1e20, False, 'DeltaSL_down_0')
DeltaSL_up_0 = model.new_var(0, 1e20, False, 'DeltaSL_up_0')
Delta_down_0 = model.new_var(0, 1e20, False, 'Delta_down_0')
Delta_up_0 = model.new_var(0, 1e20, False, 'Delta_up_0')

# Declare the voltage variables (Va_0_X)
Va_0_0 = model.new_var(-6.28, 6.28, False, 'Va_0_0')
Va_0_1 = model.new_var(-6.28, 6.28, False, 'Va_0_1')
Va_0_2 = model.new_var(-6.28, 6.28, False, 'Va_0_2')
Va_0_3 = model.new_var(-6.28, 6.28, False, 'Va_0_3')
Va_0_4 = model.new_var(-6.28, 6.28, False, 'Va_0_4')
Va_0_5 = model.new_var(-6.28, 6.28, False, 'Va_0_5')
Va_0_6 = model.new_var(-6.28, 6.28, False, 'Va_0_6')
Va_0_7 = model.new_var(-6.28, 6.28, False, 'Va_0_7')
Va_0_8 = model.new_var(-6.28, 6.28, False, 'Va_0_8')
Va_0_9 = model.new_var(-6.28, 6.28, False, 'Va_0_9')
Va_0_10 = model.new_var(-6.28, 6.28, False, 'Va_0_10')
Va_0_11 = model.new_var(-6.28, 6.28, False, 'Va_0_11')
Va_0_12 = model.new_var(-6.28, 6.28, False, 'Va_0_12')
Va_0_13 = model.new_var(-6.28, 6.28, False, 'Va_0_13')
Va_0_14 = model.new_var(-6.28, 6.28, False, 'Va_0_14')
Va_0_15 = model.new_var(-6.28, 6.28, False, 'Va_0_15')

ac_flow_0_0 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_0')
ac_flow_0_1 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_1')
ac_flow_0_2 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_2')
ac_flow_0_3 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_3')
ac_flow_0_4 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_4')
ac_flow_0_5 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_5')
ac_flow_0_6 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_6')
ac_flow_0_7 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_7')
ac_flow_0_8 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_8')
ac_flow_0_9 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_9')
ac_flow_0_10 = model.new_var(-2, 2, False, 'ac_flow_0_10')
ac_flow_0_11 = model.new_var(-1, 1, False, 'ac_flow_0_11')
ac_flow_0_12 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_12')
ac_flow_0_13 = model.new_var(-1, 1, False, 'ac_flow_0_13')
ac_flow_0_14 = model.new_var(-0.8, 0.8, False, 'ac_flow_0_14')
ac_flow_0_15 = model.new_var(-0.5, 0.5, False, 'ac_flow_0_15')
ac_flow_0_16 = model.new_var(-0.5, 0.5, False, 'ac_flow_0_16')
ac_flow_0_17 = model.new_var(-0.8, 0.8, False, 'ac_flow_0_17')
ac_flow_0_18 = model.new_var(-0.5, 0.5, False, 'ac_flow_0_18')
ac_flow_0_19 = model.new_var(-0.5, 0.5, False, 'ac_flow_0_19')
ac_flow_0_20 = model.new_var(-1e+20, 1e+20, False, 'ac_flow_0_20')
ac_flow_0_21 = model.new_var(-0.2, 0.2, False, 'ac_flow_0_21')

hvdc_flow_0_0 = model.new_var(-10, 10, False, 'hvdc_flow_0_0')

# Define the objective function
model.minimize(DeltaSL_down_0 + DeltaSL_up_0 + Delta_down_0 - Delta_up_0 + ac_flow_0_16 + ac_flow_0_17 - ac_flow_0_21 - hvdc_flow_0_0)

# Define the constraints

# Deltas equality
model.add(DeltaSL_down_0 - DeltaSL_up_0 - Delta_down_0 + Delta_up_0 == 0)

# AC Flow constraints
model.add(-23.7473284256 * Va_0_3 + 23.7473284256 * Va_0_4 + ac_flow_0_0 == 0)
model.add(5.02765208648 * Va_0_10 - 5.02765208648 * Va_0_5 + ac_flow_0_1 == 0)
model.add(3.90915132325 * Va_0_11 - 3.90915132325 * Va_0_5 + ac_flow_0_2 == 0)
model.add(7.67636447379 * Va_0_12 - 7.67636447379 * Va_0_5 + ac_flow_0_3 == 0)
model.add(-11.8343195266 * Va_0_8 + 11.8343195266 * Va_0_9 + ac_flow_0_4 == 0)
model.add(3.69849840965 * Va_0_13 - 3.69849840965 * Va_0_8 + ac_flow_0_5 == 0)
model.add(5.20643515385 * Va_0_10 - 5.20643515385 * Va_0_9 + ac_flow_0_6 == 0)
model.add(-5.00300180108 * Va_0_11 + 5.00300180108 * Va_0_12 + ac_flow_0_7 == 0)
model.add(-2.87339808057 * Va_0_12 + 2.87339808057 * Va_0_13 + ac_flow_0_8 == 0)
model.add(-1000 * Va_0_15 + 1000 * Va_0_3 + ac_flow_0_9 == 0)
model.add(-16.9004563123 * Va_0_0 + 16.9004563123 * Va_0_1 + ac_flow_0_10 == 0)
model.add(-4.48350071736 * Va_0_0 + 4.48350071736 * Va_0_4 + ac_flow_0_11 == 0)
model.add(-5.0512703945 * Va_0_1 + 5.0512703945 * Va_0_2 + ac_flow_0_12 == 0)
model.add(-5.67150635209 * Va_0_1 + 5.67150635209 * Va_0_3 + ac_flow_0_13 == 0)
model.add(-5.75109270761 * Va_0_1 + 5.75109270761 * Va_0_4 + ac_flow_0_14 == 0)
model.add(-5.84692743963 * Va_0_2 + 5.84692743963 * Va_0_3 + ac_flow_0_15 == 0)
model.add(-3.96793905246 * Va_0_4 + 3.96793905246 * Va_0_5 + ac_flow_0_17 == 0)
model.add(-5.67697984672 * Va_0_6 + 5.67697984672 * Va_0_7 + ac_flow_0_18 == 0)
model.add(-9.09008271975 * Va_0_6 + 9.09008271975 * Va_0_8 + ac_flow_0_19 == 0)
model.add(-200 * Va_0_14 + 200 * Va_0_4 + ac_flow_0_20 == 0)

# Fixed AC Flow
model.add(-1.79797907152 * Va_0_3 + 1.79797907152 * Va_0_8 + ac_flow_0_16 == 0.106620158941)
model.add(4.78194338179 * Va_0_15 - 4.78194338179 * Va_0_6 + ac_flow_0_21 == -0.23909716909)

# Kirchhoff constraints
model.add(-0.333333 * Delta_down_0 - ac_flow_0_10 - ac_flow_0_11 == -0.592887637492)
model.add(-0.333333 * Delta_down_0 + ac_flow_0_10 - ac_flow_0_12 - ac_flow_0_13 - ac_flow_0_14 == -0.375887637492)

# More Kirchhoff constraints...
# params = """
# primal_residual_tolerance = 1e-8
# primal_feasibility_tolerance = 1e-8
# dual_feasibility_tolerance = 1e-8
# mip_abs_gap = 1e-8
# time_limit = 60000
# """
# # Build solver with Highs solver
solver = model_builder.Solver('Highs')

# Set the solver parameters
# solver.set_solver_specific_parameters(params)

status = solver.solve(model)

print("status:", status)

# Check if an optimal solution is found
if status == SolveStatus.OPTIMAL:

    print('Solution found:')
    for variable in model.get_variables():
        print(f'{variable.name} = {solver.value(variable)}')

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
