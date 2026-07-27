# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
from typing import Optional

from VeraGridEngine.basic_structures import IntVec


class CandidateGenerationOptions:
    """
    Options for the candidate-investment generator.
    """

    def __init__(self,
                 top_n_corridors: int = 5,
                 base_overload_threshold: float = 1.0,
                 n1_overload_threshold: float = 1.0,
                 ptdf_threshold: float = 1e-4,
                 verify_top_k: int = 1,
                 use_time_series: bool = False,
                 time_indices: Optional[IntVec] = None):
        """
        :param top_n_corridors: Number of nearby-substation corridors enumerated as new-line
                                candidates for each flagged violation (in addition to the parallel
                                duplicate of the overloaded branch itself).
        :param base_overload_threshold: Base-case loading fraction above which a branch is flagged
                                        (1.0 = 100% of ``rate``).
        :param n1_overload_threshold: N-1 loading fraction above which a branch is flagged
                                      (1.0 = 100% of ``rate * contingency_factor``).
        :param ptdf_threshold: Sensitivities with absolute value below this are treated as zero.
        :param verify_top_k: Number of top-ranked candidates to verify with a fresh AC power flow
                             plus N-1 screening (step 5).
        :param use_time_series: If True, scan ``time_indices`` for the most critical snapshot
                                (most base-case branch overloads plus bus voltage violations) and
                                run the whole pipeline at that snapshot instead of today's grid
                                state.
        :param time_indices: Time steps to scan when ``use_time_series`` is True. ``None`` means
                             every time step in the grid (``grid.get_all_time_indices()``).
        """
        self.top_n_corridors: int = int(top_n_corridors)
        self.base_overload_threshold: float = float(base_overload_threshold)
        self.n1_overload_threshold: float = float(n1_overload_threshold)
        self.ptdf_threshold: float = float(ptdf_threshold)
        self.verify_top_k: int = int(verify_top_k)
        self.use_time_series: bool = bool(use_time_series)
        self.time_indices: Optional[IntVec] = time_indices
