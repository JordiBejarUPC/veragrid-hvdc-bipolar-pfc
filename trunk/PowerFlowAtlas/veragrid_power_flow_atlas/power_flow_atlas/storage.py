from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.lib.npyio import NpzFile
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import SuperLU, splu

from power_flow_atlas.enumerations import AtlasStorageStatus
from power_flow_atlas.model import (
    AtlasStorageResult,
    PowerFlowAtlas,
    PowerFlowAtlasPatch,
)
from power_flow_atlas.rectangular_series import build_topology_signature


def save_power_flow_atlas(
    directory_path: Path,
    atlas: PowerFlowAtlas,
) -> AtlasStorageResult:
    """Persist an atlas without serializing SciPy factorization internals.

    The sparse Jacobian is stored in native CSC arrays. Its LU factorization is
    deliberately rebuilt while loading because ``SuperLU`` is not a stable,
    portable persistence format across Python, SciPy, and processor versions.

    :param directory_path: Directory receiving the atlas artifact.
    :param atlas: Finalized atlas to persist.
    :return: Explicit storage result.
    """
    format_version: int = 2
    result: AtlasStorageResult
    input_valid: bool = bool(str(directory_path) != "")

    if input_valid:
        input_output_successful: bool = True
        diagnostic: str = "Atlas saved"
        try:
            directory_path.mkdir(parents=True, exist_ok=True)
            y_bus: csc_matrix = atlas.get_y_bus()
            bus_count: int = atlas.get_bus_count()
            branch_model_present: bool = atlas.has_branch_model()
            y_from_optional: csc_matrix | None = atlas.get_y_from()
            y_to_optional: csc_matrix | None = atlas.get_y_to()
            branch_from_optional: np.ndarray | None = (
                atlas.get_branch_from_indices()
            )
            branch_to_optional: np.ndarray | None = atlas.get_branch_to_indices()
            branch_model_complete: bool = bool(
                y_from_optional is not None
                and y_to_optional is not None
                and branch_from_optional is not None
                and branch_to_optional is not None
            )

            stored_y_from: csc_matrix = csc_matrix(
                (0, bus_count),
                dtype=np.complex128,
            )
            stored_y_to: csc_matrix = csc_matrix(
                (0, bus_count),
                dtype=np.complex128,
            )
            stored_branch_from: np.ndarray = np.empty(0, dtype=np.int64)
            stored_branch_to: np.ndarray = np.empty(0, dtype=np.int64)
            if branch_model_present and branch_model_complete:
                stored_y_from = y_from_optional
                stored_y_to = y_to_optional
                stored_branch_from = np.asarray(
                    branch_from_optional,
                    dtype=np.int64,
                )
                stored_branch_to = np.asarray(
                    branch_to_optional,
                    dtype=np.int64,
                )
            else:
                if branch_model_present:
                    input_output_successful = False
                    diagnostic = "Atlas branch-flow model is incomplete"
                else:
                    input_output_successful = input_output_successful and True

            if input_output_successful:
                metadata_path: Path = directory_path / "atlas_metadata.npz"
                np.savez_compressed(
                    metadata_path,
                    format_version=np.asarray((format_version,), dtype=np.int64),
                    topology_signature=np.asarray(
                        (atlas.get_topology_signature(),),
                        dtype=np.str_,
                    ),
                    system_base_power=np.asarray(
                        (atlas.get_system_base_power(),),
                        dtype=np.float64,
                    ),
                    bus_count=np.asarray((bus_count,), dtype=np.int64),
                    patch_count=np.asarray(
                        (atlas.get_patch_count(),),
                        dtype=np.int64,
                    ),
                    branch_model_present=np.asarray(
                        (branch_model_present,),
                        dtype=np.bool_,
                    ),
                    y_bus_shape=np.asarray(y_bus.shape, dtype=np.int64),
                    y_bus_data=np.asarray(y_bus.data, dtype=np.complex128),
                    y_bus_indices=np.asarray(y_bus.indices, dtype=np.int64),
                    y_bus_indptr=np.asarray(y_bus.indptr, dtype=np.int64),
                    y_from_shape=np.asarray(
                        stored_y_from.shape,
                        dtype=np.int64,
                    ),
                    y_from_data=np.asarray(
                        stored_y_from.data,
                        dtype=np.complex128,
                    ),
                    y_from_indices=np.asarray(
                        stored_y_from.indices,
                        dtype=np.int64,
                    ),
                    y_from_indptr=np.asarray(
                        stored_y_from.indptr,
                        dtype=np.int64,
                    ),
                    y_to_shape=np.asarray(stored_y_to.shape, dtype=np.int64),
                    y_to_data=np.asarray(
                        stored_y_to.data,
                        dtype=np.complex128,
                    ),
                    y_to_indices=np.asarray(
                        stored_y_to.indices,
                        dtype=np.int64,
                    ),
                    y_to_indptr=np.asarray(
                        stored_y_to.indptr,
                        dtype=np.int64,
                    ),
                    branch_from_indices=stored_branch_from,
                    branch_to_indices=stored_branch_to,
                )
            else:
                input_output_successful = False
                diagnostic = "Atlas metadata could not be written"

            patch_index: int
            for patch_index in range(atlas.get_patch_count()):
                if input_output_successful:
                    patch: PowerFlowAtlasPatch | None = atlas.get_patch(patch_index)
                    if patch is not None:
                        jacobian: csc_matrix = patch.get_rectangular_jacobian()
                        patch_path: Path = directory_path / (
                            "patch_{:06d}.npz".format(patch_index)
                        )
                        np.savez_compressed(
                            patch_path,
                            patch_id=np.asarray(
                                (patch.get_patch_id(),),
                                dtype=np.int64,
                            ),
                            anchor_s=patch.get_anchor_s(),
                            anchor_v=patch.get_anchor_v(),
                            bus_types=patch.get_bus_types(),
                            slack_indices=patch.get_slack_indices(),
                            pv_indices=patch.get_pv_indices(),
                            pq_indices=patch.get_pq_indices(),
                            free_indices=patch.get_free_indices(),
                            vm2_setpoint=patch.get_vm2_setpoint(),
                            q_min=patch.get_q_min(),
                            q_max=patch.get_q_max(),
                            jacobian_shape=np.asarray(
                                jacobian.shape,
                                dtype=np.int64,
                            ),
                            jacobian_data=np.asarray(
                                jacobian.data,
                                dtype=np.float64,
                            ),
                            jacobian_indices=np.asarray(
                                jacobian.indices,
                                dtype=np.int64,
                            ),
                            jacobian_indptr=np.asarray(
                                jacobian.indptr,
                                dtype=np.int64,
                            ),
                            validity_radius=np.asarray(
                                (patch.get_validity_radius(),),
                                dtype=np.float64,
                            ),
                            series_order=np.asarray(
                                (patch.get_series_order(),),
                                dtype=np.int64,
                            ),
                            anchor_residual=np.asarray(
                                (patch.get_anchor_residual(),),
                                dtype=np.float64,
                            ),
                        )
                    else:
                        input_output_successful = False
                        diagnostic = "Atlas contains an unavailable patch"
                else:
                    input_output_successful = False
        except (OSError, ValueError):
            input_output_successful = False
            diagnostic = "Atlas files could not be written"

        if input_output_successful:
            result = AtlasStorageResult(
                status=AtlasStorageStatus.Saved,
                atlas=atlas,
                message=diagnostic,
            )
        else:
            result = AtlasStorageResult(
                status=AtlasStorageStatus.InputOutputFailure,
                atlas=None,
                message=diagnostic,
            )
    else:
        result = AtlasStorageResult(
            status=AtlasStorageStatus.InvalidPath,
            atlas=None,
            message="Atlas directory path is empty",
        )
    return result


def load_power_flow_atlas(directory_path: Path) -> AtlasStorageResult:
    """Load an atlas and rebuild every reusable sparse LU factorization.

    :param directory_path: Directory containing the persisted atlas artifact.
    :return: Explicit storage result containing the loaded atlas when successful.
    """
    expected_format_version: int = 2
    metadata_path: Path = directory_path / "atlas_metadata.npz"
    result: AtlasStorageResult

    if directory_path.is_dir() and metadata_path.is_file():
        load_successful: bool = True
        factorization_successful: bool = True
        diagnostic: str = "Atlas loaded"
        atlas: PowerFlowAtlas | None = None
        try:
            metadata: NpzFile
            with np.load(metadata_path, allow_pickle=False) as metadata:
                metadata_file: NpzFile = metadata
                format_version: int = int(metadata_file["format_version"][0])
                topology_signature: str = str(
                    metadata_file["topology_signature"][0]
                )
                system_base_power: float = float(
                    metadata_file["system_base_power"][0]
                )
                bus_count: int = int(metadata_file["bus_count"][0])
                patch_count: int = int(metadata_file["patch_count"][0])
                branch_model_present: bool = bool(
                    metadata_file["branch_model_present"][0]
                )

                y_bus_shape_values: np.ndarray = np.asarray(
                    metadata_file["y_bus_shape"],
                    dtype=np.int64,
                )
                y_bus_shape: tuple[int, int] = (
                    int(y_bus_shape_values[0]),
                    int(y_bus_shape_values[1]),
                )
                y_bus: csc_matrix = csc_matrix(
                    (
                        np.asarray(
                            metadata_file["y_bus_data"],
                            dtype=np.complex128,
                        ),
                        np.asarray(
                            metadata_file["y_bus_indices"],
                            dtype=np.int64,
                        ),
                        np.asarray(
                            metadata_file["y_bus_indptr"],
                            dtype=np.int64,
                        ),
                    ),
                    shape=y_bus_shape,
                )

                y_from_shape_values: np.ndarray = np.asarray(
                    metadata_file["y_from_shape"],
                    dtype=np.int64,
                )
                y_from_shape: tuple[int, int] = (
                    int(y_from_shape_values[0]),
                    int(y_from_shape_values[1]),
                )
                stored_y_from: csc_matrix = csc_matrix(
                    (
                        np.asarray(
                            metadata_file["y_from_data"],
                            dtype=np.complex128,
                        ),
                        np.asarray(
                            metadata_file["y_from_indices"],
                            dtype=np.int64,
                        ),
                        np.asarray(
                            metadata_file["y_from_indptr"],
                            dtype=np.int64,
                        ),
                    ),
                    shape=y_from_shape,
                )

                y_to_shape_values: np.ndarray = np.asarray(
                    metadata_file["y_to_shape"],
                    dtype=np.int64,
                )
                y_to_shape: tuple[int, int] = (
                    int(y_to_shape_values[0]),
                    int(y_to_shape_values[1]),
                )
                stored_y_to: csc_matrix = csc_matrix(
                    (
                        np.asarray(
                            metadata_file["y_to_data"],
                            dtype=np.complex128,
                        ),
                        np.asarray(
                            metadata_file["y_to_indices"],
                            dtype=np.int64,
                        ),
                        np.asarray(
                            metadata_file["y_to_indptr"],
                            dtype=np.int64,
                        ),
                    ),
                    shape=y_to_shape,
                )
                stored_branch_from: np.ndarray = np.asarray(
                    metadata_file["branch_from_indices"],
                    dtype=np.int64,
                )
                stored_branch_to: np.ndarray = np.asarray(
                    metadata_file["branch_to_indices"],
                    dtype=np.int64,
                )

            y_from: csc_matrix | None
            y_to: csc_matrix | None
            branch_from_indices: np.ndarray | None
            branch_to_indices: np.ndarray | None
            if branch_model_present:
                y_from = stored_y_from
                y_to = stored_y_to
                branch_from_indices = stored_branch_from
                branch_to_indices = stored_branch_to
                branch_count: int = int(stored_branch_from.size)
                branch_model_valid: bool = bool(
                    stored_branch_to.size == branch_count
                    and stored_y_from.shape == (branch_count, bus_count)
                    and stored_y_to.shape == (branch_count, bus_count)
                )
            else:
                y_from = None
                y_to = None
                branch_from_indices = None
                branch_to_indices = None
                branch_model_valid = bool(
                    stored_y_from.shape == (0, bus_count)
                    and stored_y_to.shape == (0, bus_count)
                    and stored_branch_from.size == 0
                    and stored_branch_to.size == 0
                )

            calculated_signature: str = build_topology_signature(
                system_base_power=system_base_power,
                y_bus=y_bus,
                y_from=y_from,
                y_to=y_to,
                branch_from_indices=branch_from_indices,
                branch_to_indices=branch_to_indices,
            )
            metadata_valid: bool = bool(
                format_version == expected_format_version
                and bus_count > 0
                and patch_count > 0
                and y_bus.shape == (bus_count, bus_count)
                and branch_model_valid
                and calculated_signature == topology_signature
            )
            if metadata_valid:
                patch_array: np.ndarray = np.empty(patch_count, dtype=object)
                patch_index: int
                for patch_index in range(patch_count):
                    patch_path: Path = directory_path / (
                        "patch_{:06d}.npz".format(patch_index)
                    )
                    if patch_path.is_file():
                        patch_data: NpzFile
                        with np.load(patch_path, allow_pickle=False) as patch_data:
                            patch_file: NpzFile = patch_data
                            anchor_s: np.ndarray = np.asarray(
                                patch_file["anchor_s"],
                                dtype=np.complex128,
                            )
                            anchor_v: np.ndarray = np.asarray(
                                patch_file["anchor_v"],
                                dtype=np.complex128,
                            )
                            bus_types: np.ndarray = np.asarray(
                                patch_file["bus_types"],
                                dtype=np.int64,
                            )
                            slack_indices: np.ndarray = np.asarray(
                                patch_file["slack_indices"],
                                dtype=np.int64,
                            )
                            pv_indices: np.ndarray = np.asarray(
                                patch_file["pv_indices"],
                                dtype=np.int64,
                            )
                            pq_indices: np.ndarray = np.asarray(
                                patch_file["pq_indices"],
                                dtype=np.int64,
                            )
                            free_indices: np.ndarray = np.asarray(
                                patch_file["free_indices"],
                                dtype=np.int64,
                            )
                            vm2_setpoint: np.ndarray = np.asarray(
                                patch_file["vm2_setpoint"],
                                dtype=np.float64,
                            )
                            q_min: np.ndarray = np.asarray(
                                patch_file["q_min"],
                                dtype=np.float64,
                            )
                            q_max: np.ndarray = np.asarray(
                                patch_file["q_max"],
                                dtype=np.float64,
                            )
                            jacobian_shape_values: np.ndarray = np.asarray(
                                patch_file["jacobian_shape"],
                                dtype=np.int64,
                            )
                            jacobian_shape: tuple[int, int] = (
                                int(jacobian_shape_values[0]),
                                int(jacobian_shape_values[1]),
                            )
                            jacobian: csc_matrix = csc_matrix(
                                (
                                    np.asarray(
                                        patch_file["jacobian_data"],
                                        dtype=np.float64,
                                    ),
                                    np.asarray(
                                        patch_file["jacobian_indices"],
                                        dtype=np.int64,
                                    ),
                                    np.asarray(
                                        patch_file["jacobian_indptr"],
                                        dtype=np.int64,
                                    ),
                                ),
                                shape=jacobian_shape,
                            )
                            expected_state_size: int = 2 * free_indices.size
                            patch_sizes_valid: bool = bool(
                                anchor_s.size == bus_count
                                and anchor_v.size == bus_count
                                and bus_types.size == bus_count
                                and q_min.size == bus_count
                                and q_max.size == bus_count
                                and slack_indices.size
                                + pv_indices.size
                                + pq_indices.size
                                == bus_count
                                and vm2_setpoint.size == pv_indices.size
                                and jacobian.shape
                                == (expected_state_size, expected_state_size)
                            )
                            factorization: SuperLU | None = None
                            if patch_sizes_valid:
                                try:
                                    factorization = splu(jacobian)
                                except RuntimeError:
                                    factorization_successful = False
                            else:
                                factorization_successful = False

                            if factorization_successful and factorization is not None:
                                patch: PowerFlowAtlasPatch = PowerFlowAtlasPatch(
                                    patch_id=int(patch_file["patch_id"][0]),
                                    anchor_s=anchor_s,
                                    anchor_v=anchor_v,
                                    bus_types=bus_types,
                                    slack_indices=slack_indices,
                                    pv_indices=pv_indices,
                                    pq_indices=pq_indices,
                                    free_indices=free_indices,
                                    vm2_setpoint=vm2_setpoint,
                                    q_min=q_min,
                                    q_max=q_max,
                                    rectangular_jacobian=jacobian,
                                    factorization=factorization,
                                    validity_radius=float(
                                        patch_file["validity_radius"][0]
                                    ),
                                    series_order=int(
                                        patch_file["series_order"][0]
                                    ),
                                    anchor_residual=float(
                                        patch_file["anchor_residual"][0]
                                    ),
                                )
                                patch_array[patch_index] = patch
                            else:
                                load_successful = False
                                diagnostic = (
                                    "A stored patch is incompatible or cannot "
                                    "be factorized"
                                )
                    else:
                        load_successful = False
                        diagnostic = "A required patch file is missing"

                if load_successful and factorization_successful:
                    patches: tuple[PowerFlowAtlasPatch, ...] = tuple(patch_array)
                    atlas = PowerFlowAtlas(
                        topology_signature=topology_signature,
                        system_base_power=system_base_power,
                        bus_count=bus_count,
                        y_bus=y_bus,
                        y_from=y_from,
                        y_to=y_to,
                        branch_from_indices=branch_from_indices,
                        branch_to_indices=branch_to_indices,
                        patches=patches,
                    )
                else:
                    atlas = None
            else:
                load_successful = False
                diagnostic = "Atlas metadata is incompatible or incomplete"
        except (OSError, ValueError, KeyError, IndexError):
            load_successful = False
            diagnostic = "Atlas files are unreadable or have an invalid format"

        if load_successful and atlas is not None:
            result = AtlasStorageResult(
                status=AtlasStorageStatus.Loaded,
                atlas=atlas,
                message=diagnostic,
            )
        else:
            if factorization_successful:
                status: AtlasStorageStatus = AtlasStorageStatus.InvalidFormat
            else:
                status = AtlasStorageStatus.FactorizationFailure
            result = AtlasStorageResult(
                status=status,
                atlas=None,
                message=diagnostic,
            )
    else:
        result = AtlasStorageResult(
            status=AtlasStorageStatus.InvalidPath,
            atlas=None,
            message="Atlas directory or metadata file does not exist",
        )
    return result
