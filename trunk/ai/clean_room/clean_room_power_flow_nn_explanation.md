# Typed-GNN Power Flow Solver: NN Technology Overview

This note explains the neural-network technology used in [clean_room_power_flow.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/clean_room/clean_room_power_flow.py).

The implementation is not a generic deep-learning model. It is a graph neural network specialized for electric power networks and coupled to a deterministic AC power-flow physics layer.

## Short Description

The model is a:

- physics-informed graph neural network
- with typed nodes
- used as an unrolled iterative voltage solver

More precisely, it is a typed message-passing GNN that predicts bus-voltage corrections and uses an AC physics layer to evaluate whether those voltages satisfy the power-flow equations.

## Core Idea

The model does not directly learn the AC equations.

Instead:

1. the GNN proposes voltage updates
2. the physics layer evaluates the electrical consequences
3. training pushes the GNN toward voltage states that satisfy the network equations and match the target operating point

This is why the architecture is more accurate to describe as a learned solver than as a plain regressor.

## Main Components

### `SupersetGrid`

Defined in [clean_room_power_flow.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/clean_room/clean_room_power_flow.py).

This is the fixed graph artifact used by both the solver and the physics.

It stores:

- bus-to-branch connectivity
- branch electrical parameters
- bus shunts
- bus types

The important point is that the graph structure is explicit and physically meaningful. The network is not trying to infer topology from data.

### `AcPowerFlowPhysics`

This is the deterministic AC equation evaluator.

It takes:

- bus voltages `Vr`, `Vi`
- branch active mask

It computes:

- bus injections `P`, `Q`
- branch flows `Pf`, `Qf`, `Pt`, `Qt`
- mismatch terms when targets are provided

This module is not learned. It is fixed physics.

That matters because the NN is constrained by the actual electrical equations rather than being trained as a purely black-box predictor.

### `TypedGNNSolver`

This is the neural solver.

It receives:

- target active/reactive injections
- branch active states
- optional voltage reference tensor for the slack bus

It predicts:

- `Vr`
- `Vi`

Internally, it iteratively refines the voltage state through repeated message passing and voltage updates.

## Why It Is a Graph Neural Network

The power grid is naturally a graph:

- buses are nodes
- branches are edges

The solver uses this structure directly.

There are two learned update directions:

1. bus-to-branch
2. branch-to-bus

This is implemented with message-passing steps:

- `_bus_to_branch_update(...)`
- `_branch_to_bus_update(...)`

Each branch embedding is updated from its endpoint bus states, and each bus embedding is updated from the messages coming from incident branches.

This is the defining characteristic of a message-passing GNN.

## Why It Is "Typed"

Not all buses are treated the same.

The code explicitly distinguishes:

- slack buses
- PV buses
- PQ buses

This happens in two ways:

1. bus type is injected as a one-hot feature
2. update logic is masked based on bus type

Examples:

- slack buses do not receive learned voltage updates
- reactive mismatch handling is restricted according to bus type

So "typed" here is not cosmetic. It changes the solver dynamics.

## Why It Is "Unrolled"

The solver is not one forward pass from inputs to outputs.

It runs a loop over `tgn_layers`, and each layer does:

1. evaluate current electrical mismatch from physics
2. build bus features from the current state and target operating point
3. perform message passing on the graph
4. decode voltage corrections
5. update the voltage state

This is called unrolling because the network explicitly models multiple solver iterations inside one forward pass.

That makes it conceptually closer to a learned numerical method than to a conventional feedforward network.

## What the Network Actually Learns

The learned parts are the MLP-based encoders, updaters, and decoder:

- `enc_bus`
- `enc_branch`
- `upd_branch`
- `msg_br_to_bus`
- `upd_bus`
- `dec_dv`

These modules learn:

- how to encode bus state
- how to encode branch context
- how to propagate useful electrical information across the graph
- how to translate local and neighborhood information into voltage corrections

The network does not learn Ohm's law, branch admittance equations, or complex-power equations. Those remain in the physics module.

## Branch Features

Branches are not represented only by connectivity. They carry physically meaningful features derived from the line parameters:

- `rho = 1 / |z|`
- `delta = -atan2(x, r)`
- `b`

These are used to initialize branch embeddings.

That is a useful design choice because it gives the GNN a physically structured edge representation from the start.

## Bus Features

At each unrolled layer, the bus features include:

- current `Vr`
- current `Vi`
- current active mismatch `dP`
- current reactive mismatch `dQ`
- specified `Pinj`
- specified `Qinj`
- reference voltage magnitude
- reference voltage angle
- bus type one-hot vector

This is important because the network is not blind to the current numerical state. It sees both:

- where the current solution is
- how far it is from the specified injections

That is exactly what an iterative solver needs.

## Voltage Update Strategy

The solver works in Cartesian voltage coordinates:

- `Vr`
- `Vi`

The decoder outputs:

- `ΔVr`
- `ΔVi`

Then the voltage is updated with a learned step scale.

This means the GNN is learning a correction operator, not predicting the final solution in one shot.

## Physics-Informed Training

Training uses two kinds of signal:

1. direct voltage supervision
2. physics mismatch supervision

In the current code, the direct voltage term is based on voltage magnitude:

- `voltage_magnitude_loss(...)`

The physics term comes from the AC physics layer:

- mismatch between predicted bus injections and target injections

This hybrid objective is important.

A pure supervised model could fit voltages while violating electrical consistency.
A pure physics-only model could be harder to optimize and less stable during development.

The current implementation uses both.

## Why Batching Produces 3D Tensors

The original data layout is time-major:

- `(T, N)` for bus quantities
- `(T, M)` for branch quantities

During training, the code samples multiple windows and stacks them into batches:

- `(B, T, N)`
- `(B, T, M)`

Here:

- `B` = number of windows in the batch
- `T` = time steps inside each sampled window
- `N` = number of buses
- `M` = number of branches

The implementation handles this by flattening the leading dimensions and running the same electrical and graph operations on the flattened data.

This is an implementation technique. It does not change the underlying NN concept.

## What This Model Is Good At

This architecture is well suited to power-flow problems because:

- the domain is naturally graph-structured
- node and edge types matter
- the AC equations are known and can be enforced
- iterative correction is a natural way to solve power flow

So the model is aligned with the structure of the problem.

## What This Model Is Not

It is not:

- a transformer
- a recurrent sequence model in the usual sense
- a vanilla GCN doing one-shot graph regression
- a classical Newton-Raphson solver
- a standard PINN in the continuous-field sense

The closest practical description is:

"a typed message-passing GNN coupled to an AC physics evaluator and unrolled as a learned iterative power-flow solver."

## Practical Interpretation

At runtime, the model is effectively answering this question:

"Given the present voltage estimate, the desired injections, the network topology, branch availability, and bus-type constraints, what voltage correction should be applied next?"

That is the right mental model for the implementation.

## Important Engineering Consequence

Because the physics module is separate and deterministic, debugging has two clear layers:

1. the physics layer can be checked independently for equation correctness
2. the GNN can be checked for whether it learns useful correction dynamics

That separation is one of the strongest design choices in this code.

## Relevant Code Anchors

Key implementation points in [clean_room_power_flow.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/clean_room/clean_room_power_flow.py):

- `SupersetGrid`
- `AcPowerFlowPhysics`
- `TypedGNNSolver`
- `_bus_to_branch_update(...)`
- `_branch_to_bus_update(...)`
- `train_solver_with_windows(...)`
- `voltage_magnitude_loss(...)`

## Final Summary

The NN technology used here is a typed, physics-informed, message-passing graph neural network that is unrolled as an iterative voltage solver.

It learns how to update bus voltages on an electrical graph, while a fixed AC physics layer evaluates whether those updates are electrically consistent.
