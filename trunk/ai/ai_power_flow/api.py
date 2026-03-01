"""Unified package-style workflow API for the AI power-flow module."""

from __future__ import annotations

from enum import Enum
from typing import Optional

import torch

from trunk.ai.ai_power_flow.experiment_protocol import DatasetCollections
from trunk.ai.ai_power_flow.experiment_protocol import DatasetEvaluationSummary
from trunk.ai.ai_power_flow.experiment_protocol import SplitEvaluationSummary
from trunk.ai.ai_power_flow.experiment_protocol import evaluate_dataset_split
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import GeneralPurposeTypedGNNSolver
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import MultiGridDataset
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import StatelessAcPowerFlowPhysics
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import load_multigrid_collection
from trunk.ai.ai_power_flow.general_purpose_power_flow_gnn import train_general_purpose_solver
from trunk.ai.ai_power_flow.hybrid_inference import HybridInferenceResult
from trunk.ai.ai_power_flow.hybrid_inference import HybridRefinementConfig
from trunk.ai.ai_power_flow.hybrid_inference import predict_and_refine_dataset_window


class AiPowerFlowMode(Enum):
    """
    Supported high-level workflow modes.

    :cvar DIRECT: train on a training split and evaluate on a testing split
    :cvar EXPERIMENT: train on a training split and evaluate on validation and testing splits
    :cvar HYBRID: train on a training split and run GNN plus native refinement on one testing dataset
    """

    DIRECT = "direct"
    EXPERIMENT = "experiment"
    HYBRID = "hybrid"


class AiPowerFlowTrainingConfiguration:
    """
    Training hyper-parameters for the unified workflow API.

    :param embed_dim: solver embedding width
    :param msg_hidden: message/update hidden width
    :param tgn_layers: number of unrolled solver layers
    :param msg_steps: message passing steps per layer
    :param window: requested training and evaluation window
    :param steps: optimizer steps
    :param graphs_per_step: sampled graph windows per optimizer step
    :param lr: learning rate
    :param w_v: voltage supervised loss weight
    :param w_pf: power-flow mismatch loss weight
    :param w_branch_p: branch active-flow loss weight
    :param w_branch_q: branch reactive-flow loss weight
    :param verbose_every: log frequency
    :param default_hours_number: repeated time points for snapshot grids
    :param seed: random seed
    :param use_cartesian_voltage_loss: whether to optimize Cartesian voltage loss instead of voltage-magnitude loss
    """

    __slots__ = (
        "_default_hours_number",
        "_embed_dim",
        "_graphs_per_step",
        "_lr",
        "_msg_hidden",
        "_msg_steps",
        "_seed",
        "_steps",
        "_tgn_layers",
        "_use_cartesian_voltage_loss",
        "_verbose_every",
        "_w_branch_p",
        "_w_branch_q",
        "_w_pf",
        "_w_v",
        "_window",
    )

    def __init__(
        self,
        embed_dim: int = 64,
        msg_hidden: int = 128,
        tgn_layers: int = 6,
        msg_steps: int = 2,
        window: int = 96,
        steps: int = 400,
        graphs_per_step: int = 4,
        lr: float = 1e-3,
        w_v: float = 0.1,
        w_pf: float = 1.0,
        w_branch_p: float = 1.0,
        w_branch_q: float = 0.5,
        verbose_every: int = 50,
        default_hours_number: int = 1,
        seed: int = 0,
        use_cartesian_voltage_loss: bool = True,
    ) -> None:
        """Initialize the training configuration."""
        self._embed_dim = int(embed_dim)
        self._msg_hidden = int(msg_hidden)
        self._tgn_layers = int(tgn_layers)
        self._msg_steps = int(msg_steps)
        self._window = int(window)
        self._steps = int(steps)
        self._graphs_per_step = int(graphs_per_step)
        self._lr = float(lr)
        self._w_v = float(w_v)
        self._w_pf = float(w_pf)
        self._w_branch_p = float(w_branch_p)
        self._w_branch_q = float(w_branch_q)
        self._verbose_every = int(verbose_every)
        self._default_hours_number = int(default_hours_number)
        self._seed = int(seed)
        self._use_cartesian_voltage_loss = bool(use_cartesian_voltage_loss)

    @property
    def embed_dim(self) -> int:
        """Return the solver embedding width."""
        return self._embed_dim

    @property
    def msg_hidden(self) -> int:
        """Return the message/update hidden width."""
        return self._msg_hidden

    @property
    def tgn_layers(self) -> int:
        """Return the number of unrolled solver layers."""
        return self._tgn_layers

    @property
    def msg_steps(self) -> int:
        """Return the message passing steps per layer."""
        return self._msg_steps

    @property
    def window(self) -> int:
        """Return the requested window length."""
        return self._window

    @property
    def steps(self) -> int:
        """Return the optimizer steps."""
        return self._steps

    @property
    def graphs_per_step(self) -> int:
        """Return the sampled graph windows per optimizer step."""
        return self._graphs_per_step

    @property
    def lr(self) -> float:
        """Return the learning rate."""
        return self._lr

    @property
    def w_v(self) -> float:
        """Return the voltage-magnitude loss weight."""
        return self._w_v

    @property
    def w_pf(self) -> float:
        """Return the power-flow mismatch loss weight."""
        return self._w_pf

    @property
    def w_branch_p(self) -> float:
        """Return the branch active-flow loss weight."""
        return self._w_branch_p

    @property
    def w_branch_q(self) -> float:
        """Return the branch reactive-flow loss weight."""
        return self._w_branch_q

    @property
    def verbose_every(self) -> int:
        """Return the training log frequency."""
        return self._verbose_every

    @property
    def default_hours_number(self) -> int:
        """Return the repeated time points used for snapshot grids."""
        return self._default_hours_number

    @property
    def seed(self) -> int:
        """Return the random seed."""
        return self._seed

    @property
    def use_cartesian_voltage_loss(self) -> bool:
        """Return whether Cartesian voltage loss is enabled."""
        return self._use_cartesian_voltage_loss


class AiPowerFlowPlotConfiguration:
    """
    Plotting options for the unified workflow API.

    :param plot_validation: whether to plot validation evaluations
    :param plot_testing: whether to plot testing evaluations
    """

    __slots__ = ("_plot_testing", "_plot_validation")

    def __init__(self, plot_validation: bool = False, plot_testing: bool = True) -> None:
        """Initialize the plot configuration."""
        self._plot_validation = bool(plot_validation)
        self._plot_testing = bool(plot_testing)

    @property
    def plot_validation(self) -> bool:
        """Return whether validation plots are enabled."""
        return self._plot_validation

    @property
    def plot_testing(self) -> bool:
        """Return whether testing plots are enabled."""
        return self._plot_testing


class AiPowerFlowRefinementConfiguration:
    """
    Native-refinement settings for the hybrid workflow.

    :param max_iter: maximum native solver iterations
    :param verbose: native solver verbosity
    :param start_idx: hybrid evaluation start index
    """

    __slots__ = ("_max_iter", "_start_idx", "_verbose")

    def __init__(self, max_iter: int = 25, verbose: int = 0, start_idx: int = 0) -> None:
        """Initialize the refinement configuration."""
        self._max_iter = int(max_iter)
        self._verbose = int(verbose)
        self._start_idx = int(start_idx)

    @property
    def max_iter(self) -> int:
        """Return the native solver maximum iteration count."""
        return self._max_iter

    @property
    def verbose(self) -> int:
        """Return the native solver verbosity."""
        return self._verbose

    @property
    def start_idx(self) -> int:
        """Return the hybrid evaluation start index."""
        return self._start_idx


class AiPowerFlowFileSplit:
    """
    Explicit file split used by the unified workflow API.

    :param train_file_names: training file paths
    :param validation_file_names: validation file paths
    :param test_file_names: testing file paths
    """

    __slots__ = ("_test_file_names", "_train_file_names", "_validation_file_names")

    def __init__(
        self,
        train_file_names: list[str],
        validation_file_names: Optional[list[str]] = None,
        test_file_names: Optional[list[str]] = None,
    ) -> None:
        """Initialize the file split."""
        self._train_file_names = list(train_file_names)
        if validation_file_names is None:
            self._validation_file_names = list()
        else:
            self._validation_file_names = list(validation_file_names)
        if test_file_names is None:
            self._test_file_names = list()
        else:
            self._test_file_names = list(test_file_names)

    @property
    def train_file_names(self) -> list[str]:
        """Return the training file list."""
        return list(self._train_file_names)

    @property
    def validation_file_names(self) -> list[str]:
        """Return the validation file list."""
        return list(self._validation_file_names)

    @property
    def test_file_names(self) -> list[str]:
        """Return the testing file list."""
        return list(self._test_file_names)


class AiPowerFlowWorkflowRequest:
    """
    Unified workflow request.

    :param mode: selected workflow mode
    :param file_split: explicit file split
    :param training: training configuration
    :param plotting: plotting configuration
    :param refinement: optional hybrid refinement configuration
    """

    __slots__ = ("_file_split", "_mode", "_plotting", "_refinement", "_training")

    def __init__(
        self,
        mode: AiPowerFlowMode,
        file_split: AiPowerFlowFileSplit,
        training: AiPowerFlowTrainingConfiguration,
        plotting: Optional[AiPowerFlowPlotConfiguration] = None,
        refinement: Optional[AiPowerFlowRefinementConfiguration] = None,
    ) -> None:
        """Initialize the workflow request."""
        self._mode = mode
        self._file_split = file_split
        self._training = training
        if plotting is None:
            self._plotting = AiPowerFlowPlotConfiguration(plot_validation=False, plot_testing=True)
        else:
            self._plotting = plotting
        self._refinement = refinement

    @property
    def mode(self) -> AiPowerFlowMode:
        """Return the selected workflow mode."""
        return self._mode

    @property
    def file_split(self) -> AiPowerFlowFileSplit:
        """Return the explicit file split."""
        return self._file_split

    @property
    def training(self) -> AiPowerFlowTrainingConfiguration:
        """Return the training configuration."""
        return self._training

    @property
    def plotting(self) -> AiPowerFlowPlotConfiguration:
        """Return the plotting configuration."""
        return self._plotting

    @property
    def refinement(self) -> Optional[AiPowerFlowRefinementConfiguration]:
        """Return the optional hybrid refinement configuration."""
        return self._refinement


class AiPowerFlowWorkflowResult:
    """
    Unified workflow result.

    :param mode: executed workflow mode
    :param solver: trained solver
    :param physics: stateless physics evaluator
    :param collections: materialized datasets
    :param effective_window: effective window length used by the workflow
    :param validation_summary: optional validation summary
    :param test_summary: optional testing summary
    :param hybrid_result: optional hybrid inference result
    """

    __slots__ = (
        "_collections",
        "_effective_window",
        "_hybrid_result",
        "_mode",
        "_physics",
        "_solver",
        "_test_summary",
        "_validation_summary",
    )

    def __init__(
        self,
        mode: AiPowerFlowMode,
        solver: GeneralPurposeTypedGNNSolver,
        physics: StatelessAcPowerFlowPhysics,
        collections: DatasetCollections,
        effective_window: int,
        validation_summary: Optional[SplitEvaluationSummary],
        test_summary: Optional[SplitEvaluationSummary],
        hybrid_result: Optional[HybridInferenceResult],
    ) -> None:
        """Initialize the workflow result."""
        self._mode = mode
        self._solver = solver
        self._physics = physics
        self._collections = collections
        self._effective_window = int(effective_window)
        self._validation_summary = validation_summary
        self._test_summary = test_summary
        self._hybrid_result = hybrid_result

    @property
    def mode(self) -> AiPowerFlowMode:
        """Return the executed workflow mode."""
        return self._mode

    @property
    def solver(self) -> GeneralPurposeTypedGNNSolver:
        """Return the trained solver."""
        return self._solver

    @property
    def physics(self) -> StatelessAcPowerFlowPhysics:
        """Return the physics evaluator."""
        return self._physics

    @property
    def collections(self) -> DatasetCollections:
        """Return the materialized dataset collections."""
        return self._collections

    @property
    def effective_window(self) -> int:
        """Return the effective window length used by the workflow."""
        return self._effective_window

    @property
    def validation_summary(self) -> Optional[SplitEvaluationSummary]:
        """Return the optional validation summary."""
        return self._validation_summary

    @property
    def test_summary(self) -> Optional[SplitEvaluationSummary]:
        """Return the optional testing summary."""
        return self._test_summary

    @property
    def hybrid_result(self) -> Optional[HybridInferenceResult]:
        """Return the optional hybrid inference result."""
        return self._hybrid_result


def build_default_training_configuration() -> AiPowerFlowTrainingConfiguration:
    """
    Build the default training configuration.

    :returns: default training configuration
    """
    configuration: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration()
    return configuration


def build_default_plot_configuration() -> AiPowerFlowPlotConfiguration:
    """
    Build the default plot configuration.

    :returns: default plot configuration
    """
    configuration: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration()
    return configuration


def build_default_refinement_configuration() -> AiPowerFlowRefinementConfiguration:
    """
    Build the default hybrid refinement configuration.

    :returns: default refinement configuration
    """
    configuration: AiPowerFlowRefinementConfiguration = AiPowerFlowRefinementConfiguration()
    return configuration


def load_dataset_split(
    file_names: list[str],
    device: torch.device,
    dtype: torch.dtype,
    default_hours_number: int,
) -> list[MultiGridDataset]:
    """
    Load one file split into materialized datasets.

    :param file_names: file paths to load
    :param device: runtime device
    :param dtype: floating dtype
    :param default_hours_number: repeated time points for snapshot grids
    :returns: loaded datasets
    """
    datasets: list[MultiGridDataset]
    if len(file_names) == 0:
        datasets = list()
    else:
        datasets = load_multigrid_collection(
            file_names=file_names,
            device=device,
            dtype=dtype,
            default_hours_number=default_hours_number,
        )
    return datasets


def build_dataset_collections_from_request(
    request: AiPowerFlowWorkflowRequest,
    device: torch.device,
    dtype: torch.dtype,
) -> DatasetCollections:
    """
    Materialize all dataset splits referenced by a workflow request.

    :param request: workflow request
    :param device: runtime device
    :param dtype: floating dtype
    :returns: materialized dataset collections
    """
    training_datasets: list[MultiGridDataset] = load_dataset_split(
        file_names=request.file_split.train_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=request.training.default_hours_number,
    )
    validation_datasets: list[MultiGridDataset] = load_dataset_split(
        file_names=request.file_split.validation_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=request.training.default_hours_number,
    )
    testing_datasets: list[MultiGridDataset] = load_dataset_split(
        file_names=request.file_split.test_file_names,
        device=device,
        dtype=dtype,
        default_hours_number=request.training.default_hours_number,
    )
    collections: DatasetCollections = DatasetCollections(
        training_datasets=training_datasets,
        validation_datasets=validation_datasets,
        testing_datasets=testing_datasets,
    )
    return collections


def build_solver_and_physics(
    training: AiPowerFlowTrainingConfiguration,
    device: torch.device,
    dtype: torch.dtype,
) -> tuple[GeneralPurposeTypedGNNSolver, StatelessAcPowerFlowPhysics]:
    """
    Build the solver and the stateless physics evaluator.

    :param training: training configuration
    :param device: runtime device
    :param dtype: floating dtype
    :returns: ``(solver, physics)``
    """
    solver: GeneralPurposeTypedGNNSolver = GeneralPurposeTypedGNNSolver(
        embed_dim=training.embed_dim,
        msg_hidden=training.msg_hidden,
        tgn_layers=training.tgn_layers,
        msg_steps=training.msg_steps,
        dtype=dtype,
    ).to(device)
    physics: StatelessAcPowerFlowPhysics = StatelessAcPowerFlowPhysics(dtype=dtype).to(device)
    return solver, physics


def compute_effective_window(
    requested_window: int,
    dataset_groups: list[list[MultiGridDataset]],
) -> int:
    """
    Compute the effective window supported by all participating datasets.

    :param requested_window: requested window length
    :param dataset_groups: participating dataset groups
    :returns: effective window length
    """
    candidate_lengths: list[int] = list()
    dataset_group: list[MultiGridDataset]
    for dataset_group in dataset_groups:
        if len(dataset_group) == 0:
            pass
        else:
            candidate_lengths.append(min(dataset.n_time for dataset in dataset_group))
    if len(candidate_lengths) == 0:
        raise ValueError("At least one non-empty dataset group is required to compute the effective window.")
    else:
        effective_window: int = int(max(1, min(int(requested_window), min(candidate_lengths))))
    return effective_window


def build_direct_split_summary(
    datasets: list[MultiGridDataset],
    split_name: str,
    solver: GeneralPurposeTypedGNNSolver,
    physics: StatelessAcPowerFlowPhysics,
    window: int,
    plot_datasets: bool,
) -> SplitEvaluationSummary:
    """
    Build one split evaluation summary.

    :param datasets: datasets to evaluate
    :param split_name: split label
    :param solver: trained solver
    :param physics: physics evaluator
    :param window: evaluation window
    :param plot_datasets: whether to create plots
    :returns: split evaluation summary
    """
    summary: SplitEvaluationSummary = evaluate_dataset_split(
        solver=solver,
        physics=physics,
        datasets=datasets,
        split_name=split_name,
        window=window,
        plot_datasets=plot_datasets,
    )
    return summary


def validate_workflow_request(request: AiPowerFlowWorkflowRequest) -> None:
    """
    Validate the coherence of a workflow request.

    :param request: workflow request
    :returns: ``None``
    """
    if len(request.file_split.train_file_names) == 0:
        raise ValueError("The unified workflow requires at least one training file.")
    else:
        pass
    if request.mode == AiPowerFlowMode.DIRECT:
        if len(request.file_split.test_file_names) == 0:
            raise ValueError("The direct workflow requires at least one testing file.")
        else:
            pass
    else:
        if request.mode == AiPowerFlowMode.EXPERIMENT:
            if len(request.file_split.validation_file_names) == 0:
                raise ValueError("The experiment workflow requires at least one validation file.")
            else:
                pass
            if len(request.file_split.test_file_names) == 0:
                raise ValueError("The experiment workflow requires at least one testing file.")
            else:
                pass
        else:
            if request.mode == AiPowerFlowMode.HYBRID:
                if len(request.file_split.test_file_names) == 0:
                    raise ValueError("The hybrid workflow requires at least one testing file.")
                else:
                    pass
                if request.refinement is None:
                    raise ValueError("The hybrid workflow requires a refinement configuration.")
                else:
                    pass
            else:
                raise ValueError(f"Unsupported workflow mode: {request.mode}.")


def run_workflow(request: AiPowerFlowWorkflowRequest) -> AiPowerFlowWorkflowResult:
    """
    Run the unified AI power-flow workflow.

    :param request: workflow request
    :returns: workflow result
    """
    validate_workflow_request(request=request)

    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype: torch.dtype = torch.float32
    collections: DatasetCollections = build_dataset_collections_from_request(
        request=request,
        device=device,
        dtype=dtype,
    )
    solver: GeneralPurposeTypedGNNSolver
    physics: StatelessAcPowerFlowPhysics
    solver, physics = build_solver_and_physics(
        training=request.training,
        device=device,
        dtype=dtype,
    )

    dataset_groups: list[list[MultiGridDataset]] = list()
    dataset_groups.append(collections.training_datasets)
    if request.mode == AiPowerFlowMode.DIRECT:
        dataset_groups.append(collections.testing_datasets)
    else:
        if request.mode == AiPowerFlowMode.EXPERIMENT:
            dataset_groups.append(collections.validation_datasets)
            dataset_groups.append(collections.testing_datasets)
        else:
            if request.mode == AiPowerFlowMode.HYBRID:
                dataset_groups.append(collections.testing_datasets)
            else:
                raise ValueError(f"Unsupported workflow mode: {request.mode}.")

    effective_window: int = compute_effective_window(
        requested_window=request.training.window,
        dataset_groups=dataset_groups,
    )

    train_general_purpose_solver(
        solver=solver,
        physics=physics,
        datasets=collections.training_datasets,
        window=effective_window,
        steps=request.training.steps,
        graphs_per_step=request.training.graphs_per_step,
        lr=request.training.lr,
        w_v=request.training.w_v,
        w_pf=request.training.w_pf,
        w_branch_p=request.training.w_branch_p,
        w_branch_q=request.training.w_branch_q,
        verbose_every=request.training.verbose_every,
        seed=request.training.seed,
        use_cartesian_voltage_loss=request.training.use_cartesian_voltage_loss,
    )

    validation_summary: Optional[SplitEvaluationSummary] = None
    test_summary: Optional[SplitEvaluationSummary] = None
    hybrid_result: Optional[HybridInferenceResult] = None

    if request.mode == AiPowerFlowMode.DIRECT:
        test_summary = build_direct_split_summary(
            datasets=collections.testing_datasets,
            split_name="test",
            solver=solver,
            physics=physics,
            window=effective_window,
            plot_datasets=request.plotting.plot_testing,
        )
    else:
        if request.mode == AiPowerFlowMode.EXPERIMENT:
            validation_summary = build_direct_split_summary(
                datasets=collections.validation_datasets,
                split_name="validation",
                solver=solver,
                physics=physics,
                window=effective_window,
                plot_datasets=request.plotting.plot_validation,
            )
            test_summary = build_direct_split_summary(
                datasets=collections.testing_datasets,
                split_name="test",
                solver=solver,
                physics=physics,
                window=effective_window,
                plot_datasets=request.plotting.plot_testing,
            )
        else:
            if request.mode == AiPowerFlowMode.HYBRID:
                refinement_request: AiPowerFlowRefinementConfiguration
                if request.refinement is None:
                    raise ValueError("The hybrid workflow requires a refinement configuration.")
                else:
                    refinement_request = request.refinement
                native_config: HybridRefinementConfig = HybridRefinementConfig(
                    max_iter=refinement_request.max_iter,
                    verbose=refinement_request.verbose,
                )
                hybrid_result = predict_and_refine_dataset_window(
                    solver=solver,
                    dataset=collections.testing_datasets[0],
                    file_name=request.file_split.test_file_names[0],
                    window=effective_window,
                    start_idx=refinement_request.start_idx,
                    default_hours_number=request.training.default_hours_number,
                    refinement_config=native_config,
                )
                summary_entry: DatasetEvaluationSummary = DatasetEvaluationSummary(
                    dataset_name=request.file_split.test_file_names[0],
                    metrics=hybrid_result.refined_metrics,
                )
                test_summary = SplitEvaluationSummary(
                    split_name="hybrid_test",
                    dataset_summaries=[summary_entry],
                )
            else:
                raise ValueError(f"Unsupported workflow mode: {request.mode}.")

    result: AiPowerFlowWorkflowResult = AiPowerFlowWorkflowResult(
        mode=request.mode,
        solver=solver,
        physics=physics,
        collections=collections,
        effective_window=effective_window,
        validation_summary=validation_summary,
        test_summary=test_summary,
        hybrid_result=hybrid_result,
    )
    return result


def print_split_summary(summary: SplitEvaluationSummary) -> None:
    """
    Print one split summary in a uniform format.

    :param summary: split summary
    :returns: ``None``
    """
    print(f"\n[{summary.split_name}]")
    dataset_summary: DatasetEvaluationSummary
    for dataset_summary in summary.dataset_summaries:
        print(
            f"  {dataset_summary.dataset_name}: "
            f"voltage_mse={dataset_summary.metrics.voltage_mse:.6e}  "
            f"vm_mse={dataset_summary.metrics.voltage_magnitude_mse:.6e}  "
            f"pf_mismatch={dataset_summary.metrics.pf_mismatch:.6e}  "
            f"branch_p_mse={dataset_summary.metrics.branch_active_flow_mse:.6e}  "
            f"branch_q_mse={dataset_summary.metrics.branch_reactive_flow_mse:.6e}"
        )


def print_workflow_result(result: AiPowerFlowWorkflowResult) -> None:
    """
    Print the unified workflow result.

    :param result: workflow result
    :returns: ``None``
    """
    print(f"\n[workflow] mode={result.mode.value}  effective_window={result.effective_window}")
    if result.validation_summary is None:
        pass
    else:
        print_split_summary(summary=result.validation_summary)
    if result.test_summary is None:
        pass
    else:
        print_split_summary(summary=result.test_summary)
    if result.hybrid_result is None:
        pass
    else:
        print("\n[gnn_only]")
        print(f"  voltage_mse={result.hybrid_result.gnn_metrics.voltage_mse:.6e}")
        print(f"  vm_mse={result.hybrid_result.gnn_metrics.voltage_magnitude_mse:.6e}")
        print(f"  pf_mismatch={result.hybrid_result.gnn_metrics.pf_mismatch:.6e}")
        print(f"  branch_p_mse={result.hybrid_result.gnn_metrics.branch_active_flow_mse:.6e}")
        print(f"  branch_q_mse={result.hybrid_result.gnn_metrics.branch_reactive_flow_mse:.6e}")
        print("\n[gnn_plus_native_refinement]")
        print(f"  voltage_mse={result.hybrid_result.refined_metrics.voltage_mse:.6e}")
        print(f"  vm_mse={result.hybrid_result.refined_metrics.voltage_magnitude_mse:.6e}")
        print(f"  pf_mismatch={result.hybrid_result.refined_metrics.pf_mismatch:.6e}")
        print(f"  branch_p_mse={result.hybrid_result.refined_metrics.branch_active_flow_mse:.6e}")
        print(f"  branch_q_mse={result.hybrid_result.refined_metrics.branch_reactive_flow_mse:.6e}")
