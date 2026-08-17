# Fixed sample

## Purpose

Evaluates a condition once, on the first accepted runtime update, and stores the Boolean result (`0.0` or `1.0`) in a retained mode. Later updates leave that value unchanged.

## Configuration

- **Output mode**: retained mode receiving the sampled Boolean value.
- **Condition**: symbolic expression or comparison evaluated once.

## Runtime behavior

This is useful for selecting an operating branch from initial conditions. The output mode must exist and must not be written by another procedural entry. Put this entry before logic that consumes its output during the same boundary update.
