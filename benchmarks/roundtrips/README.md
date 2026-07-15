# Roundtrip Benchmarks

This folder contains file-format roundtrip benchmarks built from VeraGrid's own regression fixtures.

Current benchmark groups:

- `cim/opendss`: plain CIM fixtures exercised against OpenDSS-style imports and VeraGrid CIM export
- `raw/psse`: PSS/E RAW and RAWX roundtrips
- `matpower`: MATPOWER roundtrips
- `ucte`: UCTE roundtrip
- `cgmes`: CGMES 2.4.15 roundtrip with boundary set

## System setup

Use the same Python environment you use to run `VeraGridEngine` locally. The scripts expect:

- Python 3
- VeraGrid dependencies installed
- execution from the repository root

Example:

```bash
cd /home/santi/Git/eRoots/VeraGrid
python3 benchmarks/roundtrips/run_all.py
```

## Individual runs

```bash
python3 benchmarks/roundtrips/cim/opendss/run_all.py
python3 benchmarks/roundtrips/raw/psse/run_raw_roundtrip.py
python3 benchmarks/roundtrips/matpower/run_matpower_roundtrip.py
python3 benchmarks/roundtrips/ucte/run_ucte_roundtrip.py
python3 benchmarks/roundtrips/cgmes/run_cgmes_roundtrip.py
```

## What each benchmark checks

- `cim/opendss`: power-flow roundtrip compatibility for the included plain CIM cases
- `matpower` and `ucte`: bus-voltage and branch-flow preservation after export and re-import
- `raw/psse` and `cgmes`: numerical-circuit equivalence after export and re-import

Generated export artifacts are intentionally kept next to each benchmark so the input and output files stay together.
