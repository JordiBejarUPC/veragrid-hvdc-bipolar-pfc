# `grid_ai`

Multi-grid graph-neural-network power-flow workspace.

This folder contains a shared typed GNN that is trained across many runtime grids represented as VeraGrid `MultiCircuit` models.

The folder is organized around one core implementation file and several supporting files that each push the workflow in a different direction:

- one file defines the actual learned solver and its data path
- one file defines a stricter experiment structure
- one file defines a hybrid GNN + native-solver inference path
- one file defines typed augmentation scaffolding

So the important thing to understand is that these files are not redundant copies of each other.

They serve different levels of the workflow.

## Main Files

### [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py)

This is the central implementation file.

If you want to understand the actual model, this is the first file to read.

It contains the full baseline pipeline:

- runtime graph representation
- per-file dataset representation
- per-window training sample representation
- deterministic AC physics evaluation
- shared typed GNN solver
- conversion from VeraGrid `MultiCircuit` files into datasets
- multi-grid training loop
- post-training evaluation logic
- post-training plots
- one direct end-to-end example entry point

#### Approach followed by this file

This file follows the direct “train and evaluate the shared learned solver” approach.

That means:

- each input file is converted into a `MultiGridDataset`
- each dataset contains one fixed graph and one time-varying electrical trajectory
- training repeatedly samples windows from those datasets
- the same GNN weights are applied to many different graphs
- the deterministic AC physics block is used during training and evaluation

The solver itself is:

- graph-agnostic in weights
- graph-specific in runtime input

So this file is where the actual solver idea lives.

#### What makes it important

This file is the only one that really answers:

- what is the model?
- what are the inputs?
- what is the output?
- how does learning happen?

Everything else in the folder either wraps this file, extends this file, or organizes how this file is used.

#### What kind of workflow it supports

This file supports the simplest complete workflow:

1. give training file names
2. give testing file names
3. build datasets
4. train one shared solver
5. test it
6. plot test performance

That is why the direct demo scripts use it.

#### How it differs from the other main files

Compared with [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py):

- `general_purpose_power_flow_gnn.py` is the model and baseline runtime
- `experiment_protocol.py` is an experiment wrapper around it

Compared with [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py):

- `general_purpose_power_flow_gnn.py` stops at the learned solver output
- `hybrid_inference.py` takes that output and refines it with a native solver

Compared with [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py):

- `general_purpose_power_flow_gnn.py` defines how data is consumed
- `data_augmentation.py` defines how data requests may later be varied before consumption

#### When to use it

Use this file when:

- you want the main implementation
- you want the simplest end-to-end path
- you are debugging the model itself
- you do not yet need a formal train/validation/test experiment layer

### [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py)

This file is not a different model.

It is a stricter orchestration layer around the main model.

Its job is to make experiments explicit and defensible.

It introduces:

- explicit file split objects
- explicit hyper-parameter objects
- explicit dataset collections
- explicit split-wise evaluation summaries
- one full experiment runner

#### Approach followed by this file

This file follows the “structured experiment” approach.

Instead of simply:

- train on some files
- evaluate on some files

it makes the experiment structure explicit through typed objects:

- training split
- validation split
- testing split

Algorithmically, the model is still the same.

What changes is the discipline of how the experiment is run and reported.

#### Why it exists

Once a multi-grid model starts being used seriously, the main problem is no longer just “can it run?”

The harder problem becomes:

- are the reported results honest?
- are we evaluating on seen data or unseen data?
- are we mixing validation and testing accidentally?

This file exists to prevent the folder from collapsing into ad-hoc scripts with unclear experimental meaning.

#### What it does that the main file does not

The main file already supports explicit train/test usage, but it is still a direct workflow file.

This experiment-protocol file goes further by making:

- the split definition explicit
- the collections explicit
- the reporting structure explicit

That means it is the right place to grow toward:

- repeatable experiments
- validation-driven model selection
- comparable train/validation/test reports

#### How it differs from the other main files

Compared with [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py):

- this file does not define a new solver
- it defines a cleaner way to run the solver

Compared with [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py):

- this file is about experiment structure
- the hybrid file is about inference refinement

Compared with [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py):

- this file assumes the datasets already exist
- the augmentation file is about how input dataset requests may be expanded or tagged

#### When to use it

Use this file when:

- you want a real train/validation/test workflow
- you want clearer experimental semantics
- you want to compare runs more honestly

### [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py)

This file takes a different view of what the GNN should do.

Instead of asking the GNN to be the final solver, it asks the GNN to be:

- a warm-start generator for a conventional power-flow solver

This is a major conceptual difference.

#### Approach followed by this file

This file follows the hybrid-solver approach:

1. the GNN predicts a voltage state
2. that predicted voltage is injected as the initial guess
3. VeraGrid’s native NR-style power-flow machinery refines the solution

So the hybrid file is not about replacing physics with learning.

It is about:

- using learning to accelerate or stabilize physics-based solving

#### Why this approach matters

This is often the most practical way to use learned solvers in engineering systems.

Pure learned inference can be:

- fast
- expressive

but it can also be:

- brittle on unseen grids
- slightly off on the final physical residual

The hybrid approach tries to get the best of both worlds:

- the GNN gives a strong initial guess
- the native solver restores hard physical convergence behavior

#### What this file contains

It defines typed objects for:

- the GNN warm-start result
- the native refinement result
- the combined hybrid result
- the native refinement configuration

It also defines the procedural path to:

- predict a voltage window with the GNN
- refine one snapshot with native power flow
- refine a whole window snapshot by snapshot
- compare the GNN-only result against the refined result

#### How it differs from the other main files

Compared with [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py):

- the core file stops at learned prediction
- this file adds a native post-processing refinement stage

Compared with [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py):

- experiment protocol is about split structure and evaluation discipline
- hybrid inference is about a different inference strategy

Compared with [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py):

- hybrid inference changes what happens after prediction
- augmentation changes how training data requests may be varied

#### When to use it

Use this file when:

- you want to test GNN warm-start + native solver refinement
- you care about robustness more than pure end-to-end learned prediction
- you want to compare:
  - GNN-only
  - GNN+NR

### [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py)

This file is currently the most forward-looking of the four main files.

It does not yet implement a large library of physical perturbations.

Instead, it introduces typed objects that define:

- what an augmentation request is
- how datasets may be requested with augmentation metadata
- how those requests are materialized into loaded dataset entries

#### Approach followed by this file

This file follows the “typed augmentation interface first” approach.

That means it prefers:

- explicit augmentation request objects
- explicit tags and metadata
- conservative loading behavior

instead of immediately introducing many label-sensitive perturbations.

This is a deliberate design choice.

The wrong way to do augmentation in a physics problem is:

- perturb the inputs casually
- keep old labels
- silently create inconsistent training targets

This file avoids that.

#### Why it exists even though augmentation is still limited

Because augmentation changes the shape of the training system, not just one function call.

If augmentation is going to become serious later, the folder needs:

- typed request objects
- a place to record augmentation semantics
- a safe loading path

This file provides that base.

#### What it currently does

It currently supports:

- typed dataset requests
- replication-style request expansion
- typed augmented dataset entries

So today it is mostly:

- metadata and interface scaffolding

not yet:

- a mature augmentation engine

#### How it differs from the other main files

Compared with [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py):

- the core file consumes datasets
- this file helps define how dataset requests may later be varied

Compared with [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py):

- experiment protocol is about splits and evaluation
- augmentation is about shaping the training corpus itself

Compared with [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py):

- hybrid inference acts after the model predicts
- augmentation acts before training samples are even created

#### When to use it

Use this file when:

- you want to start building an explicit augmentation workflow
- you want typed augmentation requests instead of loose flags
- you are preparing for richer data-generation pipelines

## How The Four Main Files Fit Together

The cleanest way to think about the four main files is:

1. [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py)
   - defines the actual solver and baseline data path
2. [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py)
   - defines how to run proper train/validation/test experiments with that solver
3. [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py)
   - defines how to refine the solver’s prediction with a native solver
4. [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py)
   - defines the typed base for future augmentation pipelines

So the relationship is:

- core solver
- experiment structure
- hybrid inference strategy
- augmentation interface

not:

- four competing model implementations

## Demos

- [demo_same_grid_time_series.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series.py)
  - simplest same-grid path
- [demo_matpower_files.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files.py)
  - simplest multi-file path
- [demo_same_grid_time_series_experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series_experiment_protocol.py)
  - same-grid path with explicit train/validation/test structure
- [demo_matpower_files_experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files_experiment_protocol.py)
  - multi-file path with explicit train/validation/test structure
- [demo_same_grid_time_series_hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series_hybrid_inference.py)
  - same-grid GNN warm-start + native refinement
- [demo_matpower_files_hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files_hybrid_inference.py)
  - multi-file GNN warm-start + native refinement

## Documentation

- [grid_ai_folder_guide.md](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/grid_ai_folder_guide.md)
  - folder-level guide, theory, file-by-file explanation, demos, current test story
- [general_purpose_power_flow_gnn_explanation.md](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn_explanation.md)
  - detailed explanation of the main model and algorithm
- [inference_model_explanation.md](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/inference_model_explanation.md)
  - explains what is shared vs runtime-specific at inference

## Recommended Entry Points

Use:

1. [demo_same_grid_time_series.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series.py)
   - if you want the simplest end-to-end debug path
2. [demo_matpower_files.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files.py)
   - if you want the simplest multi-file training/testing path
3. [demo_matpower_files_experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files_experiment_protocol.py)
   - if you want a cleaner experiment structure
4. [demo_matpower_files_hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files_hybrid_inference.py)
   - if you want to test GNN warm-start plus native refinement

## Which File Should You Touch First?

If you want to modify:

### The model itself

Start with:

- [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py)

Typical changes:

- graph features
- message passing
- losses
- dataset conversion
- training behavior

### The experiment structure

Start with:

- [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py)

Typical changes:

- new split semantics
- validation logic
- reporting structure

### The inference strategy

Start with:

- [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py)

Typical changes:

- warm-start behavior
- native solver refinement options
- comparison metrics

### The data growth strategy

Start with:

- [data_augmentation.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/data_augmentation.py)

Typical changes:

- dataset request types
- augmentation request expansion
- future perturbation pipelines

## Current Test Status

This folder currently relies mainly on:

- `python3 -m py_compile ...`
- demo execution as integration-style validation

There is not yet a dedicated `tests/` suite in this folder.
