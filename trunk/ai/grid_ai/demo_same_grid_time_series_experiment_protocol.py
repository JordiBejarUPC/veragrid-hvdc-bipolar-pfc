from experiment_protocol import ExperimentHyperParameters
from experiment_protocol import ExperimentRunResult
from experiment_protocol import FileSplit
from experiment_protocol import SplitEvaluationSummary
from experiment_protocol import run_experiment_protocol


train_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
]

validation_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
]

test_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
]

file_split: FileSplit = FileSplit(
    train_file_names=train_file_names,
    validation_file_names=validation_file_names,
    test_file_names=test_file_names,
)

hyper_parameters: ExperimentHyperParameters = ExperimentHyperParameters(
    embed_dim=64,
    msg_hidden=128,
    tgn_layers=6,
    msg_steps=2,
    window=96,
    steps=400,
    graphs_per_step=4,
    lr=1e-3,
    w_v=0.1,
    w_pf=1.0,
    verbose_every=50,
    default_hours_number=1,
)

result: ExperimentRunResult = run_experiment_protocol(
    file_split=file_split,
    hyper_parameters=hyper_parameters,
    plot_validation=False,
    plot_testing=True,
)

split_summary: SplitEvaluationSummary
for split_summary in [result.validation_summary, result.test_summary]:
    print(f"\n[{split_summary.split_name}]")
    dataset_summary_idx: int
    for dataset_summary_idx in range(len(split_summary.dataset_summaries)):
        dataset_summary = split_summary.dataset_summaries[dataset_summary_idx]
        print(
            f"  {dataset_summary.dataset_name}: "
            f"voltage_mse={dataset_summary.metrics.voltage_mse:.6e}  "
            f"vm_mse={dataset_summary.metrics.voltage_magnitude_mse:.6e}  "
            f"pf_mismatch={dataset_summary.metrics.pf_mismatch:.6e}"
        )
