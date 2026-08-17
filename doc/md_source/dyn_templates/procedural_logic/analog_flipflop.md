# Analog flip-flop

## Purpose

Implements a set/reset latch that captures and retains an analog input value.

## Configuration

- **Output mode**: retained analog value.
- **Input expression**: value captured when Set activates.
- **Set condition**: captures and holds the input.
- **Reset condition**: releases the active latch state.

## Runtime behavior

The input is sampled when the latch is initialized or transitions into the set state. It is not continuously tracked while held. Order matters if the input expression reads modes written earlier in the same update.
