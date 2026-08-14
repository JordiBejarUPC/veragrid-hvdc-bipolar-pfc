# Delayed threshold latch

## Purpose

Trips a retained mode after a monitored DAE variable stays beyond a fixed threshold for a specified time.

## Configuration

- **Monitored variable**: DAE signal being compared.
- **Output mode**: retained trip state.
- **Threshold**: numeric comparison threshold.
- **Delay**: non-negative trip delay.
- **Reset delay**: optional non-negative time after which the latch resets.

## Runtime behavior

The latch requests event boundaries at the scheduled trip or reset times. It is suited to protection and fault-control logic where a threshold must persist before action.
