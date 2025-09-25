# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import pdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.linalg

#Eigenvalues = [2,3,4,5,6,7,8]
#df_Eig = pd.DataFrame(Eigenvalues)
#df_Eig.to_csv("Eigenvalues_results.csv", index=False)


def Andes_vs_Veragrid_stability(eigV, eigA):
    VeraGrid_Eig = np.genfromtxt(eigV, delimiter=",", dtype=complex)
    Andes_Eig = np.genfromtxt(eigA, delimiter=",", dtype=complex)

    VeraGrid_Eig_ord = VeraGrid_Eig[np.argsort(-np.abs(VeraGrid_Eig))]
    Andes_Eig_ord = Andes_Eig[np.argsort(-np.abs(Andes_Eig))]

    #print("vera eig:", VeraGrid_Eig_ord)
    #print("andes eig:", Andes_Eig_ord)

    print("vera eig ord:", VeraGrid_Eig_ord)
    print("andes eig ord:", Andes_Eig_ord)
    print("vera eig ord abs:", np.abs(VeraGrid_Eig_ord))
    print("andes eig ord abs:", np.abs(Andes_Eig_ord))

    rel_err = np.ndarray(VeraGrid_Eig_ord.shape)
    for i in range(len(Andes_Eig_ord)):
        if np.abs(Andes_Eig_ord[i]) <= 1e-10:
            rel_err[i] = float('inf')
        else:
            rel_err[i] = np.where(np.abs(Andes_Eig_ord[i]) != 0,
                               np.abs(np.abs(Andes_Eig_ord[i]) - np.abs(VeraGrid_Eig_ord[i])) * 100 / np.abs(Andes_Eig_ord[i]),
                               0)

    """
    rel_err = np.zeros_like(VeraGrid_Eig_ord).real.astype(float)
    print("re rel err", rel_err)
    
    """

    print("Relative error [%]:",rel_err)


    #S-domain plot
    x1 = VeraGrid_Eig_ord.real
    y1 = VeraGrid_Eig_ord.imag
    x2= Andes_Eig_ord.real
    y2 = Andes_Eig_ord.imag

    plt.scatter(x2, y2, marker='o', color='orange', label='Andes')
    plt.scatter(x1, y1, marker='x', color='blue', label='VeraGrid')
    plt.xlabel("Re [s -1]")
    plt.ylabel("Im [s -1]")
    plt.title("Stability plot")
    # plt.xlim([-5, 5])
    # plt.ylim([-5, 5])
    plt.axhline(0, color='black', linewidth=1)  # eje horizontal (y = 0)
    plt.axvline(0, color='black', linewidth=1)
    # plt.grid(True)
    plt.legend(loc='upper left', ncol=2)
    plt.tight_layout()
    plt.show()

Andes_vs_Veragrid_stability("Eigenvalues_results.csv", "Eigenvalues_results_Andes.csv")

