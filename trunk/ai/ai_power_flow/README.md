# `ai_power_flow`

Package-style workspace for learned AC power-flow experiments on VeraGrid `MultiCircuit` models.

## Recommended entry points

The folder now has one clear public workflow API and one consolidated demo file.

### Public API

- [__init__.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/__init__.py)
- [api.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/api.py)

Import and run the package through:

```python
from trunk.ai.ai_power_flow import AiPowerFlowFileSplit
from trunk.ai.ai_power_flow import AiPowerFlowMode
from trunk.ai.ai_power_flow import AiPowerFlowTrainingConfiguration
from trunk.ai.ai_power_flow import AiPowerFlowWorkflowRequest
from trunk.ai.ai_power_flow import print_workflow_result
from trunk.ai.ai_power_flow import run_workflow

file_split = AiPowerFlowFileSplit(
    train_file_names=["files/case9.matpower", "files/case14.matpower"],
    test_file_names=["files/case14_ps.matpower"],
)

training = AiPowerFlowTrainingConfiguration(
    steps=400,
    default_hours_number=24,
)

request = AiPowerFlowWorkflowRequest(
    mode=AiPowerFlowMode.DIRECT,
    file_split=file_split,
    training=training,
)

result = run_workflow(request=request)
print_workflow_result(result=result)
```

### Demo

- [demo.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/demo.py)
- [__main__.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/__main__.py)

Use the demo module when you want one place that shows the supported use cases:

- bundled IEEE39 time-series train/test workflow
- direct train/test workflow
- explicit train/validation/test workflow
- hybrid GNN plus native-refinement workflow
- bundled Matpower examples
- same-grid time-series examples

The selected scenario lives in `demo.py` inside `main()`.

The main demo example is the bundled `files/IEEE39_1W.gridcal` case:

- train on `files/IEEE39_1W.gridcal`
- test on `files/IEEE39_1W.gridcal`
- use the grid's own time series instead of synthesizing snapshot repetitions

The default package entry point therefore exercises a real time-series workflow on one bundled grid file.

## Internal structure

### Core solver implementation

- [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/general_purpose_power_flow_gnn.py)

This file contains the actual solver and dataset machinery:

- graph representation
- VeraGrid-to-dataset conversion
- deterministic AC physics evaluation
- typed GNN solver
- training loop
- evaluation logic
- plotting helpers

### Structured evaluation helpers

- [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/experiment_protocol.py)

This file still contains explicit split-level evaluation utilities. The new package API uses these utilities instead of asking users to run this module directly.

### Hybrid refinement helpers

- [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/hybrid_inference.py)

This file contains the warm-start-plus-native-solver path. The new package API exposes it through the unified `HYBRID` workflow mode.

### Conservative augmentation scaffolding

- [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/ai_power_flow/data_augmentation.py)

This remains a typed place for dataset request expansion, but it is not the primary entry point.

## Supported workflow modes

The package API is organized around `AiPowerFlowMode`:

- `DIRECT`: train on a training split and evaluate on a testing split
- `EXPERIMENT`: train on a training split and evaluate on validation and testing splits
- `HYBRID`: train on a training split and refine the first testing dataset with the native solver

This is now the intended way to use the folder. The lower-level files remain available for model work and debugging, but the package API is the default top-level interface.
