# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Typed augmentation requests and conservative loading interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch

from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import MultiGridDataset
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import load_multigrid_collection


@dataclass(frozen=True)
class AugmentationSpec:
    """
    Requested augmentation settings for one source file.

    This first version is intentionally conservative. It does not invent synthetic
    labels from unsupported perturbations. Instead, it provides a typed place where
    file-level augmentation semantics can be attached later.

    :param replicate_count: how many times to repeat this source request
    :param tag: human-readable augmentation tag
    """

    replicate_count: int
    tag: str


@dataclass(frozen=True)
class DatasetRequest:
    """
    One requested dataset source plus its augmentation description.

    :param file_name: source file name
    :param augmentation: augmentation specification
    """

    file_name: str
    augmentation: AugmentationSpec


@dataclass(frozen=True)
class DatasetRequestCollection:
    """
    Typed collection of dataset requests.

    :param requests: request list
    """

    requests: list[DatasetRequest]


@dataclass(frozen=True)
class AugmentedDatasetEntry:
    """
    Loaded dataset plus augmentation metadata.

    :param dataset: loaded dataset
    :param source_file_name: source file name
    :param augmentation_tag: augmentation tag
    :param augmentation_index: replication index
    """

    dataset: MultiGridDataset
    source_file_name: str
    augmentation_tag: str
    augmentation_index: int


def expand_dataset_requests(request_collection: DatasetRequestCollection) -> list[DatasetRequest]:
    """
    Expand replicated dataset requests into a flat request list.

    :param request_collection: typed request collection
    :returns: flat request list
    """
    expanded_requests: list[DatasetRequest] = list()
    request: DatasetRequest
    for request in request_collection.requests:
        replicate_count: int = int(request.augmentation.replicate_count)
        replicate_idx: int
        for replicate_idx in range(replicate_count):
            _ = replicate_idx
            expanded_requests.append(request)
    return expanded_requests


def load_augmented_dataset_entries(
    request_collection: DatasetRequestCollection,
    device: Optional[torch.device] = None,
    dtype: torch.dtype = torch.float32,
    default_hours_number: int = 1,
) -> list[AugmentedDatasetEntry]:
    """
    Load datasets from a typed augmentation request collection.

    :param request_collection: typed request collection
    :param device: runtime device, or ``None``
    :param dtype: floating dtype
    :param default_hours_number: repeated time points for snapshot grids
    :returns: augmented dataset entry list
    """
    # This is intentionally conservative:
    # - every entry is loaded through the same trusted dataset builder
    # - no label-breaking perturbation is introduced here yet
    # - the augmentation metadata is still recorded explicitly so real augmentations
    #   can be added later without redesigning the training interfaces
    expanded_requests: list[DatasetRequest] = expand_dataset_requests(request_collection=request_collection)
    file_names: list[str] = list()
    request: DatasetRequest
    for request in expanded_requests:
        file_names.append(request.file_name)

    loaded_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number,
    )

    entries: list[AugmentedDatasetEntry] = list()
    idx: int
    for idx in range(len(loaded_datasets)):
        dataset: MultiGridDataset = loaded_datasets[idx]
        request = expanded_requests[idx]
        entry: AugmentedDatasetEntry = AugmentedDatasetEntry(
            dataset=dataset,
            source_file_name=request.file_name,
            augmentation_tag=request.augmentation.tag,
            augmentation_index=idx,
        )
        entries.append(entry)
    return entries
