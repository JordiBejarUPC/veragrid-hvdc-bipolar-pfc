import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def generator_step_fn(states, params, history, d_history, h, history2=None):
    _t0 = np.cos(states[4] - 2.0943951023931953)
    _t1 = np.cos(states[4] + 2.0943951023931953)
    _t2 = np.sin(states[4] + 2.0943951023931953)
    _t3 = np.sin(states[4] - 2.0943951023931953)
    _t4 = np.sin(states[4])
    _t5 = np.cos(states[4])
    residuals = np.zeros(23, dtype=np.float64)
    residuals[0] = states[11] - params[10] * states[7] - states[5] * states[1]
    residuals[1] = states[12] - params[10] * states[8] + states[5] * states[0]
    residuals[2] = states[13] - params[9] * states[10]
    residuals[3] = states[21] - params[11] * states[9]
    residuals[4] = params[12] * states[5]
    residuals[5] = (states[20] - states[17] - params[0] * (states[5] - params[13])) / 2 * params[1]
    residuals[6] = params[12] * (params[13] - states[5])
    residuals[7] = states[0] - (params[7] + params[5]) * states[7] + params[7] * states[9]
    residuals[8] = states[1] - (params[8] + params[5]) * states[8]
    residuals[9] = states[3] - params[7] * states[7] + (params[7] + params[6]) * states[9]
    residuals[10] = states[2] - params[4] * states[10]
    residuals[11] = states[11] - 0.6666666666666666 * (params[14] * _t5 + params[15] * _t0 + params[16] * _t1)
    residuals[12] = states[12] - 0.6666666666666666 * (params[14] * _t4 + params[15] * _t3 + params[16] * _t2)
    residuals[13] = states[13] - 0.6666666666666666 * (params[14] * 0.5 + params[15] * 0.5 + params[16] * 0.5)
    residuals[14] = states[14] - states[7] * _t5 + states[8] * _t4 + states[10]
    residuals[15] = states[15] - states[7] * _t0 + states[8] * _t3 + states[10]
    residuals[16] = states[16] - states[7] * _t1 + states[8] * _t2 + states[10]
    residuals[17] = states[17] + 1.5 * (states[0] * states[8] - states[1] * states[7])
    residuals[18] = states[18] - states[14] * params[14] + states[15] * params[15] + states[16] * params[16]
    residuals[19] = states[19] - 0.5773502691896258 * ((params[14] - params[15]) * states[16] + (params[15] - params[16]) * states[14] + (params[16] - params[14]) * states[15])
    residuals[20] = states[20] - states[17] + params[3] * (params[13] - states[5]) + params[2] * states[6]
    residuals[21] = states[21] - params[17]
    residuals[22] = states[22] - states[18]
    return residuals