"""Plain demo functions for the AI power-flow package."""

from __future__ import annotations

from trunk.ai.ai_power_flow.api import AiPowerFlowFileSplit
from trunk.ai.ai_power_flow.api import AiPowerFlowMode
from trunk.ai.ai_power_flow.api import AiPowerFlowPlotConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowRefinementConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowTrainingConfiguration
from trunk.ai.ai_power_flow.api import AiPowerFlowWorkflowRequest
from trunk.ai.ai_power_flow.api import AiPowerFlowWorkflowResult
from trunk.ai.ai_power_flow.api import print_workflow_result
from trunk.ai.ai_power_flow.api import run_workflow


def run_ieee39_time_series_train_test_demo() -> AiPowerFlowWorkflowResult:
    """
    Run the main bundled IEEE39 time-series train/test demo.

    This is the simplest realistic example in this folder and is the default
    demo executed by :func:`main`.

    What this demo does:

    - opens the bundled ``files/IEEE39_1W.gridcal`` file
    - uses that same time-series grid for training
    - uses that same time-series grid again for testing
    - keeps the workflow in direct train/test mode
    - enables testing plots so the post-training RMS curves are visible

    Why this demo exists:

    - it uses a real bundled ``.gridcal`` file instead of synthetic snapshot repetition
    - it is the shortest path from package entry point to an actual time-series run
    - it is the most useful first debug target when working on the solver

    :returns: workflow result for the bundled IEEE39 direct demo
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=["files/IEEE39_1W.gridcal"],
        test_file_names=["files/IEEE39_1W.gridcal"],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def run_matpower_train_test_demo() -> AiPowerFlowWorkflowResult:
    """
    Run a bundled Matpower multi-grid direct train/test demo.

    What this demo does:

    - trains one shared solver on several bundled Matpower cases
    - evaluates that trained solver on a separate bundled Matpower test set
    - disables plots to keep the run lightweight

    Why this demo exists:

    - it shows the intended multi-grid usage pattern
    - it stresses graph transfer more than the single-grid IEEE39 example
    - it is useful when testing whether architecture changes generalize across topologies

    :returns: workflow result for the bundled Matpower direct demo
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
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def run_matpower_experiment_demo() -> AiPowerFlowWorkflowResult:
    """
    Run a bundled Matpower train/validation/test experiment demo.

    What this demo does:

    - uses explicit training, validation, and testing file lists
    - runs the package in ``EXPERIMENT`` mode instead of direct train/test mode
    - prints split summaries for validation and testing

    Why this demo exists:

    - it shows how to structure a more honest experiment with explicit split semantics
    - it is the right starting point when comparing hyper-parameters or architectures
    - it avoids mixing model selection and final evaluation by construction

    :returns: workflow result for the bundled Matpower experiment demo
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[
            "files/case9.matpower",
            "files/case14.matpower",
            "files/case89pegase.matpower",
        ],
        validation_file_names=["files/case14_ps.matpower"],
        test_file_names=[
            "files/case24_ieee_rts.matpower",
            "files/case_ieee30.matpower",
        ],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=1500,
        default_hours_number=24,
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def run_matpower_hybrid_demo() -> AiPowerFlowWorkflowResult:
    """
    Run a bundled Matpower hybrid inference demo.

    What this demo does:

    - trains on several bundled Matpower cases
    - predicts one testing case with the learned solver
    - refines that prediction with VeraGrid's native power-flow solver

    Why this demo exists:

    - it shows the warm-start-plus-native-refinement workflow
    - it is useful when pure learned inference is not accurate enough
    - it helps compare GNN-only versus GNN-plus-native refinement behavior

    :returns: workflow result for the bundled Matpower hybrid demo
    """
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[
            "files/case9.matpower",
            "files/case14.matpower",
            "files/case89pegase.matpower",
        ],
        test_file_names=["files/case14_ps.matpower"],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        window=24,
        steps=1500,
        default_hours_number=24,
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def run_external_same_grid_experiment_demo() -> AiPowerFlowWorkflowResult:
    """
    Run an experiment demo on one external IEEE39 time-series file.

    What this demo does:

    - uses the external grid in ``Grids_and_profiles/grids/IEEE39_1W.gridcal``
    - places that same file into train, validation, and test splits
    - enables testing plots

    Why this demo exists:

    - it preserves the older external-path workflow for comparison
    - it is useful when checking behavior against a file outside the bundled demo assets
    - it gives a split-structured version of the same-grid time-series workflow

    :returns: workflow result for the external same-grid experiment demo
    """
    grid_file_name: str = "files/IEEE39_1W.gridcal"
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[grid_file_name],
        validation_file_names=[grid_file_name],
        test_file_names=[grid_file_name],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def run_external_same_grid_hybrid_demo() -> AiPowerFlowWorkflowResult:
    """
    Run a hybrid demo on one external IEEE39 time-series file.

    What this demo does:

    - trains on the external IEEE39 time-series file
    - tests on that same file again
    - applies native solver refinement after the learned prediction

    Why this demo exists:

    - it preserves the older same-grid hybrid example in plain function form
    - it is useful for comparing the stronger learned solver against native refinement
    - it keeps an explicit example that points at an external grid path

    :returns: workflow result for the external same-grid hybrid demo
    """
    grid_file_name: str = "files/IEEE39_1W.gridcal"
    file_split: AiPowerFlowFileSplit = AiPowerFlowFileSplit(
        train_file_names=[grid_file_name],
        test_file_names=[grid_file_name],
    )
    training: AiPowerFlowTrainingConfiguration = AiPowerFlowTrainingConfiguration(
        steps=400,
        default_hours_number=1,
        use_cartesian_voltage_loss=True,
        w_branch_p=1.0,
        w_branch_q=0.5,
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
    result: AiPowerFlowWorkflowResult = run_workflow(request=request)
    print_workflow_result(result=result)
    return result


def main() -> None:
    """
    Run the default demo function for this module.

    The default is the bundled IEEE39 time-series train/test demo because it is
    the shortest realistic example and the best first target for debugging.

    :returns: ``None``
    """
    _ = run_ieee39_time_series_train_test_demo()


if __name__ == "__main__":
    # main()
    run_matpower_hybrid_demo()
