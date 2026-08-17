# Startup handover

## Purpose

Switches a retained startup mode according to a runtime enable-time parameter.

## Configuration

- **Output mode**: retained startup/handover selector.
- **Enable-time parameter**: runtime parameter containing the transition time.

## Runtime behavior

Before the configured time the startup path remains selected; at the boundary the mode changes to the normal-operation path. The entry participates in event-boundary scheduling so the handover can occur at the requested time rather than only at the end of a larger step.
