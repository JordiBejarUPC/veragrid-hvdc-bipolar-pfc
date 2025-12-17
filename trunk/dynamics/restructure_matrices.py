# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0


import time
from andes.io.json import write
#import matplotlib
import pandas as pd
import numpy as np
#matplotlib.use('TkAgg')  # or 'QtAgg', depending on your system
from andes.utils.paths import list_cases, get_case


def restructure_matrices(fx, fy, gx, gy, A, pfact, fxA, fyA, gxA, gyA,  A_A, p_fact_A ):
    """
    Restructure matrices in order to be able to compare the jacobian and A matrix between VeraGrid and Andes
    """
    V_fx = np.genfromtxt(fx, delimiter=",", dtype=complex)
    A_fx = np.genfromtxt(fxA, delimiter=",", dtype=complex)
    V_fy = np.genfromtxt(fy, delimiter=",", dtype=complex)
    A_fy = np.genfromtxt(fyA, delimiter=",", dtype=complex)
    V_gx = np.genfromtxt(gx, delimiter=",", dtype=complex)
    A_gx = np.genfromtxt(gxA, delimiter=",", dtype=complex)
    V_gy = np.genfromtxt(gy, delimiter=",", dtype=complex)
    A_gy = np.genfromtxt(gyA, delimiter=",", dtype=complex)
    V_A = np.genfromtxt(A, delimiter=",", dtype=complex)
    A_A = np.genfromtxt(A_A, delimiter=",", dtype=complex)
    V_pfact = np.genfromtxt(pfact, delimiter=",", dtype=complex)
    A_pfact = np.genfromtxt(p_fact_A, delimiter=",", dtype=complex)


    # reorder cols Veragrid
    # KUNDUR
    order_cols_fx_V = [0, 2, 4, 6, 1, 3, 5, 7]
    order_cols_fy_V = [1,3,5,7,9,11,13,15,17,19,21,0,2,4,6,8,10,12,14,16,18,20,98,109,120,131,99,110,121,132,96,107,118,129,97,108,119,130,102,113,124,135,94,105,
                        116,127,95,106,117,128,100,111,122,133,101,112,123,134,103,114,125,136,104,115,126,137,138,139,140,141,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,
                        38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,
                        89,90,91,92,93]
    order_cols_gx_V = [0, 2, 4, 6, 1, 3, 5, 7]
    order_cols_gy_V = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 98, 109, 120, 131,
                     99, 110, 121, 132, 96, 107, 118, 129, 97, 108, 119, 130, 102, 113, 124, 135, 94, 105,
                     116, 127, 95, 106, 117, 128, 100, 111, 122, 133, 101, 112, 123, 134, 103, 114, 125, 136, 104, 115,
                     126, 137, 138, 139, 140, 141, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37,
                     38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62,
                     63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87,
                     88,89, 90, 91, 92, 93]
    order_cols_A_V = [0, 2, 4, 6, 1, 3, 5, 7]

    # SIMPLE SYSTEM
    # order_cols_fx_V = [0, 1]
    # order_cols_gx_V = [0, 1]
    # order_cols_A_V = [0, 1]

    # syst0: gen-trafo-load
    # order_cols_fy_V = [1,3,0,2,12,13,10,11,16,8,9,14,15,17,18,19,20,4,5,6,7]
    # order_cols_gy_V = [1,3,0,2,12,13,10,11,16,8,9,14,15,17,18,19,20,4,5,6,7]

    # syst1: gen-trafo-line-load
    # order_cols_fy_V = [1, 3, 5, 0, 2, 4, 18, 19, 16, 17, 22, 14, 15, 20, 21, 23, 24, 25, 26, 6, 7, 8, 9, 10, 11, 12, 13]
    # order_cols_gy_V = [1, 3, 5, 0, 2, 4, 18, 19, 16, 17, 22, 14, 15, 20, 21, 23, 24, 25, 26, 6, 7, 8, 9, 10, 11, 12, 13]

    # syst2: gen-trafo-double equal paralel line-load
    # order_cols_fy_V = [1,3,5,0,2,4,22,23,20,21,26,18,19,24,25,27,28,29,30,14,15,16,17,6,7,8,9,10,11,12,13]
    # order_cols_gy_V = [1,3,5,0,2,4,22,23,20,21,26,18,19,24,25,27,28,29,30,14,15,16,17,6,7,8,9,10,11,12,13]

    #syst3: 2 GEN(1 at bus 1, 1 at bus 3 that connects to bus2 by line 3), 1 TRAFO, 1 LINE, 1 LOAD
    # order_cols_fx_V = [0, 2, 1, 3]
    # order_cols_gx_V = [0, 2, 1, 3]
    # order_cols_A_V = [0, 2, 1, 3]
    # order_cols_fy_V = [1,3,5,7,0,2,4,6,24,25,22,23,28,20,21,26,27,35,36,33,34,39,31,32,37,38,29,30,40,41,16,17,18,19,
    #                    8,9,10,11,12,13,14,15,42,43]
    # order_cols_gy_V = [1,3,5,7,0,2,4,6,24,25,22,23,28,20,21,26,27,35,36,33,34,39,31,32,37,38,29,30,40,41,16,17,18,19,
    #                    8,9,10,11,12,13,14,15,42,43]


    V_fx_rc = V_fx[:,order_cols_fx_V]
    V_fy_rc = V_fy[:,order_cols_fy_V]
    V_gx_rc = V_gx[:,order_cols_gx_V]
    V_gy_rc = V_gy[:,order_cols_gy_V]
    V_A_rc = V_A[:, order_cols_A_V]



    # reorder rows Veragrid
    # kundur
    order_rows_fx_V = [0, 2, 4, 6, 1, 3, 5, 7]
    order_rows_fy_V = [0, 2, 4, 6, 1, 3, 5, 7]
    order_rows_gx_V = [1,3,5,7,9,11,13,15,17,19,21,0,2,4,6,8,10,12,14,16,18,20,96,107,118,129,97,108,119,130,98,109,120,131,99,110,121,132,100,111,122,133,101,112,123,134,102,
                       113,124,135,94,105,116,127,95,106,117,128,104,115,126,137,103,114,125,136,138,139,140,141,22,23,24,25,26,27,28,29,30,31,32,33,34,35,
                       36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,
                       68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93]
    order_rows_gy_V = [1,3,5,7,9,11,13,15,17,19,21,0,2,4,6,8,10,12,14,16,18,20,96,107,118,129,97,108,119,130,98,109,120,131,99,110,121,132,100,111,122,133,101,112,123,134,102,
                       113,124,135,94,105,116,127,95,106,117,128,104,115,126,137,103,114,125,136,138,139,140,141,22,23,24,25,26,27,28,29,30,31,32,33,34,35,
                       36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,
                       68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93]
    order_rows_A_V = [0, 2, 4, 6, 1, 3, 5, 7]
    order_rows_pfact_V = [0, 2, 4, 6, 1, 3, 5, 7]

    # simple system
    # order_rows_fx_V = [0, 1]
    # order_rows_fy_V = [0, 1]
    # order_rows_A_V = [0, 1]
    # order_rows_pfact_V = [0, 1]

    #syst0: gen-trafo-load
    # order_rows_gx_V = [1,3,0,2,10,11,12,13,14,15,16,8,9,18,17,19,20,4,5,6,7]
    # order_rows_gy_V = [1,3,0,2,10,11,12,13,14,15,16,8,9,18,17,19,20,4,5,6,7]

    #syst1: gen-trafo-line-load
    # order_rows_gx_V = [1,3,5,0,2,4,16,17,18,19,20,21,22,14,15,23,24,25,26,6,7,8,9,10,11,12,13]
    # order_rows_gy_V = [1,3,5,0,2,4,16,17,18,19,20,21,22,14,15,23,24,25,26,6,7,8,9,10,11,12,13]

    # syst2: gen-trafo-double equal paralel line-load
    # order_rows_gx_V = [1,3,5,0,2,4,20,21,22,23,24,25,26,18,19,27,28,29,30,14,15,16,17,6,7,8,9,10,11,12,13]
    # order_rows_gy_V = [1,3,5,0,2,4,20,21,22,23,24,25,26,18,19,27,28,29,30,14,15,16,17,6,7,8,9,10,11,12,13]

    # syst3: 2 GEN(1 at bus 1, 1 at bus 3 that connects to bus2 by line 3), 1 TRAFO, 1 LINE, 1 LOAD
    # order_rows_fx_V = [0, 2, 1, 3]
    # order_rows_fy_V = [0, 2, 1, 3]
    # order_rows_A_V = [0, 2, 1, 3]
    # order_rows_pfact_V = [0, 2, 1, 3]
    # order_rows_gx_V = [1,3,5,7,0,2,4,6,22,23,24,25,26,27,28,20,21,33,34,35,36,37,38,39,31,32,29,30,40,41,16,17,18,19,
    #                    8,9,10,11,12,13,14,15,42,43]
    # order_rows_gy_V = [1,3,5,7,0,2,4,6,22,23,24,25,26,27,28,20,21,33,34,35,36,37,38,39,31,32,29,30,40,41,16,17,18,19,
    #                    8,9,10,11,12,13,14,15,42,43]

    V_fx_r = V_fx_rc[order_rows_fx_V, :]
    V_fy_r = V_fy_rc[order_rows_fy_V, :]
    V_gx_r = V_gx_rc[order_rows_gx_V, :]
    V_gy_r = V_gy_rc[order_rows_gy_V, :]
    V_A_r = V_A_rc[order_rows_A_V, :]
    V_pfact_r = V_pfact[order_rows_pfact_V, :]


    #reorder cols Andes
    #kundur
    order_cols_fx_A =  [0,1,2,3,4,5,6,7]
    order_cols_fy_A = [0,1, 2, 3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,27,28,29,30,31,32,33,34,35,36,37,38,
                       39,40,41,42,47,48,49,50,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,22,23,24,25,26,43,44,45,
                       46,51,52,53,54,55,56,57,58]
    order_cols_gx_A = [0, 1, 2, 3, 4, 5, 6, 7]
    order_cols_gy_A = [0,1, 2, 3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,27,28,29,30,31,32,33,34,35,36,37,38,
                       39,40,41,42,47,48,49,50,59,60,61,62,63,64,65,66,67,68,69,70,71,72,73,74,22,23,24,25,26,43,44,45,
                       46,51,52,53,54,55,56,57,58]
    order_cols_A_A = [0, 1, 2, 3, 4, 5, 6, 7]

    #simple system
    # order_cols_fx_A = [0, 1]
    # order_cols_gx_A = [0, 1]
    # order_cols_A_A = [0, 1]

    # syst0: gen-trafo-load
    # order_cols_fy_A = [0, 1, 2, 3, 6, 7, 8, 9, 11, 14, 15, 16, 17, 4, 5, 10, 12, 13]
    # order_cols_gy_A = [0, 1, 2, 3, 6, 7, 8, 9, 11, 14, 15, 16, 17, 4, 5, 10, 12, 13]

    # syst1: gen-trafo-line-load
    # order_cols_fy_A = [0,1,2,3,4,5,8,9,10,11,13,16,17,18,19,6,7,12,14,15]
    # order_cols_gy_A = [0,1,2,3,4,5,8,9,10,11,13,16,17,18,19,6,7,12,14,15]

    # syst2: gen-trafo-double equal paralel line-load
    # order_cols_fy_A = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 13, 16, 17, 18, 19, 6, 7, 12, 14, 15]
    # order_cols_gy_A = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 13, 16, 17, 18, 19, 6, 7, 12, 14, 15]

    # syst3: 2 GEN(1 at bus 1, 1 at bus 3 that connects to bus2 by line 3), 1 TRAFO, 1 LINE, 1 LOAD
    # order_cols_fx_A = [0, 1, 2, 3]
    # order_cols_gx_A = [0, 1, 2, 3]
    # order_cols_A_A = [0, 1, 2, 3]
    # order_cols_fy_A = [0,1,2,3,4,5,6,7,11,13,15,17,21,27,29,31,33,12,14,16,18,22,28,30,32,34,19,23,25,20,24,26,8,9,10]
    # order_cols_gy_A = [0,1,2,3,4,5,6,7,11,13,15,17,21,27,29,31,33,12,14,16,18,22,28,30,32,34,19,23,25,20,24,26,8,9,10]


    A_fx_rc = A_fx[:, order_cols_fx_A]
    A_fy_rc = A_fy[:, order_cols_fy_A]
    A_gx_rc = A_gx[:, order_cols_gx_A]
    A_gy_rc = A_gy[:, order_cols_gy_A]
    A_A_rc = A_A[:, order_cols_A_A]

    # reorder rows Andes
    #kundur
    order_rows_fx_A = [0, 1, 2, 3, 4, 5, 6, 7]
    order_rows_fy_A = [0, 1, 2, 3, 4, 5, 6, 7]
    order_rows_gx_A = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 27, 28, 29, 30, 31,
                       32, 33, 34, 35, 36, 37, 38,
                       39, 40, 41, 42, 47, 48, 49, 50, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74,
                       22, 23, 24, 25, 26, 43, 44, 45,
                       46, 51, 52, 53, 54, 55, 56, 57, 58]
    order_rows_gy_A = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 27, 28, 29, 30, 31,
                       32, 33, 34, 35, 36, 37, 38,
                       39, 40, 41, 42, 47, 48, 49, 50, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74,
                       22, 23, 24, 25, 26, 43, 44, 45,
                       46, 51, 52, 53, 54, 55, 56, 57, 58]
    order_rows_A_A = [0, 1, 2, 3, 4, 5, 6, 7]
    order_rows_pfact_A = [0, 1, 2, 3, 4, 5, 6, 7]

    # simple system
    # order_rows_fx_A = [0, 1]
    # order_rows_fy_A = [0, 1]
    # order_rows_A_A = [0, 1]
    # order_rows_pfact_A = [0, 1]

    # syst0: gen-trafo-load
    # order_rows_gx_A = [0, 1, 2, 3, 6, 7, 8, 9, 11, 14, 15, 16, 17, 4, 5, 10, 12, 13]
    # order_rows_gy_A = [0, 1, 2, 3, 6, 7, 8, 9, 11, 14, 15, 16, 17, 4, 5, 10, 12, 13]

    # syst1: gen-trafo-line-load
    # order_rows_gx_A = [0,1,2,3,4,5,8,9,10,11,13,16,17,18,19,6,7,12,14,15]
    # order_rows_gy_A = [0,1,2,3,4,5,8,9,10,11,13,16,17,18,19,6,7,12,14,15]


    # syst2: gen-trafo-double equal paralel line-load
    # order_rows_gx_A = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 13, 16, 17, 18, 19, 6, 7, 12, 14, 15]
    # order_rows_gy_A = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 13, 16, 17, 18, 19, 6, 7, 12, 14, 15]

    # syst3: 2 GEN(1 at bus 1, 1 at bus 3 that connects to bus2 by line 3), 1 TRAFO, 1 LINE, 1 LOAD
    # order_rows_fx_A = [0, 1, 2, 3]
    # order_rows_fy_A = [0, 1, 2, 3]
    # order_rows_A_A = [0, 1, 2, 3]
    # order_rows_pfact_A = [0, 1, 2, 3]
    # order_rows_gx_A = [0,1,2,3,4,5,6,7,11,13,15,17,21,27,29,31,33,12,14,16,18,22,28,30,32,34,19,23,25,20,24,26,8,9,10]
    # order_rows_gy_A = [0,1,2,3,4,5,6,7,11,13,15,17,21,27,29,31,33,12,14,16,18,22,28,30,32,34,19,23,25,20,24,26,8,9,10]


    A_fx_r = A_fx_rc[order_rows_fx_A, :]
    A_fy_r = A_fy_rc[order_rows_fy_A, :]
    A_gx_r = A_gx_rc[order_rows_gx_A, :]
    A_gy_r = A_gy_rc[order_rows_gy_A, :]
    A_A_r = A_A_rc[order_rows_A_A, :]
    # A_pfact_r = A_pfact[order_rows_pfact_A, :]


    # safe results VeraGrid
    df_V_fx = pd.DataFrame(V_fx_r)
    df_V_fx.to_csv("fx_results_restructured.csv", index=False, header=False,float_format="%.10f")
    df_V_fy = pd.DataFrame(V_fy_r)
    df_V_fy.to_csv("fy_results_restructured.csv", index=False, header=False,float_format="%.10f")
    df_V_gx = pd.DataFrame(V_gx_r)
    df_V_gx.to_csv("gx_results_restructured.csv", index=False, header=False,float_format="%.10f")
    df_V_gy = pd.DataFrame(V_gy_r)
    df_V_gy.to_csv("gy_results_restructured.csv", index=False, header=False,float_format="%.10f")
    df_V_A = pd.DataFrame(V_A_r)
    df_V_A.to_csv("A_results_restructured.csv", index=False, header=False, float_format="%.10f")
    df_V_pfact = pd.DataFrame(V_pfact_r)
    df_V_pfact.to_csv("pfactors_results_restructured.csv", index=False, header=False, float_format="%.10f")

    # Safe results Andes
    df_A_fx = pd.DataFrame(A_fx_r)
    df_A_fx.to_csv("fx_results_restructured_Andes.csv", index=False, header=False,float_format="%.10f")
    df_A_fy = pd.DataFrame(A_fy_r)
    df_A_fy.to_csv("fy_results_restructured_Andes.csv", index=False, header=False,float_format="%.10f")
    df_A_gx = pd.DataFrame(A_gx_r)
    df_A_gx.to_csv("gx_results_restructured_Andes.csv", index=False, header=False,float_format="%.10f")
    df_A_gy = pd.DataFrame(A_gy_r)
    df_A_gy.to_csv("gy_results_restructured_Andes.csv", index=False, header=False,float_format="%.10f")
    df_A_A = pd.DataFrame(A_A_r)
    df_A_A.to_csv("A_results_restructured_Andes.csv", index=False, header=False, float_format="%.10f")
    # df_A_pfact = pd.DataFrame(A_pfact_r)
    # df_A_pfact.to_csv("pfactors_results_restructured_Andes.csv", index=False, header=False, float_format="%.10f")

if __name__ == '__main__':
    _ =  restructure_matrices('fx_results.csv', 'fy_results.csv', 'gx_results.csv', 'gy_results.csv', 'A_results.csv', 'p_factors_results.csv','fx_results_Andes.csv', 'fy_results_Andes.csv', 'gx_results_Andes.csv', 'gy_results_Andes.csv', 'A_results_Andes.csv', 'pfactors_results.csv' )