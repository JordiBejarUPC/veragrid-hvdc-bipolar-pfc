# Pickup/dropoff relay

## Purpose

Creates a binary relay with independent activation and deactivation delays.

## Configuration

- **Output mode**: retained relay state.
- **Condition**: requested relay state.
- **Pickup delay**: time the condition must remain true before activation.
- **Dropoff delay**: time the condition must remain false before deactivation.

## Runtime behavior

The logic schedules exact pending relay boundaries when possible. If the condition reverses before a delay completes, the pending transition is cancelled. Delay expressions are evaluated at runtime and should remain non-negative.
