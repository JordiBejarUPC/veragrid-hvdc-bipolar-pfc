# Valve state

## Purpose

Determines the retained conduction state of a controlled electrical valve from its type, gate command, antiparallel option, voltage and current.

## Configuration

- **Output mode**: retained conduction-path state.
- **Valve type**, **Gate command**, **Antiparallel enabled**: runtime control parameters.
- **Voltage deadband**, **Current deadband**: runtime numerical tolerances.
- **Valve voltage**, **Valve current**: measured DAE variables.

## Runtime behavior

The state machine applies valve-specific turn-on, turn-off and reverse-path rules at accepted boundaries. Deadbands prevent numerical chatter near zero. All references are mandatory and must identify symbols compiled into the same dynamic system.
