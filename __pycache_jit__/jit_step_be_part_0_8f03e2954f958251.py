import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jit_step_be_part_0(states, params, history, d_history, h, residuals, history2=None):
    residuals[0] = ((states[0] - history[0]) / h) - states[1]
    residuals[1] = ((states[1] - history[1]) / h) - -states[0]