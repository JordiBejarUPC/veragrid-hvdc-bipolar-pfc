# Lookup and table blocks

### Purpose

Lookup and table blocks approximate nonlinear functions or stored curves from tabulated data.

### Behavior

- Receives one or more input variables.
- Interpolates or selects a value from a stored array, object-array, or matrix.
- Produces one approximated output.

### Characteristics

- Useful for nonlinear device curves, empirical control laws, saturation maps, and tabulated profiles.
- The library includes fixed-size, variable-size, linear, spline, and inverse-lookup variants.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `yi` | Main input of one-dimensional lookup variants | model-dependent |
| Input | `yi1` | First input of multi-dimensional lookup variants | model-dependent |
| Input | `yi2` | Second input of multi-dimensional lookup variants | model-dependent |
| Output | `yo` | Interpolated output value | model-dependent |
| Parameter | `array_K` | Stored lookup array in simple array-based variants | data object |
| Parameter | `oarray_K` | Stored object-array lookup data | data object |
| Parameter | `matrix_K` | Stored matrix lookup data | data object |
| Parameter | `vClip` | Clipping-enable or clipping-style parameter in variants that support clipping | boolean or 0/1 |

## How to use it

- Use these blocks whenever a nonlinear relation is easier to define by tabulated data than by one closed-form equation.
- Select the lookup variant according to interpolation method and whether the data are fixed or variable during runtime.
