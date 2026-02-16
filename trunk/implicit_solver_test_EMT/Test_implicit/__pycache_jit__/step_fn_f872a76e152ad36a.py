import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def step_fn(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(10, dtype=np.float64)
    residuals[0] = ((2.0/h) * (states[0] - history[0]) - d_history[0]) - states[1]
    residuals[1] = ((2.0/h) * (states[1] - history[1]) - d_history[1]) - states[0] * 0 + params[0] * (states[2] - states[0])
    residuals[2] = ((2.0/h) * (states[2] - history[2]) - d_history[2]) - states[3]
    residuals[3] = ((2.0/h) * (states[3] - history[3]) - d_history[3]) - states[2] * 0 + params[0] * (states[0] - states[2]) + params[0] * (states[4] - states[2])
    residuals[4] = ((2.0/h) * (states[4] - history[4]) - d_history[4]) - states[5]
    residuals[5] = ((2.0/h) * (states[5] - history[5]) - d_history[5]) - states[4] * 0 + params[0] * (states[2] - states[4]) + params[0] * (states[6] - states[4])
    residuals[6] = ((2.0/h) * (states[6] - history[6]) - d_history[6]) - states[7]
    residuals[7] = ((2.0/h) * (states[7] - history[7]) - d_history[7]) - states[6] * 0 + params[0] * (states[4] - states[6]) + params[0] * (states[8] - states[6])
    residuals[8] = ((2.0/h) * (states[8] - history[8]) - d_history[8]) - states[9]
    residuals[9] = ((2.0/h) * (states[9] - history[9]) - d_history[9]) - states[8] * 0 + params[0] * (states[6] - states[8])
    return residuals