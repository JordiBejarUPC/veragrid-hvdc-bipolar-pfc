"""
Canonical MDHEM API surface for VeraGrid integration.

This module is the stable import point for the MDHEM implementation used by
the case14 and ACTIVSg2000 scripts. Legacy files keep their current names for
compatibility, but new code should import the shared business logic from here.
"""

from __future__ import annotations

from mdhelm_pv_case14_exaple import MDHEMRunResult
from mdhelm_pv_case14_exaple import MDHEMPVMap
from mdhelm_pv_case14_exaple import MultiIndexTable
from mdhelm_pv_case14_exaple import SparseLinearSolver
from mdhelm_pv_case14_exaple import VeraGridCaseData
from mdhelm_pv_case14_exaple import build_mdhelm_map_from_veragrid_case
from mdhelm_pv_case14_exaple import build_system_matrix
from mdhelm_pv_case14_exaple import calculate_known_qx_convolution
from mdhelm_pv_case14_exaple import calculate_known_qx_convolution_numba
from mdhelm_pv_case14_exaple import calculate_known_qx_convolution_parallel_numba
from mdhelm_pv_case14_exaple import calculate_known_reciprocal_convolution
from mdhelm_pv_case14_exaple import calculate_known_reciprocal_convolution_numba
from mdhelm_pv_case14_exaple import calculate_known_reciprocal_convolution_parallel_numba
from mdhelm_pv_case14_exaple import calculate_known_voltage_convolution
from mdhelm_pv_case14_exaple import calculate_known_voltage_convolution_numba
from mdhelm_pv_case14_exaple import calculate_known_voltage_convolution_parallel_numba
from mdhelm_pv_case14_exaple import calculate_monomial_weights
from mdhelm_pv_case14_exaple import calculate_monomial_weights_numba
from mdhelm_pv_case14_exaple import calculate_monomial_weights_parallel_numba
from mdhelm_pv_case14_exaple import calculate_rhs_power_numba
from mdhelm_pv_case14_exaple import count_coefficients
from mdhelm_pv_case14_exaple import create_full_to_local_lookup
from mdhelm_pv_case14_exaple import create_multi_index_table
from mdhelm_pv_case14_exaple import determine_rhs_block_columns
from mdhelm_pv_case14_exaple import format_byte_count
from mdhelm_pv_case14_exaple import get_physical_memory_bytes
from mdhelm_pv_case14_exaple import load_veragrid_case_data
from mdhelm_pv_case14_exaple import run_case14_demo
from mdhelm_pv_case14_exaple import solve_mdhelm_pv
from mdhelm_pv_case14_query_artifact import DimensionKind
from mdhelm_pv_case14_query_artifact import MDHEMQueryResult
from mdhelm_pv_case14_query_artifact import MDHEMPVQueryArtifact
from mdhelm_pv_case14_query_artifact import PhysicalGermContext
from mdhelm_pv_case14_query_artifact import VeraGridQueryCaseData
from mdhelm_pv_case14_query_artifact import build_artifact_from_case
from mdhelm_pv_case14_query_artifact import build_initial_germ_state
from mdhelm_pv_case14_query_artifact import build_query_basis
from mdhelm_pv_case14_query_artifact import calculate_branch_results
from mdhelm_pv_case14_query_artifact import calculate_pv_voltage_error
from mdhelm_pv_case14_query_artifact import calculate_query_mismatch_norm
from mdhelm_pv_case14_query_artifact import compute_power_from_ybus
from mdhelm_pv_case14_query_artifact import create_mdhelm_inputs
from mdhelm_pv_case14_query_artifact import extract_slack_voltage_values
from mdhelm_pv_case14_query_artifact import import_veragrid_engine_modules
from mdhelm_pv_case14_query_artifact import load_multicircuit_from_file
from mdhelm_pv_case14_query_artifact import load_query_artifact
from mdhelm_pv_case14_query_artifact import mdhelm_power_flow
from mdhelm_pv_case14_query_artifact import mdhelm_power_flow_from_sbus
from mdhelm_pv_case14_query_artifact import print_bus_layout
from mdhelm_pv_case14_query_artifact import restore_csc_matrix
from mdhelm_pv_case14_query_artifact import run_case14_artifact_demo
from mdhelm_pv_case14_query_artifact import save_query_artifact
from mdhelm_pv_case14_query_artifact import solve_initial_passive_voltage
from mdhelm_pv_case14_query_artifact import solve_mdhelm_query_artifact
from mdhelm_pv_case14_query_artifact import solve_physical_germ
from mdhelm_pv_case14_query_artifact import solve_physical_germ_step
__all__: list[str] = [
    "DimensionKind",
    "MDHEMQueryResult",
    "MDHEMPVMap",
    "MDHEMPVQueryArtifact",
    "MDHEMRunResult",
    "MultiIndexTable",
    "PhysicalGermContext",
    "SparseLinearSolver",
    "VeraGridCaseData",
    "VeraGridQueryCaseData",
    "build_artifact_from_case",
    "build_initial_germ_state",
    "build_mdhelm_map_from_veragrid_case",
    "build_query_basis",
    "build_system_matrix",
    "calculate_branch_results",
    "calculate_known_qx_convolution",
    "calculate_known_qx_convolution_numba",
    "calculate_known_qx_convolution_parallel_numba",
    "calculate_known_reciprocal_convolution",
    "calculate_known_reciprocal_convolution_numba",
    "calculate_known_reciprocal_convolution_parallel_numba",
    "calculate_known_voltage_convolution",
    "calculate_known_voltage_convolution_numba",
    "calculate_known_voltage_convolution_parallel_numba",
    "calculate_monomial_weights",
    "calculate_monomial_weights_numba",
    "calculate_monomial_weights_parallel_numba",
    "calculate_pv_voltage_error",
    "calculate_query_mismatch_norm",
    "calculate_rhs_power_numba",
    "compute_power_from_ybus",
    "count_coefficients",
    "create_full_to_local_lookup",
    "create_mdhelm_inputs",
    "create_multi_index_table",
    "determine_rhs_block_columns",
    "extract_slack_voltage_values",
    "format_byte_count",
    "get_physical_memory_bytes",
    "import_veragrid_engine_modules",
    "load_multicircuit_from_file",
    "load_query_artifact",
    "load_veragrid_case_data",
    "mdhelm_power_flow",
    "mdhelm_power_flow_from_sbus",
    "print_bus_layout",
    "restore_csc_matrix",
    "run_case14_artifact_demo",
    "run_case14_demo",
    "save_query_artifact",
    "solve_initial_passive_voltage",
    "solve_mdhelm_pv",
    "solve_mdhelm_query_artifact",
    "solve_physical_germ",
    "solve_physical_germ_step",
]
