# SPDX-License-Identifier: MPL-2.0

import numpy as np
from typing import List

from VeraGridEngine.Simulations.results_template import ResultsTemplate
from VeraGridEngine.Simulations.results_table import ResultsTable
from VeraGridEngine.basic_structures import CxVec, Vec, BoolVec
from VeraGridEngine.enumerations import StudyResultsType, ResultTypes, DeviceType


class EraMatrixPencilResults(ResultsTemplate):
    """
    Container for the supersynchronous and subsynchronous poles
    extracted by the Matrix Pencil Method.
    """
    __slots__ = (
        '_eigenvalues_s',
        '_frequencies_hz',
        '_damping_ratios',
        '_is_stable'
    )

    def __init__(self, eigenvalues_s: CxVec) -> None:
        """
        Initializes the results, pre-calculating engineering metrics
        such as damping and frequency in Hz.
        """
        ResultsTemplate.__init__(
            self,
            name='ERA Matrix Pencil Results',
            available_results=[
                ResultTypes.Modes,
                ResultTypes.SDomainPlotHz
            ],
            time_array=None,
            clustering_results=None,
            study_results_type=StudyResultsType.SmallSignalStability
        )

        self._eigenvalues_s: CxVec = eigenvalues_s

        alpha: Vec = self._eigenvalues_s.real
        beta: Vec = self._eigenvalues_s.imag

        # Calculate damping and frequencies
        self._damping_ratios: Vec = -alpha / np.sqrt(alpha ** 2 + beta ** 2 + 1e-15)
        self._frequencies_hz: Vec = np.abs(beta) / (2.0 * np.pi)
        self._is_stable: BoolVec = alpha < 0.0

        self.register(name='eigenvalues_s', tpe=CxVec)
        self.register(name='frequencies_hz', tpe=Vec)
        self.register(name='damping_ratios', tpe=Vec)

    def get_eigenvalues(self) -> CxVec:
        return self._eigenvalues_s

    def mdl(self, result_type: ResultTypes) -> ResultsTable:
        """
        Exports the processed arrays into a formal VeraGrid ResultsTable.
        """
        if result_type == ResultTypes.Modes:
            n_modes: int = len(self._eigenvalues_s)
            data: np.ndarray = np.c_[
                self._eigenvalues_s.real,
                self._eigenvalues_s.imag,
                self._damping_ratios,
                self._frequencies_hz
            ]

            index_list: List[str] = list()
            for i in range(n_modes):
                index_list.append(f"Pole {i}")

            return ResultsTable(
                data=data,
                index=np.array(index_list, dtype=np.str_),
                columns=np.array(["Real (s)", "Imag (s)", "Damp Ratio", "Freq [Hz]"]),
                title="ERA Identified Modes (S-Domain)",
                idx_device_type=DeviceType.NoDevice,
                cols_device_type=DeviceType.NoDevice
            )
        else:
            return super().mdl(result_type)