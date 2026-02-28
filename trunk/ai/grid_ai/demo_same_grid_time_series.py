

from general_purpose_power_flow_gnn import main_multigrid_example

train_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal"
]

test_file_names: list[str] = [
    "/home/santi/Git/eRoots/VeraGrid/Grids_and_profiles/grids/IEEE39_1W.gridcal"
]

main_multigrid_example(
    train_file_names=train_file_names,
    test_file_names=test_file_names,
)