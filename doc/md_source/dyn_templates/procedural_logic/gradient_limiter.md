# Gradient limiter

## Purpose

Limits how fast a retained output can move toward a requested source value.

## Configuration

- **Output mode**: retained rate-limited result.
- **Source expression**: requested value.
- **Lower rate** and **Upper rate**: permitted slopes per second.

## Runtime behavior

The first accepted update initializes the held output from the source. Each later update restricts the change using elapsed accepted time. Reversed lower and upper bounds are normalized automatically.
