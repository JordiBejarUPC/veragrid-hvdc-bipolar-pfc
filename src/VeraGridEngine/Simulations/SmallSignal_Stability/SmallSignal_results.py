# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from typing import Union
import matplotlib.colors as plt_colors
from typing import List, Tuple, Dict

from VeraGridEngine.Devices.Parents.physical_device import PhysicalDevice
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.DataStructures.numerical_circuit import NumericalCircuit
from VeraGridEngine.basic_structures import IntVec, Vec, StrVec, CxVec, ConvergenceReport, Logger, DateVec, Mat
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var

class SmallSignal_Stability_Results(ResultsTemplate):

    def __init__(self,
                 stability: str,
                 Eigenvalues: np.ndarray,
                 PF: np.ndarray,
                 stat_vars: List[Var],
                 vars2device: Dict[int, PhysicalDevice],
                 ):
        ResultsTemplate.__init__(
            self,
            name='Small Signal Stability',
            available_results=[ResultTypes.Eigenvalues,
                               ResultTypes.ParticipationFactors
                               ],
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.SmallSignalStability
        )
        stat_vars_names = [str(var) + vars2device[var.uid].name for var in stat_vars]

        self.stat_vars_array = np.array(stat_vars_names, dtype=np.str_)

        self.stability = stability
        self.eigenvalues = Eigenvalues
        self.participation_factors = PF
        # self.register(name='Stability', tpe=Vec)
        self.register(name='eigenvalues', tpe=Vec)
        self.register(name='participation_factors', tpe=Vec)

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Export the results as a ResultsTable for plotting.
        """
        if result_type == ResultTypes.ParticipationFactors:

            return ResultsTable(
                data=self.participation_factors,
                index=np.array(self.stat_vars_array.astype(str), dtype=np.str_),
                columns=np.array(self.eigenvalues.astype(str), dtype=np.str_), #
                title="Participation factors for each eigenvalue",
                idx_device_type=DeviceType.NoDevice,
                cols_device_type=DeviceType.NoDevice
            )

        elif result_type == ResultTypes.Eigenvalues:
            print("eigenvals:",self.eigenvalues )
            print("np.array([]):", np.array(["-"]))
            print("np.array([self.eigenvalues*0]:", np.array([self.eigenvalues*0]))
            print("np.empty(len(self.eigenvalues)):", np.empty(len(self.eigenvalues)))
            return ResultsTable(
                data=self.eigenvalues,
                index= np.empty(len(self.eigenvalues)),
                columns= np.array(["-"]),
                title="Eigenvalues",
                idx_device_type=DeviceType.NoDevice,
                cols_device_type=DeviceType.NoDevice
            )
        else:
            raise Exception(f"Result type not understood: {result_type}")

    def plot(self, fig, ax):
        """
        Plot the S-Domain modes plot
        :param fig: Matplotlib figure. If None, one will be created
        :param ax: Matplotlib Axis. If None, one will be created
        """
        if ax is None:
            fig = plt.figure(figsize=(8, 7))
            ax = fig.add_subplot(111)

        x = self.eigenvalues.real
        y = self.eigenvalues.imag

        ax.scatter(x, y, 'k', linewidth=2)

        ax.set_title(r'$S-Domain$ plot')
        ax.set_xlabel(r'$Imaginary [s^{-1}]$')
        ax.set_ylabel(r'$Real [s^{-1}]$')