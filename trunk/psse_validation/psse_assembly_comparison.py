import VeraGridEngine as vg

files = [
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0100.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0200.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0300.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0400.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0500.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0600.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0700.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0800.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_0900.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1000.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1100.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1200.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1300.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1400.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1500.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1600.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1700.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1800.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_1900.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_2000.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_2100.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_2200.raw",
    "/home/santi/Descargas/Casos PSS-20260709T133221Z-2-001/Casos PSS/raw_collect_utf8/20260101_2300.raw",
]

grid_ts = vg.open_file(filename=files[0])
grid_ts.format_profiles2(nt=len(files))
main_elements_dict_by_type = grid_ts.build_main_elements_dict_by_type(use_secondary_key=True)
logger = vg.Logger()

for i, filename in enumerate(files):
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
