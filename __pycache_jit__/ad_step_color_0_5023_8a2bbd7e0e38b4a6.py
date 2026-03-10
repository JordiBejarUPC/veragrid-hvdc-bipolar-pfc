import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def ad_step_color_0_5023(states, seeds, params, history, d_history, h, history2=None):
    jvp = np.zeros(1, dtype=np.float64)
    jvp[0] = (2.0/h)
    return jvp