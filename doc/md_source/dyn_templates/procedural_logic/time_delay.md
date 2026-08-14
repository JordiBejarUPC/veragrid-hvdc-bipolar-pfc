# Time delay

## Purpose

Stores accepted source samples and exposes the value corresponding to an earlier simulation time.

## Configuration

- **Output mode**: retained delayed result.
- **Source expression**: signal sampled into the history.
- **Delay**: symbolic delay in seconds.

## Runtime behavior

A non-positive delay passes the current sample through. Positive delays use the available accepted-step history, so accuracy depends on the simulation step and event boundaries. Delays should remain non-negative during operation.
