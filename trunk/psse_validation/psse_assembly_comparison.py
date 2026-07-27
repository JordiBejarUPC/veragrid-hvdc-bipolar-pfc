import os
import VeraGridEngine as vg

folder = "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/"

files = [
    "20260101_0100.raw",
    "20260101_0200.raw",
    "20260101_0300.raw",
    "20260101_0400.raw",
    "20260101_0500.raw",
    "20260101_0600.raw",
    "20260101_0700.raw",
    "20260101_0800.raw",
    "20260101_0900.raw",
    "20260101_1000.raw",
    "20260101_1100.raw",
    "20260101_1200.raw",
    "20260101_1300.raw",
    "20260101_1400.raw",
    "20260101_1500.raw",
    "20260101_1600.raw",
    "20260101_1700.raw",
    "20260101_1800.raw",
    "20260101_1900.raw",
    "20260101_2000.raw",
    "20260101_2100.raw",
    "20260101_2200.raw",
    "20260101_2300.raw",
    "20260630_0030.raw",
    "20260630_0130.raw",
    "20260630_0230.raw",
    "20260630_0330.raw",
    "20260630_0430.raw",
    "20260630_0530.raw",
    "20260630_0630.raw",
    "20260630_0800.raw",
    "20260630_0900.raw",
    "20260630_1000.raw",
    "20260630_1030.raw",
    "20260630_1130.raw",
    "20260630_1230.raw",
    "20260630_1330.raw",
    "20260630_1430.raw",
    "20260630_1515.raw",
    "20260630_1615.raw",
    "20260630_1800.raw",
    "20260630_1815.raw",
    "20260630_1930.raw",
    "20260630_2030.raw",
    "20260630_2115.raw",
    "20260630_2245.raw",
    "20260630_2330.raw",
]

grid_ts = vg.open_file(filename=os.path.join(folder, files[0]))
grid_ts.format_profiles2(nt=len(files))
main_elements_dict_by_type = grid_ts.build_main_elements_dict_by_type(use_secondary_key=True)
logger = vg.Logger()

for i, name in enumerate(files):

    filename = os.path.join(folder, name)

    grid_i = vg.open_file(filename=filename)
    nc_i = vg.compile_numerical_circuit_at(circuit=grid_i, t_idx=None)

    grid_ts.assign_grid(
        t=i,
        grid_to_add=grid_i,
        main_elements_dict_by_type=main_elements_dict_by_type,
        use_secondary_key=True,
        logger=logger
    )

    nc_main = vg.compile_numerical_circuit_at(circuit=grid_ts, t_idx=i)

    ok, comparison_logger = nc_main.compare(nc_2=nc_i, by_idtag=True)
    ok_sums, sums_logger = nc_main.compare_sums(nc_2=nc_i)

    if not ok:
        comparison_logger.print(f"{filename}: FAILED")

    if not ok_sums:
        sums_logger.print(f"{filename}: SUMS FAILED")
