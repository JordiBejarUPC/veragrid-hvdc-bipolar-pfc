# Hard saturation

## Purpose

Clamps an input expression between two evaluated limits and writes the result to a retained mode.

## Configuration

- **Output mode**: retained saturated result.
- **Input expression**: requested value.
- **Minimum** and **Maximum**: symbolic bounds.

## Runtime behavior

All three expressions are evaluated at each accepted update. If the bounds are reversed, the implementation normalizes their order before clamping. The operation is procedural and therefore does not add an algebraic residual.
