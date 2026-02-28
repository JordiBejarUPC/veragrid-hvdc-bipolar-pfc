# `trunk/ai/grid_ai` Folder Guide

This document explains the purpose of the files in `trunk/ai/grid_ai`, the theory behind the approach, and what currently serves as demos and tests.

The folder is centered around one idea:

- train one shared graph neural network to solve AC power-flow problems across many grids

This is not a single-grid model folder. It is the beginning of a multi-grid learning framework.

## 1. Folder Purpose

The folder contains:

- the main graph-based power-flow model
- supporting experiment utilities
- hybrid GNN + native solver refinement utilities
- typed augmentation scaffolding
- example/demo scripts
- reference literature
- explanatory Markdown documents

So the folder is both:

- implementation code
- research/development documentation

## 2. Core Theory

The theoretical basis is:

1. power systems are graphs
2. power flow is an iterative constrained physical problem
3. a graph neural network can learn voltage-correction behavior
4. a deterministic physics block can enforce electrical consistency

The model family in this folder is therefore:

- a typed graph neural network
- coupled to an AC power-flow physics evaluator
- trained across multiple `MultiCircuit` models

The target is not:

- “predict anything without the grid”

The target is:

- “reuse one learned solver across many runtime grids”

## 3. Main Architectural Idea

The most important design change relative to the older clean-room single-grid path is:

- the grid is no longer embedded permanently inside one model instance

Instead:

- one shared neural network is trained
- each inference/training sample provides its own runtime graph

So:

- weights are shared
- grids vary

This is the correct architecture if the goal is a reusable multi-grid solver.

## 4. File-by-File Guide

### `general_purpose_power_flow_gnn.py`

This is the main implementation file.

It contains:

- the runtime graph struct
- the dataset structs
- the deterministic AC physics evaluator
- the shared typed GNN solver
- dataset builders from VeraGrid files
- training loop
- testing/evaluation logic
- testing plots
- one direct end-to-end example entry point

This file is the operational core of the folder.

If someone asks:

- “where is the actual model?”

the answer is:

- `general_purpose_power_flow_gnn.py`

### `experiment_protocol.py`

This file adds a stricter experiment structure on top of the core model.

It contains:

- explicit train/validation/test split structs
- explicit split dataset construction
- validation/test evaluation utilities
- one experiment runner

Its purpose is to make experiments honest and reproducible.

This file is about:

- experiment orchestration

not about:

- new model architecture

### `hybrid_inference.py`

This file adds a hybrid inference path.

It contains:

- a GNN warm-start prediction stage
- a native power-flow refinement stage
- typed result structs for the hybrid workflow

The idea is:

1. use the GNN to predict a voltage state
2. inject that voltage into the native VeraGrid/NR initialization
3. refine with the conventional solver

This file is about:

- robustness
- warm-starting
- hybrid solver behavior

This is one of the most practical directions in the folder.

### `data_augmentation.py`

This file is augmentation scaffolding.

It currently contains:

- typed augmentation request structs
- typed dataset request collections
- conservative loading interfaces

Important current limitation:

- it does not yet implement aggressive physical perturbation pipelines

So right now it is:

- an explicit typed augmentation interface

not yet:

- a full augmentation engine

This file exists so augmentation can be added later without redesigning the whole pipeline.

### `demo_matpower_files.py`

This is the simplest MATPOWER-style demo using the direct main entry point in the core file.

It:

- defines train file names
- defines test file names
- calls `main_multigrid_example(...)`

This is the simplest demonstration path for cross-file use.

### `demo_same_grid_time_series.py`

This is the simplest same-grid time-series demo using the direct main entry point.

It:

- uses the same `.gridcal` file for train and test
- calls `main_multigrid_example(...)`

This is useful for:

- debugging
- same-grid post-training evaluation

It is not a true unseen-grid test.

### `demo_matpower_files_experiment_protocol.py`

This demo replicates the MATPOWER-style example using the stricter experiment protocol.

It:

- defines explicit train/validation/test splits
- defines explicit hyper-parameters
- runs `run_experiment_protocol(...)`

This is the better example if the goal is:

- a more defensible experiment structure

### `demo_same_grid_time_series_experiment_protocol.py`

This is the same-grid time-series version of the experiment-protocol demo.

It is useful for:

- validating the protocol path
- checking plots and metrics on one known grid

Again, it is not an unseen-grid generalization study if all splits point to the same file.

### `demo_matpower_files_hybrid_inference.py`

This demo shows the hybrid inference path on MATPOWER-style files.

It:

- trains the shared GNN
- runs GNN inference on a test dataset
- runs native refinement from the GNN warm start
- prints GNN-only vs refined metrics

This is the demo to use if the question is:

- “does warm-start + native refinement improve the result?”

### `demo_same_grid_time_series_hybrid_inference.py`

This is the same-grid time-series version of the hybrid demo.

It is useful for:

- checking hybrid inference on one known case
- debugging the warm-start/refinement path before testing on more diverse grids

### `general_purpose_power_flow_gnn_explanation.md`

This Markdown file explains the main module in detail:

- theory
- implementation structure
- dataset flow
- training/testing behavior

It is the best “deep dive” document for the folder.

### `inference_model_explanation.md`

This Markdown file explains the inference contract.

It answers:

- do we still need a grid at inference?
- what is shared?
- what is runtime-specific?

This is important because the multi-grid design can be misunderstood as “grid-free inference”, which is wrong.

### `Tania B - Power flow analysis via typed graph neural networks.md`

This is a local text reference of the typed-GNN paper.

It is a theory/reference file, not runtime code.

Its role is:

- background literature
- architectural inspiration

### `Tania B - Power flow analysis via typed graph neural networks.pdf`

This is the same paper in PDF form.

Again:

- literature reference
- not runtime code

### `files/`

This directory contains example data files used by the demos, especially MATPOWER-style inputs.

Its role is:

- demo input corpus

not:

- core implementation

### `__pycache__/`

This is Python cache output.

It is not part of the designed codebase.

## 5. Core Execution Path

The main execution path across the folder is:

1. user provides file names
2. files are loaded as VeraGrid `MultiCircuit` models
3. each file is solved as a time series
4. each file becomes one `MultiGridDataset`
5. windows are sampled from those datasets
6. the shared GNN predicts voltages
7. the AC physics evaluator computes mismatch and flows
8. losses are accumulated during training
9. post-training evaluation reports metrics and plots
10. optionally, native refinement is applied

That is the central operational story of the folder.

## 6. What the Main Model Actually Is

The core solver is:

- a typed GNN
- with message passing over the electrical graph
- with an unrolled iterative correction loop
- with a deterministic AC physics evaluator inside that loop

It is not:

- a pure black-box regressor
- a model without physics
- a grid-free predictor

The trained weights are shared, but the grid remains a runtime input.

## 7. What “General Purpose” Means Here

In this folder, “general purpose” means:

- one trained GNN can be used on many different runtime grids

It does not mean:

- one trained GNN can solve power flow without being given the grid

That is a critical distinction.

## 8. What Currently Counts as Tests

There are currently no formal unit-test files in this folder.

So the current test story is:

### 1. Syntax checks

The files are being validated through:

- `python3 -m py_compile ...`

This checks:

- syntax correctness
- import-time correctness at parse level

It does **not** check:

- numerical behavior
- runtime solver correctness

### 2. Demos as integration-style tests

The demo scripts currently act as the closest thing to integration tests:

- `demo_matpower_files.py`
- `demo_same_grid_time_series.py`
- `demo_matpower_files_experiment_protocol.py`
- `demo_same_grid_time_series_experiment_protocol.py`
- `demo_matpower_files_hybrid_inference.py`
- `demo_same_grid_time_series_hybrid_inference.py`

These test:

- data loading
- dataset construction
- training loop execution
- evaluation flow
- optional plotting
- optional hybrid refinement path

So they are currently:

- executable demos
- informal integration tests

not:

- formal automated tests

### 3. Literature comparison as conceptual testing

The paper reference files are not tests, but they do provide:

- conceptual design validation
- a baseline for checking whether the architecture still makes sense

## 9. What Is Missing from the Test Story

If this folder is going to mature, the missing tests are:

1. unit tests for:
- graph validation
- dataset window sampling
- snapshot handling
- loss calculations

2. deterministic smoke tests for:
- one tiny grid
- one training step
- one evaluation step

3. regression tests for:
- same input file -> stable metric range
- hybrid refinement improves or at least does not degrade basic voltage error

4. split tests for:
- train/validation/test protocol behavior

At the moment, the demos are doing the heavy lifting.

## 10. Recommended Way to Read the Folder

If you are new to the folder, read it in this order:

1. [general_purpose_power_flow_gnn_explanation.md](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn_explanation.md)
2. [inference_model_explanation.md](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/inference_model_explanation.md)
3. [general_purpose_power_flow_gnn.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/general_purpose_power_flow_gnn.py)
4. [experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/experiment_protocol.py)
5. [hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/hybrid_inference.py)
6. one demo script of interest

Recommended demo order:

1. [demo_same_grid_time_series.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series.py)
2. [demo_same_grid_time_series_experiment_protocol.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series_experiment_protocol.py)
3. [demo_same_grid_time_series_hybrid_inference.py](/home/santi/Git/eRoots/VeraGrid/trunk/ai/grid_ai/demo_same_grid_time_series_hybrid_inference.py)
4. then the MATPOWER demos

## 11. Folder Maturity Summary

This folder is currently:

- a serious prototype / research implementation
- already organized enough to run end-to-end workflows
- not yet a finished production training framework

Strong parts:

- clear main model
- explicit multi-grid dataset concept
- explicit train/test structure
- hybrid refinement path
- extensive explanatory documentation

Still immature parts:

- augmentation is mostly scaffolding
- tests are mostly demos
- no formal test suite
- no checkpoint/reporting framework yet

## 12. Final Summary

`trunk/ai/grid_ai` is a focused workspace for a multi-grid learned power-flow solver.

The files fall into five categories:

1. core model:
- `general_purpose_power_flow_gnn.py`

2. experiment/control utilities:
- `experiment_protocol.py`
- `hybrid_inference.py`
- `data_augmentation.py`

3. demos:
- all `demo_*.py`

4. documentation:
- `general_purpose_power_flow_gnn_explanation.md`
- `inference_model_explanation.md`

5. literature/reference:
- the Tania B paper files

Current tests are mostly:

- syntax checks
- demo execution as integration-style testing

There is not yet a formal unit/regression test suite in this folder.
