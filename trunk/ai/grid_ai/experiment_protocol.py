# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""
Experiment protocol utilities for the general-purpose power-flow GNN.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch

from general_purpose_power_flow_gnn import EvaluationMetrics
from general_purpose_power_flow_gnn import EvaluationResult
from general_purpose_power_flow_gnn import GeneralPurposeTypedGNNSolver
from general_purpose_power_flow_gnn import MultiGridDataset
from general_purpose_power_flow_gnn import StatelessAcPowerFlowPhysics
from general_purpose_power_flow_gnn import evaluate_general_purpose_solver_on_dataset
from general_purpose_power_flow_gnn import load_multigrid_collection
from general_purpose_power_flow_gnn import plot_testing_performance
from general_purpose_power_flow_gnn import train_general_purpose_solver


@dataclass(frozen=True)
class FileSplit:
    """
    Explicit train/validation/test file split.

    :param train_file_names: training file list
    :param validation_file_names: validation file list
    :param test_file_names: testing file list
    """

    train_file_names: list[str]
    validation_file_names: list[str]
    test_file_names: list[str]


@dataclass(frozen=True)
class ExperimentHyperParameters:
    """
    Hyper-parameters for one experiment run.

    :param embed_dim: solver embedding width
    :param msg_hidden: message/update MLP hidden width
    :param tgn_layers: unrolled solver layers
    :param msg_steps: message passing steps per layer
    :param window: requested train/evaluation window
    :param steps: optimizer steps
    :param graphs_per_step: sampled graph windows per optimizer step
    :param lr: learning rate
    :param w_v: voltage magnitude loss weight
    :param w_pf: power-flow mismatch loss weight
    :param verbose_every: log frequency
    :param default_hours_number: repeated time points for snapshot grids
    """

    embed_dim: int
    msg_hidden: int
    tgn_layers: int
    msg_steps: int
    window: int
    steps: int
    graphs_per_step: int
    lr: float
    w_v: float
    w_pf: float
    verbose_every: int
    default_hours_number: int


@dataclass(frozen=True)
class DatasetCollections:
    """
    Materialized dataset collections for an experiment.

    :param training_datasets: training datasets
    :param validation_datasets: validation datasets
    :param testing_datasets: testing datasets
    """

    training_datasets: list[MultiGridDataset]
    validation_datasets: list[MultiGridDataset]
    testing_datasets: list[MultiGridDataset]


@dataclass(frozen=True)
class DatasetEvaluationSummary:
    """
    Scalar evaluation summary for one dataset.

    :param dataset_name: dataset identifier
    :param metrics: scalar metrics
    """

    dataset_name: str
    metrics: EvaluationMetrics


@dataclass(frozen=True)
class SplitEvaluationSummary:
    """
    Evaluation summary for one split.

    :param split_name: split label
    :param dataset_summaries: per-dataset summaries
    """

    split_name: str
    dataset_summaries: list[DatasetEvaluationSummary]


@dataclass(frozen=True)
class ExperimentRunResult:
    """
    Full result of one experiment run.

    :param collections: materialized dataset collections
    :param validation_summary: validation split evaluation summary
    :param test_summary: testing split evaluation summary
    """

    collections: DatasetCollections
    validation_summary: SplitEvaluationSummary
    test_summary: SplitEvaluationSummary


def build_dataset_collections(
    file_split: FileSplit,
    device: Optional[torch.device] = None,
    dtype: torch.dtype = torch.float32,
    default_hours_number: int = 1,
) -> DatasetCollections:
    """
    Build explicit training, validation and testing dataset collections.

    :param file_split: experiment file split
    :param device: runtime device, or ``None``
    :param dtype: floating dtype
    :param default_hours_number: repeated time points for snapshot grids
    :returns: materialized dataset collections
    """
    # The point of this function is to make dataset construction explicit at the split level.
    training_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=file_split.train_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number,
    )
    validation_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=file_split.validation_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number,
    )
    testing_datasets: list[MultiGridDataset] = load_multigrid_collection(
        file_names=file_split.test_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=default_hours_number,
    )
    collections: DatasetCollections = DatasetCollections(
        training_datasets=training_datasets,
        validation_datasets=validation_datasets,
        testing_datasets=testing_datasets,
    )
    return collections


def evaluate_dataset_split(
    solver: GeneralPurposeTypedGNNSolver,
    physics: StatelessAcPowerFlowPhysics,
    datasets: list[MultiGridDataset],
    split_name: str,
    window: int,
    plot_datasets: bool,
) -> SplitEvaluationSummary:
    """
    Evaluate one split of datasets.

    :param solver: trained shared-weight solver
    :param physics: stateless physics evaluator
    :param datasets: dataset split
    :param split_name: split label
    :param window: evaluation window
    :param plot_datasets: whether to plot each dataset evaluation
    :returns: split evaluation summary
    """
    dataset_summaries: list[DatasetEvaluationSummary] = list()
    dataset: MultiGridDataset
    for dataset in datasets:
        evaluation_result: EvaluationResult = evaluate_general_purpose_solver_on_dataset(
            solver=solver,
            physics=physics,
            dataset=dataset,
            window=window,
            start_idx=0,
        )
        dataset_summary: DatasetEvaluationSummary = DatasetEvaluationSummary(
            dataset_name=dataset.name,
            metrics=evaluation_result.metrics,
        )
        dataset_summaries.append(dataset_summary)
        if plot_datasets:
            plot_testing_performance(
                solver=solver,
                physics=physics,
                dataset=dataset,
                evaluation_result=evaluation_result,
                bus_indices=None,
                branch_indices=None,
            )
        else:
            pass
    split_summary: SplitEvaluationSummary = SplitEvaluationSummary(
        split_name=split_name,
        dataset_summaries=dataset_summaries,
    )
    return split_summary


def run_experiment_protocol(
    file_split: FileSplit,
    hyper_parameters: ExperimentHyperParameters,
    plot_validation: bool = False,
    plot_testing: bool = True,
) -> ExperimentRunResult:
    """
    Run one full train/validation/test experiment.

    :param file_split: experiment file split
    :param hyper_parameters: experiment hyper-parameters
    :param plot_validation: whether to plot validation evaluations
    :param plot_testing: whether to plot testing evaluations
    :returns: experiment result
    """
    # This function makes the experiment control flow explicit:
    # build split datasets -> train on train split -> evaluate on validation/test splits.
    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype: torch.dtype = torch.float32

    collections: DatasetCollections = build_dataset_collections(
        file_split=file_split,
        device=device,
        dtype=dtype,
        default_hours_number=hyper_parameters.default_hours_number,
    )

    solver: GeneralPurposeTypedGNNSolver = GeneralPurposeTypedGNNSolver(
        embed_dim=hyper_parameters.embed_dim,
        msg_hidden=hyper_parameters.msg_hidden,
        tgn_layers=hyper_parameters.tgn_layers,
        msg_steps=hyper_parameters.msg_steps,
        dtype=dtype,
    ).to(device)
    physics: StatelessAcPowerFlowPhysics = StatelessAcPowerFlowPhysics(dtype=dtype).to(device)

    min_train_time: int = min(dataset.n_time for dataset in collections.training_datasets)
    min_validation_time: int = min(dataset.n_time for dataset in collections.validation_datasets)
    min_test_time: int = min(dataset.n_time for dataset in collections.testing_datasets)
    effective_window: int = int(
        max(
            1,
            min(
                int(hyper_parameters.window),
                min_train_time,
                min_validation_time,
                min_test_time,
            ),
        )
    )

    print("\n[experiment] training on explicit training split")
    train_general_purpose_solver(
        solver=solver,
        physics=physics,
        datasets=collections.training_datasets,
        window=effective_window,
        steps=hyper_parameters.steps,
        graphs_per_step=hyper_parameters.graphs_per_step,
        lr=hyper_parameters.lr,
        w_v=hyper_parameters.w_v,
        w_pf=hyper_parameters.w_pf,
        verbose_every=hyper_parameters.verbose_every,
        seed=0,
    )

    print("\n[experiment] evaluating validation split")
    validation_summary: SplitEvaluationSummary = evaluate_dataset_split(
        solver=solver,
        physics=physics,
        datasets=collections.validation_datasets,
        split_name="validation",
        window=effective_window,
        plot_datasets=plot_validation,
    )

    print("\n[experiment] evaluating test split")
    test_summary: SplitEvaluationSummary = evaluate_dataset_split(
        solver=solver,
        physics=physics,
        datasets=collections.testing_datasets,
        split_name="test",
        window=effective_window,
        plot_datasets=plot_testing,
    )

    result: ExperimentRunResult = ExperimentRunResult(
        collections=collections,
        validation_summary=validation_summary,
        test_summary=test_summary,
    )
    return result
