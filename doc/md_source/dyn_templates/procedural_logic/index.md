# Runtime procedural logic

Procedural logic runs at accepted simulation boundaries, outside the continuous DAE residual evaluation. It reads the accepted state, runtime parameters and simulation time, and may update retained modes or explicitly mutable targets before the next solve.

The order shown in the editor is the execution order inside each owning block. If one entry reads a mode written by another entry, place the writer first unless a one-step delay is intentional.

## Retained modes

A retained mode is a runtime parameter with an initialization expression. Its value survives between accepted steps. Most procedural entries write one or more modes; DAE equations can read them like any other symbolic parameter.

## Available types

- [Fixed sample](fixed_sample.md)
- [Sampled value](sampled_value.md)
- [Hard saturation](hard_saturation.md)
- [Time delay](time_delay.md)
- [Moving average](moving_average.md)
- [Gradient limiter](gradient_limiter.md)
- [Flip-flop](flipflop.md)
- [Analog flip-flop](analog_flipflop.md)
- [Pickup/dropoff relay](pickup_dropoff.md)
- [Reset on rising edge](reset_on_rising_edge.md)
- [Delayed threshold latch](delayed_threshold_latch.md)
- [Startup handover](startup_handover.md)
- [Valve state](valve_state.md)
- [Three-phase carrier PWM](three_phase_carrier_pwm.md)
- [Three-phase carrier sampled modulation](three_phase_carrier_sampled_modulation.md)

Use **Validate runtime logic** before applying. Validation checks names, references, expressions, missing modes, duplicate writers and order-dependent reads.
