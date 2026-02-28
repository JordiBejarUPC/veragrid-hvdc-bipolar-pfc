from general_purpose_power_flow_gnn import main_multigrid_example

train_file_names: list[str] = [
    "files/case9.matpower",
    "files/case14.matpower",
    "files/case89pegase.matpower",
]

test_file_names: list[str] = [
    "files/case14_ps.matpower",
    "files/case24_ieee_rts.matpower",
    "files/case_ieee30.matpower",
]

main_multigrid_example(
    train_file_names=train_file_names,
    test_file_names=test_file_names,
    steps=1500,
    plot_testing=False,
    default_hours_number=24,
)
