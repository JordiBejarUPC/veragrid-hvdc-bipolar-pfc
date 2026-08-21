from pathlib import Path

from VeraGridEngine.IO.dgs.dgs_circuit import DgsCircuit


def main() -> None:
    """Parse an externally exported DGS without loading PowerFactory in Engine.

    :return: None.
    """
    dgs_path: Path = Path(__file__).resolve().parent / "IEEE_14.dgs"
    dgs_grid: DgsCircuit = DgsCircuit()
    dgs_grid.parse_dgs(path=str(dgs_path))
    print(f"Parsed dynamic roots: {len(dgs_grid.elmcomps)}")


if __name__ == "__main__":
    main()
else:
    pass
