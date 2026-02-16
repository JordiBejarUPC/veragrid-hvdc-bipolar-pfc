import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def ad_step_color_1_3716(states, seeds, params, history, d_history, h, history2=None):
    jvp = np.zeros(2, dtype=np.float64)
    jvp[0] = (-(((-1.0))) / (params[4]))
    jvp[1] = ((2.0/h) - (((-(1.0) / (params[3])))) / (params[5]))
    return jvp