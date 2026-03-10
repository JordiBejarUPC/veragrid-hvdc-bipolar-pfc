import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jit_step_be_part_0(states, params, history, d_history, h, residuals, history2=None):
    residuals[0] = ((states[0] - history[0]) / h) - -params[2] * states[0]