import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jac_eval_be_dense(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(4, dtype=np.float64)
    residuals[0] = params[2]
    residuals[1] = -1
    residuals[2] = 1
    residuals[3] = params[2]
    return residuals