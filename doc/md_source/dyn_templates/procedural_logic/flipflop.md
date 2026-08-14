# Flip-flop

## Purpose

Implements a retained binary set/reset latch.

## Configuration

- **Output mode**: retained `0.0` or `1.0` latch state.
- **Set condition**: drives the state high.
- **Reset condition**: drives the state low.

## Runtime behavior

At initialization, Set determines the initial state. During operation, Set-only activates and Reset-only clears. When both conditions have the same truth value, the previous state is retained. Use explicit, mutually understandable conditions to avoid ambiguous control intent.
