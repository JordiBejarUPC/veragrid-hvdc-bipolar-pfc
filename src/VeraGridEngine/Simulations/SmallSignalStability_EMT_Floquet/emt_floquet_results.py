# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
from matplotlib import pyplot as plt
from typing import List

from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.basic_structures import Vec, Mat
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var


class EmtFloquetResults(ResultsTemplate):
    """
    EmtFloquetResults
    :param multipliers: Floquet multipliers (eigenvalues of Monodromy Matrix)
    :param right_vecs: Right eigenvectors (columns)
    :param left_vecs: Left eigenvectors from adjoint problem (columns)
    :param period: Cycle period T (s)
    :param stat_vars: List of state variables
    """

    def __init__(self,
                 multipliers: Vec,
                 right_vecs: Mat,
                 left_vecs: Mat,
                 period: float,
                 stat_vars: List[Var]):

        # Correcting the constructor call to match VeraGrid's parent class requirements
        ResultsTemplate.__init__(
            self,
            name='EMT Floquet Stability',
            available_results=[
                ResultTypes.Modes,
                ResultTypes.ParticipationFactors,
                ResultTypes.SDomainPlot,
                ResultTypes.SDomainPlotHz
            ],
            time_array=np.array([]),
            clustering_results=None,
            study_results_type=StudyResultsType.SmallSignalStability
        )

        self.multipliers = multipliers
        self.right_vecs = right_vecs
        self.left_vecs = left_vecs
        self.period = period
        self.stat_vars = stat_vars

        # Map Discrete Multipliers (Z) to Floquet Exponents (S)
        self.eigenvalues = np.log(self.multipliers.astype(complex)) / self.period

        # Periodic averaged modal properties
        alpha = self.eigenvalues.real
        beta = self.eigenvalues.imag
        self.damping_ratios = -alpha / np.sqrt(alpha ** 2 + beta ** 2 + 1e-15)
        self.conjugate_frequencies = np.abs(beta) / (2.0 * np.pi)

        # Internal computation of bi-orthonormal Participation Factors
        self.participation_factors = self._compute_pf()

        stat_names = [f"{v}" for v in stat_vars]
        self.stat_vars_array = np.array(stat_names, dtype=np.str_)

        self.register(name='multipliers', tpe=Vec)
        self.register(name='eigenvalues', tpe=Vec)
        self.register(name='participation_factors', tpe=Mat)

    def _compute_pf(self) -> Mat:
        """
        Calculates bi-orthonormal Participation Factors.
        """
        n_states, n_modes = self.right_vecs.shape
        PF = np.zeros((n_states, n_modes), dtype=np.float64)

        for i in range(n_modes):
            # Normalization: l_i^H * r_i = 1.0
            norm_val = np.dot(self.left_vecs[:, i].conj().T, self.right_vecs[:, i])
            if np.abs(norm_val) > 1e-15:
                l_norm = self.left_vecs[:, i] / norm_val
                # PF_ki = Re(r_ki * l_ik)
                PF[:, i] = np.abs(self.right_vecs[:, i] * l_norm)

        # Mode-wise normalization
        col_sums = np.sum(PF, axis=0)
        mask = col_sums > 1e-15
        PF[:, mask] /= col_sums[mask]
        return PF

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """Export results as ResultsTable for the VeraGrid UI/Engine."""
        if result_type == ResultTypes.ParticipationFactors:
            return ResultsTable(
                data=self.participation_factors,
                index=self.stat_vars_array,
                columns=np.array([f"Mode {i}" for i in range(len(self.multipliers))], dtype=np.str_),
                title="Floquet Participation Factors",
                idx_device_type=DeviceType.NoDevice,
                cols_device_type=DeviceType.NoDevice
            )
        elif result_type == ResultTypes.Modes:
            data = np.c_[self.multipliers.real, self.multipliers.imag, np.abs(self.multipliers),
            self.damping_ratios, self.conjugate_frequencies]
            return ResultsTable(
                data=data,
                index=np.array([f"Mode {i}" for i in range(len(self.multipliers))], dtype=np.str_),
                columns=np.array(["Mu Re", "Mu Im", "|Mu|", "Damp Ratio", "Freq [Hz]"]),
                title="Floquet Stability Multipliers",
                idx_device_type=DeviceType.NoDevice,
                cols_device_type=DeviceType.NoDevice
            )
        elif result_type == ResultTypes.SDomainPlot:
            if self.plotting_allowed():
                plt.figure(figsize=(6, 6))
                th = np.linspace(0, 2 * np.pi, 100)
                plt.plot(np.cos(th), np.sin(th), 'k--', alpha=0.4, label='Unit Circle')
                plt.scatter(self.multipliers.real, self.multipliers.imag, color='red', marker='x', s=80)
                plt.xlabel("Real(mu)")
                plt.ylabel("Imag(mu)")
                plt.axis('equal')
                plt.grid(True)
                plt.title("Floquet Multipliers: Unit Circle Stability")
                plt.show()
            return ResultsTable(data=np.c_[self.multipliers.real, self.multipliers.imag],
                                columns=np.array(['Real', 'Imag']), title="Z-Domain Plot")
        return super().mdl(result_type)

    def report_stability(self):
        """Standard stability report for periodic systems."""
        rho = np.max(np.abs(self.multipliers))
        return f"Spectral Radius rho={rho:.4f}. {'STABLE' if rho <= 1.0001 else 'UNSTABLE'}."