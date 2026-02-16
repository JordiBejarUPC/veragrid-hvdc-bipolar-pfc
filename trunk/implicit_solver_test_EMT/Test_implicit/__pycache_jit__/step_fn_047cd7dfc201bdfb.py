import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def step_fn(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(20, dtype=np.float64)
    residuals[0] = ((2.0/h) * (states[0] - history[0]) - d_history[0]) - states[1]
    residuals[1] = ((2.0/h) * (states[1] - history[1]) - d_history[1]) - states[0] * 0 + params[0] * (states[2] - states[0])
    residuals[2] = ((2.0/h) * (states[2] - history[2]) - d_history[2]) - states[3]
    residuals[3] = ((2.0/h) * (states[3] - history[3]) - d_history[3]) - states[2] * 0 + params[0] * (states[0] - states[2]) + params[0] * (states[4] - states[2])
    residuals[4] = ((2.0/h) * (states[4] - history[4]) - d_history[4]) - states[5]
    residuals[5] = ((2.0/h) * (states[5] - history[5]) - d_history[5]) - states[4] * 0 + params[0] * (states[2] - states[4]) + params[0] * (states[6] - states[4])
    residuals[6] = ((2.0/h) * (states[6] - history[6]) - d_history[6]) - states[7]
    residuals[7] = ((2.0/h) * (states[7] - history[7]) - d_history[7]) - states[6] * 0 + params[0] * (states[4] - states[6]) + params[0] * (states[8] - states[6])
    residuals[8] = ((2.0/h) * (states[8] - history[8]) - d_history[8]) - states[9]
    residuals[9] = ((2.0/h) * (states[9] - history[9]) - d_history[9]) - states[8] * 0 + params[0] * (states[6] - states[8]) + params[0] * (states[10] - states[8])
    residuals[10] = ((2.0/h) * (states[10] - history[10]) - d_history[10]) - states[11]
    residuals[11] = ((2.0/h) * (states[11] - history[11]) - d_history[11]) - states[10] * 0 + params[0] * (states[8] - states[10]) + params[0] * (states[12] - states[10])
    residuals[12] = ((2.0/h) * (states[12] - history[12]) - d_history[12]) - states[13]
    residuals[13] = ((2.0/h) * (states[13] - history[13]) - d_history[13]) - states[12] * 0 + params[0] * (states[10] - states[12]) + params[0] * (states[14] - states[12])
    residuals[14] = ((2.0/h) * (states[14] - history[14]) - d_history[14]) - states[15]
    residuals[15] = ((2.0/h) * (states[15] - history[15]) - d_history[15]) - states[14] * 0 + params[0] * (states[12] - states[14]) + params[0] * (states[16] - states[14])
    residuals[16] = ((2.0/h) * (states[16] - history[16]) - d_history[16]) - states[17]
    residuals[17] = ((2.0/h) * (states[17] - history[17]) - d_history[17]) - states[16] * 0 + params[0] * (states[14] - states[16]) + params[0] * (states[18] - states[16])
    residuals[18] = ((2.0/h) * (states[18] - history[18]) - d_history[18]) - states[19]
    residuals[19] = ((2.0/h) * (states[19] - history[19]) - d_history[19]) - states[18] * 0 + params[0] * (states[16] - states[18])
    return residuals