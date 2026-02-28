# General-Purpose Power Flow GNN: Theory, Implementation, and Demo Guide

This document explains the module [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py) from first principles down to the concrete execution flow used by the demo files:

- [demo_matpower_files.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_matpower_files.py)
- [demo_same_grid_time_series.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series.py)

The goal is to make the global design explicit:

1. what problem the model is solving
2. why a graph neural network is being used
3. how the power-system theory maps into the code
4. how a `MultiCircuit` becomes training data
5. how training and testing are actually executed

## 1. Problem Statement

We want one learned model that can operate on many different electrical grids instead of being hard-wired to one specific topology.

The target problem is:

- input:
  - one electrical network
  - one operating condition on that network
  - branch availability
  - bus power injections
  - slack/reference information
- output:
  - the bus voltage state that satisfies the AC power-flow equations

The important design goal is that the same learned weights should work across many grids.

That is why the module is called "general purpose" in the sense of:

- one shared solver
- many graph topologies
- many operating points

It is not a universal solver for arbitrary unsupported device models. It is a general-purpose solver within the supported AC grid family represented by the code.

## 2. Why a Graph Neural Network

Power systems are naturally graphs:

- buses are nodes
- branches are edges

A graph neural network is a natural choice because:

- it can operate on variable topologies
- it can share the same parameters across many graphs
- it can propagate information locally across the network structure
- it does not require one fixed bus count or one fixed branch count

That last point is the key difference from a plain dense neural network.

A standard MLP would force all training cases into one fixed-size input layout. That is not a good fit for multi-grid learning.

## 3. Why This Is Not Just a Black-Box GNN

This module is not trying to learn physics from scratch.

It combines two parts:

1. a learned typed graph neural network
2. a deterministic AC power-flow physics evaluator

The learned part proposes voltage corrections.

The physics part evaluates what those voltages imply electrically:

- bus injections
- branch flows
- active/reactive mismatch

So the network is not free to invent arbitrary outputs. It is constantly checked against the AC equations.

This is why the model is better described as:

- a physics-informed typed GNN
- used as a learned iterative solver

rather than a pure supervised graph regressor.

## 4. Power-Flow Theory Behind the Design

The AC power-flow problem is fundamentally about finding a voltage state:

- `V = Vr + j Vi`

such that the network equations match the specified operating point.

At each bus, we care about:

- active power injection `P`
- reactive power injection `Q`
- voltage magnitude and angle

At each branch, we care about:

- branch admittance
- tap ratio and phase shift
- branch-end power flows

The classical numerical solver viewpoint is:

1. start from an initial voltage guess
2. compute mismatch between requested and implied power injections
3. update the voltage state
4. repeat until mismatch is small

This module keeps exactly that high-level structure, but replaces the hand-designed correction step with a learned graph-based correction step.

## 5. Why the Solver Is "Typed"

Not all buses behave the same way in power flow.

The code reduces bus control behavior into three categories:

- slack
- PV-like
- PQ-like

This matters because:

- slack buses are voltage-prescribed reference buses
- PV buses have a different control role than PQ buses
- the solver should not update all buses in the same way

In the code, bus type affects both:

- the features given to the network
- the update masks used during mismatch correction

So "typed" is not just a label. It changes the actual solver dynamics.

## 6. High-Level Architecture

The implementation has five conceptual layers:

1. graph representation
2. dataset representation
3. deterministic physics
4. learned GNN solver
5. multi-grid train/test orchestration

Those correspond to the following objects and functions:

- `GraphSpec`
- `MultiGridDataset`
- `MultiGridWindow`
- `StatelessAcPowerFlowPhysics`
- `GeneralPurposeTypedGNNSolver`
- `build_multigrid_dataset_from_veragrid(...)`
- `load_multigrid_collection(...)`
- `train_general_purpose_solver(...)`
- `evaluate_general_purpose_solver_on_dataset(...)`
- `plot_testing_performance(...)`
- `main_multigrid_example(...)`

## 7. Graph Representation

The graph representation lives in `GraphSpec`.

It contains:

- topology:
  - `from_bus`
  - `to_bus`
- branch electrical parameters:
  - `r`
  - `x`
  - `b`
  - `tap`
  - `shift`
- bus shunts:
  - `g_shunt_bus`
  - `b_shunt_bus`
- bus categories:
  - `bus_type`
- explicit dimensions:
  - `n_bus`
  - `n_branch`

Why this object exists:

- the graph must be explicit and immutable
- the same graph is reused across many time steps
- the solver should receive graph structure as runtime input
- the model weights must not be tied to one one-off topology

This is the main architectural difference from the earlier single-grid clean-room design.

## 8. Dataset Representation

The dataset object is `MultiGridDataset`.

One `MultiGridDataset` means:

- one input file
- one fixed graph
- one time series of solved operating states on that graph

It stores:

- `vr_true`
- `vi_true`
- `vref`
- `pinj`
- `qinj`
- `branch_active`
- `time_array`

Conceptually:

- `graph` is the static electrical network
- the tensor fields are the time-varying state that lives on that network

This is important because training is not performed directly on the full dataset object.

Instead, training repeatedly samples `MultiGridWindow` objects from it.

## 9. Window Representation

`MultiGridWindow` is the actual per-step training example.

It contains:

- one graph
- one contiguous time slice on that graph

That means:

- topology is fixed inside the window
- operating state varies across time rows inside the window

Why windows are used:

- they increase the number of training examples per file
- they reduce memory use
- they let the solver see local operating trajectories
- they support both time-series training and single-snapshot training

For single-snapshot grids:

- the only valid window is the full one-row trajectory
- the code explicitly supports `T = 1`

## 10. Snapshot and Time-Series Support

The current code supports two data regimes:

1. real time series
2. snapshot systems with one operating point

The snapshot fallback is implemented in `build_multigrid_dataset_from_veragrid(...)`.

If the grid has no time series:

- `grid.create_profiles(...)` is called
- the number of generated identical time steps is controlled by `default_hours_number`

This means the same training pipeline can be used on:

- a real time series with many points
- a single solved snapshot repeated into a tiny profile

Algorithmically, this keeps the training interface uniform.

## 11. Dataset Construction Pipeline

`build_multigrid_dataset_from_veragrid(...)` is the key data-construction function.

Its stages are:

1. load a file as a `MultiCircuit`
2. if needed, create a synthetic time axis for snapshot grids
3. run `vg.power_flow_ts(grid)`
4. compile the graph at one snapshot
5. extract time-varying arrays:
  - solved voltages
  - solved injections
  - branch active states
  - `Vbus` reference/guess
6. filter invalid or non-converged rows
7. gauge-fix the voltage reference frame
8. build a slack-only `vref`
9. move everything to torch tensors
10. package into `MultiGridDataset`

Why each step matters:

### Load and solve

The network must be trained against solved electrical states, not arbitrary synthetic labels.

### Compile the graph once

The graph structure is the invariant object for the dataset.

### Extract time-varying tensors

These are the supervision signals and runtime inputs for the learned solver.

### Filter invalid rows

Bad rows must be removed before training; otherwise the optimizer would be pushed toward meaningless states.

### Gauge fixing

Global voltage angle is not physically identifiable in the way the model should learn it.

So the code rotates the trajectories so the reference bus has zero angle.

### Slack-only `vref`

The solver should know prescribed voltages only where the power-flow formulation says they are prescribed.

So the code carries only slack-bus reference values into `vref`.

## 12. Physics Layer

The deterministic physics evaluator is `StatelessAcPowerFlowPhysics`.

Internally it calls `evaluate_ac_power_flow(...)`.

What it does:

- receives:
  - `GraphSpec`
  - `Vr`
  - `Vi`
  - branch activity mask
  - optional target `P/Q`
- computes:
  - branch currents
  - branch-end powers
  - bus injection currents
  - bus powers
  - optional mismatch

Algorithmic role:

- this is the electrical oracle
- it defines what the current voltage state means physically
- it tells the learned solver how wrong the current state still is

Without this layer, the network would only be doing pattern fitting. With it, the model is tied to the actual AC equations.

## 13. Learned Solver

The learned solver is `GeneralPurposeTypedGNNSolver`.

It is graph-agnostic because:

- the weights are shared
- the graph is passed at runtime

The solver performs an unrolled iterative procedure.

Each unrolled layer does:

1. evaluate the current voltage state with exact physics
2. compute active/reactive mismatch
3. build per-bus features
4. run graph message passing
5. decode a voltage correction
6. update the voltage state
7. re-apply slack reference constraints

This is the core algorithm.

## 14. Bus Features Used by the Solver

At each learned iteration, the solver builds bus features from:

- current `Vr`
- current `Vi`
- active mismatch
- reactive mismatch
- target `Pinj`
- target `Qinj`
- reference voltage magnitude
- reference voltage angle
- one-hot bus type

Why this is sensible:

- the solver needs the current state
- it needs the current error signal
- it needs the desired operating point
- it needs bus control semantics

This gives each bus enough local context before graph propagation starts.

## 15. Branch Features Used by the Solver

Branch features are not arbitrary learned IDs.

They are derived from the physical branch parameters:

- `rho = 1 / sqrt(r^2 + x^2)`
- `delta = -atan2(x, r)`
- `b`

Why this matters:

- the model should generalize across graphs
- branch identity should not matter
- branch electrical behavior should matter

This is one of the main reasons the model can plausibly generalize better than a network that only sees graph connectivity.

## 16. Message Passing Logic

The solver alternates two updates:

### Branch update

Each branch embedding is updated from:

- its current branch embedding
- the embedding of its from-bus
- the embedding of its to-bus

Why:

- a branch is defined by the state of the two buses it connects

### Bus update

Each bus aggregates messages from its incident branches.

Why:

- bus voltage should react to surrounding network structure
- local state alone is not enough

This is exactly the graph-neural-network part of the method.

## 17. Voltage Update Logic

The solver decodes:

- `Delta Vr`
- `Delta Vi`

and applies them with a learned step scale.

Why Cartesian voltage updates:

- they are numerically convenient
- they match the current code path
- the physics layer can still evaluate the exact AC equations from them

Why a learned step scale:

- the network needs a controlled iterative correction size
- too large is unstable
- too small stalls convergence

## 18. Why the Physics Is Inside the Unrolled Loop

This is a critical design choice.

The physics evaluator is called at each solver layer, not only at the end.

Why:

- each learned iteration needs a fresh mismatch signal
- the next correction should depend on the current physical state
- this mirrors how a numerical solver repeatedly recomputes residuals

So the network is not doing:

- one big prediction from inputs to voltages

It is doing:

- repeated learned corrections driven by up-to-date physics residuals

## 19. Training Theory

The training loop is `train_general_purpose_solver(...)`.

The optimizer step is built like this:

1. choose several datasets from the training collection
2. from each chosen dataset, sample one window
3. run the same shared solver on each sampled graph/window pair
4. compute:
  - voltage-magnitude supervision loss
  - power-flow mismatch loss
5. average losses across the sampled graph windows
6. update the shared solver weights

Why this matters:

- one step sees several different graphs
- the shared weights are constantly forced to work across topologies
- this is the main mechanism that encourages cross-grid generalization

## 20. Losses Used During Training

Two losses are combined:

### Voltage magnitude loss

This compares predicted and target `|V|`.

Why:

- it provides direct supervision from the solved dataset
- it is more stable than raw Cartesian supervision across reference-frame issues

### Power-flow mismatch loss

This uses the physics evaluator to compare:

- predicted bus injections
- requested bus injections

Why:

- it keeps the learned solution physically meaningful
- it penalizes electrically inconsistent predictions

The combined loss means:

- match the solved state
- but also satisfy the underlying AC equations

## 21. Train vs Test in the Current Example

The example entry point is `main_multigrid_example(...)`.

It now clearly separates:

1. training dataset construction
2. testing dataset construction
3. training stage
4. testing stage

This is true even if:

- `train_file_names`
- `test_file_names`

are the same list.

In that case:

- the code still has a separate training stage and separate testing stage
- but it is not a true unseen-grid generalization experiment

That distinction is important.

## 22. Testing and Post-Training Evaluation

Testing is handled by:

- `evaluate_general_purpose_solver_on_dataset(...)`
- `plot_testing_performance(...)`

The evaluation function:

- picks one window from the testing dataset
- runs the trained solver
- evaluates the predicted state
- returns:
  - scalar metrics
  - predicted voltages
  - physics evaluation

The plotting function then visualizes:

- voltage magnitude error per selected bus
- RMS voltage error
- RMS `Delta P` and `Delta Q`
- branch active-power flow comparison

Algorithmically, those plots answer:

1. did the solver recover the target voltage state?
2. did the predicted state satisfy the requested injections?
3. did it reproduce branch-level flow behavior?

## 23. Demo: `demo_same_grid_time_series.py`

This demo uses:

- the same `.gridcal` file for training and testing

Specifically:

- train list contains `IEEE39_1W.gridcal`
- test list also contains `IEEE39_1W.gridcal`

What this demo is good for:

- verifying the end-to-end pipeline
- debugging model behavior on one known grid
- checking that training and testing stages are wired correctly

What it is not:

- a genuine cross-grid generalization experiment

It is best understood as:

- same-grid post-training evaluation

## 24. Demo: `demo_matpower_files.py`

This demo uses separate train/test file lists.

Training files:

- `case9.matpower`
- `case14.matpower`
- `case89pegase.matpower`

Testing files:

- `case14_ps.matpower`
- `case24_ieee_rts.matpower`
- `case_ieee30.matpower`

It also passes:

- `steps=1500`
- `plot_testing=False`
- `default_hours_number=24`

What this demo is showing:

- a more realistic cross-file training setup
- separate training and testing corpora
- snapshot-style cases expanded into 24 repeated steps when no time series exists

Why `default_hours_number=24` matters:

- many static MATPOWER-style cases have no true time series
- the current pipeline expects a time axis
- this argument creates a simple repeated profile so the same pipeline can still run

This is a practical bridge, not a claim that the case really has 24 distinct operating points.

## 25. What "General Purpose" Means Here

In this implementation, "general purpose" means:

- one shared learned solver
- many graphs
- many operating conditions
- explicit graph runtime input

It does not mean:

- support for arbitrary unsupported device types
- support for every possible power-system formulation
- guaranteed zero-shot success on any unseen network

The model is general-purpose within the family encoded by:

- the supported VeraGrid compilation path
- the supported clean-room AC assumptions
- the typed bus treatment

## 26. Why the Current Implementation Is Conservative

The code intentionally avoids early packed heterogeneous batching.

Instead:

- one optimizer step samples several graph windows
- each graph window is solved explicitly
- the losses are accumulated

Why this is a good first design:

- variable graph sizes stay explicit
- indexing bugs are easier to catch
- the graph-to-window-to-loss path is easy to inspect

This is slower than a more aggressively packed implementation, but clearer and safer as a base architecture.

## 27. Current Strengths

The current design gets several important things right:

- explicit graph runtime input
- explicit separation between graph and time-varying state
- deterministic physics layer
- typed solver behavior
- multi-grid training loop
- snapshot compatibility
- explicit train/test dataset construction
- post-training testing plots

These are the right structural ingredients for a serious multi-grid learned solver.

## 28. Current Limitations

The current implementation is still a base version.

Important limitations:

### No true packed heterogeneous batching

The code evaluates graph windows one by one inside each optimizer step.

### No formal dataset split manager

Train/test splits are passed manually.

### Snapshot expansion is simplistic

If there is no time series, the code repeats the same operating condition for `default_hours_number` steps.

### No checkpointing or experiment management

The code is still a research/development scaffold, not a full training framework.

### Generalization is not guaranteed

True cross-grid performance still depends on:

- data diversity
- supported device family
- hyperparameters
- loss balance

## 29. End-to-End Lifecycle

The full lifecycle is:

1. user provides training file names and testing file names
2. each file is loaded as a VeraGrid `MultiCircuit`
3. each file is solved as a time series
4. each file becomes one `MultiGridDataset`
5. training repeatedly samples `MultiGridWindow` examples from the training datasets
6. the shared solver predicts voltages for each sampled window
7. the physics block evaluates the predicted voltages
8. losses are accumulated and weights are updated
9. after training, testing datasets are evaluated in the same runtime path
10. metrics and plots describe post-training performance

That is the central operational story of the module.

## 30. Minimal Usage Pattern

The simplest pattern is:

```python
from general_purpose_power_flow_gnn import main_multigrid_example

train_file_names = [
    "files/case9.matpower",
    "files/case14.matpower",
]

test_file_names = [
    "files/case24_ieee_rts.matpower",
]

main_multigrid_example(
    train_file_names=train_file_names,
    test_file_names=test_file_names,
    steps=1500,
    plot_testing=True,
    default_hours_number=24,
)
```

Conceptually, that does:

- build training datasets
- build testing datasets
- train one shared solver
- test and plot on the testing datasets

## 31. Final Summary

The module implements a graph-agnostic, physics-informed, typed GNN that acts as a learned AC power-flow solver across many `MultiCircuit` models.

Its core principles are:

- explicit graph representation
- explicit dataset/window separation
- learned message-passing voltage correction
- deterministic AC physics evaluation
- multi-grid shared-weight training
- explicit post-training testing

The two demos show two distinct modes:

- same-grid post-training evaluation
- cross-file train/test evaluation

That is the correct way to understand both the theory and the implementation as they currently exist.
