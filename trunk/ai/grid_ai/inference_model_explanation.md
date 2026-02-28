# Inference Model Explanation

This note explains what the new multi-grid approach means at inference time.

Short answer:

- yes, you still need a grid model at inference
- no, you do not need a separately trained neural network per grid

That distinction is the key architectural change.

## 1. Old Mental Model vs New Mental Model

### Old single-grid mental model

In the old style, the solver and the grid were effectively tied together:

- one trained model
- one fixed grid
- one fixed topology and indexing inside the model instance

That means the neural model itself was implicitly specialized to one electrical network.

### New multi-grid mental model

In the new style:

- one trained model
- many possible runtime grids

The trained object is now:

- a shared graph neural network with shared weights

The grid is now:

- a runtime input

So the new model is not:

- one model per grid

It is:

- one learned solver
- plus one grid description supplied at inference time

## 2. Why a Grid Model Is Still Required

Power flow is not defined without the network itself.

At inference, the solver must know:

- which buses exist
- which branches connect them
- what the branch impedances are
- what bus types exist
- which branches are active
- what the injections are
- what the slack/reference information is

Without that information, there is no power-flow problem to solve.

So a general-purpose neural power-flow solver can never mean:

- “infer voltages without being given the grid”

That would not be physically meaningful.

What it does mean is:

- “infer voltages for many different grids using the same trained weights”

## 3. What Is Shared and What Is Not

### Shared across all grids

The following is shared:

- the GNN weights
- the message-passing logic
- the learned voltage-correction behavior

This is the part that is trained once and reused.

### Supplied per inference case

The following changes for each grid:

- graph topology
- branch parameters
- bus shunts
- bus types
- branch availability
- active/reactive injections
- slack reference

This is the runtime problem definition.

So the inference contract is:

- fixed learned solver
- variable runtime electrical network

## 4. What the Runtime Grid Model Is in the Code

In the current implementation, the runtime grid model is represented by:

- `GraphSpec`

It contains:

- `from_bus`
- `to_bus`
- `r`
- `x`
- `b`
- `tap`
- `shift`
- `g_shunt_bus`
- `b_shunt_bus`
- `bus_type`
- `n_bus`
- `n_branch`

This object is the graph-level information the shared solver needs in order to operate on a particular network.

The graph is usually built from:

- a VeraGrid `MultiCircuit`

through:

- `build_graph_spec_from_multicircuit(...)`

## 5. What Else Is Needed Besides the Graph

The graph alone is not enough.

The solver also needs the operating condition.

At inference, the relevant runtime tensors are:

- `pinj`
- `qinj`
- `branch_active`
- `vref`

And optionally a time axis if you are solving a time window instead of one snapshot.

So there are really two kinds of runtime inputs:

### Static per-grid inputs

These do not change inside one dataset for one grid:

- topology
- branch parameters
- bus types
- shunts

### Dynamic per-time-step inputs

These can change from row to row:

- active/reactive injections
- branch active state
- slack/reference values

That distinction is central to the design.

## 6. Why This Is Better Than One Model Per Grid

The old “one model per grid” idea has several problems:

- it does not scale well
- every new grid needs retraining or fine-tuning
- it does not encourage transferable electrical reasoning
- it makes deployment awkward

The new approach is better because:

- the same learned correction logic is reused
- the graph structure is supplied explicitly
- the model can be trained across many cases
- adding a new grid does not require a new architecture

This is the main benefit of moving to a graph-agnostic GNN.

## 7. What “General Purpose” Actually Means

It does **not** mean:

- no grid required at inference
- no electrical metadata required
- no topology information required

It **does** mean:

- the same learned weights can operate on many different grids
- the solver is no longer frozen to one specific graph

So “general purpose” refers to:

- weight sharing across many grids

not to:

- removing the grid from the problem definition

## 8. Inference Pipeline in Practice

At inference, the intended flow is:

1. start from a `MultiCircuit`
2. compile `GraphSpec`
3. assemble the operating-point tensors:
   - `pinj`
   - `qinj`
   - `branch_active`
   - `vref`
4. pass them into the shared solver
5. obtain predicted voltages

If you use the hybrid path:

6. use the predicted voltages as a warm start for the native NR solver
7. refine the final solution

So the grid is still present all the way through inference.

## 9. What Can Be Precomputed Once Per Grid

For a given grid, these things can be compiled once and reused:

- `GraphSpec`
- branch feature tensors derived from the graph
- bus type masks
- topology-dependent indexing structures

These are static with respect to time.

This is useful because inference on multiple operating points for the same grid can reuse those graph-level artifacts.

## 10. What Changes Per Time Step

For a given grid, the main time-varying quantities are:

- active injections
- reactive injections
- branch active state
- reference/slack values

These define the actual operating scenario being solved.

That is why the dataset structure separates:

- one fixed graph
- one time-varying tensor collection

## 11. Same Grid vs New Grid Inference

There are two valid inference modes:

### Same-grid inference

Use a grid that resembles training or even is the same exact grid.

This is useful for:

- debugging
- model development
- same-grid post-training evaluation

### New-grid inference

Use a grid that the model did not see during training.

This is the real multi-grid use case.

The hope is:

- same learned solver
- new runtime `GraphSpec`
- acceptable generalization

But the grid is still always part of the runtime input.

## 12. What the New Demos Mean

The newer modules add stricter paths:

- `experiment_protocol.py`
- `hybrid_inference.py`

Those do not change the inference contract.

They still require:

- a runtime grid model
- runtime operating-point tensors

What they change is:

- clearer train/validation/test structure
- optional native refinement after GNN prediction

## 13. The Most Important Takeaway

The new approach does **not** eliminate the need for a grid model.

It eliminates the need for:

- one separately trained neural model per grid

So the correct statement is:

- inference requires a runtime grid model
- training no longer requires a separate neural solver for each grid

That is the architectural gain.

## 14. Compact Summary

At inference time:

- yes, you still provide the grid
- yes, you still provide the operating point
- no, you do not retrain the NN for each grid

The shared GNN is the reusable solver.
The `MultiCircuit`/`GraphSpec` is the runtime problem definition.
