"""Single demo entry point showing the supported AI power-flow use cases."""

from __future__ import annotations

from enum import Enum

from trunk.ai.ai_power_flow.api import AiPowerFlowFileSplit
from trunk.ai.ai_power_flow.api import AiPowerFlowMode
from trunk.ai.ai_power_flow.api import AiPowerFlowPlotConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowRefinementConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowTrainingConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowWorkflowRequest
from trunk.ai.ai_power_flow.api import AiPowerFlowWorkflowResult
from trunk.ai.ai_power_flow.api import print_workflow_result
from trunk.ai.ai_power_flow.api import run_workflow


class AiPowerFlowDemoCase(Enum):
    """
    Supported demo scenarios.

    :cvar IEEE39_TIME_SERIES_DIRECT: bundled IEEE39 time-series train/test workflow
    :cvar MATPOWER_DIRECT: multi-grid train/test workflow on bundled Matpower files
    :cvar MATPOWER_EXPERIMENT: explicit train/validation/test workflow on bundled Matpower files
    :cvar MATPOWER_HYBRID: GNN warm-start plus native refinement on bundled Matpower files
    :cvar SAME_GRID_EXPERIMENT: train/validation/test workflow on one external time-series grid
    :cvar SAME_GRID_HYBRID: GNN warm-start plus native refinement on one external time-series grid
    """

    IEEE39_TIME_SERIES_DIRECT = "ieee39_time_series_direct"
    MATPOWER_DIRECT = "matpower_direct"
    MATPOWER_EXPERIMENT = "matpower_experiment"
    MATPOWER_HYBRID = "matpower_hybrid"
    SAME_GRID_EXPERIMENT = "same_grid_experiment"
    SAME_GRID_HYBRID = "same_grid_hybrid"


def build_bundled_ieee39_time_series_direct_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the main bundled IEEE39 time-series train/test demo request.

    :returns: workflow request
    """
    grid_file_name: str = "files/IEEE39_1W.gridcal"
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[grid_file_name],
        test_file_names=[grid_file_name],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=True,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.DIRECT,
        file_split=file_split,
        training=training,
        plotting=plotting,
    )
    return request


def build_matpower_direct_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the direct Matpower train/test demo request.

    :returns: workflow request
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[
            "files/case9.matpower",
            "files/case14.matpower",
            "files/case89pegase.matpower",
        ],
        test_file_names=[
            "files/case14_ps.matpower",
            "files/case24_ieee_rts.matpower",
            "files/case_ieee30.matpower",
        ],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=1500,
        default_hours_number=24,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=False,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.DIRECT,
        file_split=file_split,
        training=training,
        plotting=plotting,
    )
    return request


def build_matpower_experiment_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the explicit Matpower train/validation/test demo request.

    :returns: workflow request
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[
            "files/case9.matpower",
            "files/case14.matpower",
            "files/case89pegase.matpower",
        ],
        validation_file_names=[
            "files/case14_ps.matpower",
        ],
        test_file_names=[
            "files/case24_ieee_rts.matpower",
            "files/case_ieee30.matpower",
        ],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=1500,
        default_hours_number=24,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=False,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.EXPERIMENT,
        file_split=file_split,
        training=training,
        plotting=plotting,
    )
    return request


def build_matpower_hybrid_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the hybrid Matpower demo request.

    :returns: workflow request
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[
            "files/case9.matpower",
            "files/case14.matpower",
            "files/case89pegase.matpower",
        ],
        test_file_names=[
            "files/case14_ps.matpower",
        ],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        window=24,
        steps=1500,
        default_hours_number=24,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=False,
    )
    refinement: AiPowerFlowRefinementConfiguration = AiPowerFlowRefinementConfiguration(
        max_iter=25,
        verbose=0,
        start_idx=0,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.HYBRID,
        file_split=file_split,
        training=training,
        plotting=plotting,
        refinement=refinement,
    )
    return request


def build_same_grid_experiment_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the same-grid train/validation/test demo request.

    :returns: workflow request
    """
    grid_file_name: str = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal"
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[grid_file_name],
        validation_file_names=[grid_file_name],
        test_file_names=[grid_file_name],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=True,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.EXPERIMENT,
        file_split=file_split,
        training=training,
        plotting=plotting,
    )
    return request


def build_same_grid_hybrid_request() -> AiPowerFlowWorkflowRequest:
    """
    Build the same-grid hybrid demo request.

    :returns: workflow request
    """
    grid_file_name: str = "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal"
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[grid_file_name],
        test_file_names=[grid_file_name],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
    )
    plotting: AiPowerFlowPlotConfiguration = AiPowerFlowPlotConfiguration(
        plot_validation=False,
        plot_testing=False,
    )
    refinement: AiPowerFlowRefinementConfiguration = AiPowerFlowRefinementConfiguration(
        max_iter=25,
        verbose=0,
        start_idx=0,
    )
    request: AiPowerFlowWorkflowRequest = AiPowerFlowWorkflowRequest(
        mode=AiPowerFlowMode.HYBRID,
        file_split=file_split,
        training=training,
        plotting=plotting,
        refinement=refinement,
    )
    return request


def build_demo_request(demo_case: AiPowerFlowDemoCase) -> AiPowerFlowWorkflowRequest:
    """
    Build the request associated with one demo scenario.

    :param demo_case: selected demo scenario
    :returns: workflow request
    """
    request: AiPowerFlowWorkflowRequest
    if demo_case == AiPowerFlowDemoCase.IEEE39_TIME_SERIES_DIRECT:
        request = build_bundled_ieee39_time_series_direct_request()
    else:
        if demo_case == AiPowerFlowDemoCase.MATPOWER_DIRECT:
            request = build_matpower_direct_request()
        else:
            if demo_case == AiPowerFlowDemoCase.MATPOWER_EXPERIMENT:
                request = build_matpower_experiment_request()
            else:
                if demo_case == AiPowerFlowDemoCase.MATPOWER_HYBRID:
                    request = build_matpower_hybrid_request()
                else:
                    if demo_case == AiPowerFlowDemoCase.SAME_GRID_EXPERIMENT:
                        request = build_same_grid_experiment_request()
                    else:
                        if demo_case == AiPowerFlowDemoCase.SAME_GRID_HYBRID:
                            request = build_same_grid_hybrid_request()
                        else:
                            raise ValueError(f"Unsupported demo case: {demo_case}.")
    return request


def run_demo(demo_case: AiPowerFlowDemoCase) -> AiPowerFlowWorkflowResult:
    """
    Run one supported demo scenario.

    :param demo_case: selected demo scenario
    :returns: workflow result
    """
    request: AiPowerFlowWorkflowRequest = build_demo_request(demo_case=demo_case)
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def main() -> None:
    """
    Run the selected demo scenario.

    :returns: ``None``
    """
    # Make the bundled IEEE39 time-series train/test flow the main package demo.
    selected_demo_case: AiPowerFlowDemoCase = AiPowerFlowDemoCase.IEEE39_TIME_SERIES_DIRECT
    _ = run_demo(demo_case=selected_demo_case)


if __name__ == "__main__":
    main()
