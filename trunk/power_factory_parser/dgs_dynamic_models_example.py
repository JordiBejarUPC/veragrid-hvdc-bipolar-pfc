import VeraGridEngine as vg

fname = "NUACTIS_models_V2.dgs"
opt = vg.FileOpenOptions(
    dgs_dynamic_simulation_mode=vg.DynamicSimulationMode.RMS,
    dgs_use_vsc_for_injections=False,
    dgs_use_dynamic_information=True,
)
grid = vg.open_file(fname, options=opt)

print()
