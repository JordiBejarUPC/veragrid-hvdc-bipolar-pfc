import torch

from general_purpose_power_flow_gnn import GeneralPurposeTypedGNNSolver
from general_purpose_power_flow_gnn import MultiGridDataset
from general_purpose_power_flow_gnn import StatelessAcPowerFlowPhysics
from general_purpose_power_flow_gnn import load_multigrid_collection
from general_purpose_power_flow_gnn import train_general_purpose_solver
from hybrid_inference import HybridInferenceResult
from hybrid_inference import HybridRefinementConfig
from hybrid_inference import predict_and_refine_dataset_window


train_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
]

test_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal",
]

device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
dtype: torch.dtype = torch.float32

train_datasets: list[MultiGridDataset] = load_multigrid_collection(
    file_names=train_file_names,
    device=device,
    dtype=dtype,
    default_hours_number=1,
)

test_datasets: list[MultiGridDataset] = load_multigrid_collection(
    file_names=test_file_names,
    device=device,
    dtype=dtype,
    default_hours_number=1,
)

solver: GeneralPurposeTypedGNNSolver = GeneralPurposeTypedGNNSolver(
    embed_dim=64,
    msg_hidden=128,
    tgn_layers=6,
    msg_steps=2,
    dtype=dtype,
).to(device)

physics: StatelessAcPowerFlowPhysics = StatelessAcPowerFlowPhysics(dtype=dtype).to(device)

train_general_purpose_solver(
    solver=solver,
    physics=physics,
    datasets=train_datasets,
    window=96,
    steps=400,
    graphs_per_step=4,
    lr=1e-3,
    w_v=0.1,
    w_pf=1.0,
    verbose_every=50,
    seed=0,
)

refinement_config: HybridRefinementConfig = HybridRefinementConfig(
    max_iter=25,
    verbose=0,
)

hybrid_result: HybridInferenceResult = predict_and_refine_dataset_window(
    solver=solver,
    dataset=test_datasets[0],
    file_name=test_file_names[0],
    window=min(96, test_datasets[0].n_time),
    start_idx=0,
    default_hours_number=1,
    refinement_config=refinement_config,
)

print("\n[gnn_only]")
print(f"  voltage_mse={hybrid_result.gnn_metrics.voltage_mse:.6e}")
print(f"  vm_mse={hybrid_result.gnn_metrics.voltage_magnitude_mse:.6e}")

print("\n[gnn_plus_native_refinement]")
print(f"  voltage_mse={hybrid_result.refined_metrics.voltage_mse:.6e}")
print(f"  vm_mse={hybrid_result.refined_metrics.voltage_magnitude_mse:.6e}")
