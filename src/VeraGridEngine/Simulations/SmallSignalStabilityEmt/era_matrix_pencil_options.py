# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Parents.editable_device import EraSvdSolverType
from typing import Tuple

from VeraGridEngine.Simulations.options_template import OptionsTemplate
from VeraGridEngine.Devices.Parents.editable_device import GCProp


class EraMatrixPencilOptions(OptionsTemplate):
    """
    Configuration options for the Eigensystem Realization Algorithm (ERA)
    and Matrix Pencil methods.

    Designed with strict state protection and getters/setters.
    """
    __slots__ = (
        '_decimation_factor',
        '_svd_solver',
        '_tol_deflation',
        '_max_modes',
        '_t_ringdown',
        '_verbose'
    )

    LOCAL_PROPERTY_DECLARATIONS: Tuple[GCProp, ...] = (
        GCProp(key="decimation_factor", tpe=int),
        GCProp(key="svd_solver", tpe=EraSvdSolverType),
        GCProp(key="tol_deflation", tpe=float),
        GCProp(key="max_modes", tpe=int),
        GCProp(key="t_ringdown", tpe=float),
        GCProp(key="verbose", tpe=int),
    )

    def __init__(self,
                 decimation_factor: int = 1,
                 svd_solver: EraSvdSolverType = EraSvdSolverType.FullSvd,
                 tol_deflation: float = 1e-6,
                 max_modes: int = 50,
                 t_ringdown: float = 0.5,
                 verbose: int = 0) -> None:
        """
        Initializes the ERA options with default values.
        """
        OptionsTemplate.__init__(self, name='EraMatrixPencilOptions')

        self._decimation_factor: int = decimation_factor
        self._svd_solver: EraSvdSolverType = svd_solver
        self._tol_deflation: float = tol_deflation
        self._max_modes: int = max_modes
        self._t_ringdown: float = t_ringdown
        self._verbose: int = verbose

    # --- Getters and Setters ---

    def get_decimation_factor(self) -> int:
        return self._decimation_factor

    def set_decimation_factor(self, value: int) -> None:
        self._decimation_factor = value

    def get_svd_solver(self) -> EraSvdSolverType:
        return self._svd_solver

    def set_svd_solver(self, value: EraSvdSolverType) -> None:
        self._svd_solver = value

    def get_tol_deflation(self) -> float:
        return self._tol_deflation

    def set_tol_deflation(self, value: float) -> None:
        self._tol_deflation = value

    def get_max_modes(self) -> int:
        return self._max_modes

    def set_max_modes(self, value: int) -> None:
        self._max_modes = value

    def get_t_ringdown(self) -> float:
        return self._t_ringdown

    def set_t_ringdown(self, value: float) -> None:
        self._t_ringdown = value

    def get_verbose(self) -> int:
        return self._verbose

    def set_verbose(self, value: int) -> None:
        self._verbose = value