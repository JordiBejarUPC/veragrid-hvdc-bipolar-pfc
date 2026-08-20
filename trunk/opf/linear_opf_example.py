import VeraGridEngine as vg

fname = "/home/santi/Escritorio/Demo NY grid/NY_activs.gridcal"

print("Loading...")
grid = vg.open_file(fname)

print("Running optimization...")
driver2 = vg.OptimalPowerFlowTimeSeriesDriver(
    grid=grid,
    options=vg.OptimalPowerFlowOptions(
        zonal_grouping=vg.ZonalGrouping.NoGrouping,
    ),
    engine=vg.EngineType.GSLV
)
driver2.run()

print("Done")
print(driver2.elapsed, "s")