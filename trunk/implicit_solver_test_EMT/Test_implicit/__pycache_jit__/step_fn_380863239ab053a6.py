import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def step_fn(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(40, dtype=np.float64)
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
    residuals[19] = ((2.0/h) * (states[19] - history[19]) - d_history[19]) - states[18] * 0 + params[0] * (states[16] - states[18]) + params[0] * (states[20] - states[18])
    residuals[20] = ((2.0/h) * (states[20] - history[20]) - d_history[20]) - states[21]
    residuals[21] = ((2.0/h) * (states[21] - history[21]) - d_history[21]) - states[20] * 0 + params[0] * (states[18] - states[20]) + params[0] * (states[22] - states[20])
    residuals[22] = ((2.0/h) * (states[22] - history[22]) - d_history[22]) - states[23]
    residuals[23] = ((2.0/h) * (states[23] - history[23]) - d_history[23]) - states[22] * 0 + params[0] * (states[20] - states[22]) + params[0] * (states[24] - states[22])
    residuals[24] = ((2.0/h) * (states[24] - history[24]) - d_history[24]) - states[25]
    residuals[25] = ((2.0/h) * (states[25] - history[25]) - d_history[25]) - states[24] * 0 + params[0] * (states[22] - states[24]) + params[0] * (states[26] - states[24])
    residuals[26] = ((2.0/h) * (states[26] - history[26]) - d_history[26]) - states[27]
    residuals[27] = ((2.0/h) * (states[27] - history[27]) - d_history[27]) - states[26] * 0 + params[0] * (states[24] - states[26]) + params[0] * (states[28] - states[26])
    residuals[28] = ((2.0/h) * (states[28] - history[28]) - d_history[28]) - states[29]
    residuals[29] = ((2.0/h) * (states[29] - history[29]) - d_history[29]) - states[28] * 0 + params[0] * (states[26] - states[28]) + params[0] * (states[30] - states[28])
    residuals[30] = ((2.0/h) * (states[30] - history[30]) - d_history[30]) - states[31]
    residuals[31] = ((2.0/h) * (states[31] - history[31]) - d_history[31]) - states[30] * 0 + params[0] * (states[28] - states[30]) + params[0] * (states[32] - states[30])
    residuals[32] = ((2.0/h) * (states[32] - history[32]) - d_history[32]) - states[33]
    residuals[33] = ((2.0/h) * (states[33] - history[33]) - d_history[33]) - states[32] * 0 + params[0] * (states[30] - states[32]) + params[0] * (states[34] - states[32])
    residuals[34] = ((2.0/h) * (states[34] - history[34]) - d_history[34]) - states[35]
    residuals[35] = ((2.0/h) * (states[35] - history[35]) - d_history[35]) - states[34] * 0 + params[0] * (states[32] - states[34]) + params[0] * (states[36] - states[34])
    residuals[36] = ((2.0/h) * (states[36] - history[36]) - d_history[36]) - states[37]
    residuals[37] = ((2.0/h) * (states[37] - history[37]) - d_history[37]) - states[36] * 0 + params[0] * (states[34] - states[36]) + params[0] * (states[38] - states[36])
    residuals[38] = ((2.0/h) * (states[38] - history[38]) - d_history[38]) - states[39]
    residuals[39] = ((2.0/h) * (states[39] - history[39]) - d_history[39]) - states[38] * 0 + params[0] * (states[36] - states[38])
    return residuals