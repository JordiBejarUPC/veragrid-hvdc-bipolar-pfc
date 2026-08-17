# Reset on rising edge

## Purpose

Detects a false-to-true transition and assigns a symbolic value to an explicitly mutable target.

## Configuration

- **Target**: state variable or runtime parameter to mutate.
- **Rising-edge condition**: Boolean expression used by the edge detector.
- **Reset value**: expression assigned on the edge.

## Runtime behavior

The first update establishes the previous condition and does not create a synthetic edge. Later rising edges mutate the target once. This type writes a target directly rather than producing a retained output mode, so use it only where an imperative reset is required.
