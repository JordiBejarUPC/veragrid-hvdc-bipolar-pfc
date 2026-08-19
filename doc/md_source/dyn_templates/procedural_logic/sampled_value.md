# Sampled value

## Purpose

Evaluates a symbolic source at every accepted solver boundary and copies its numeric value into a retained mode.

## Configuration

- **Output mode**: retained destination.
- **Source expression**: DAE variables, parameters, time-dependent expressions or previously updated modes.

## Runtime behavior

The value is piecewise constant between accepted updates. Order matters when the source reads a mode written by another procedural entry in the same block.
