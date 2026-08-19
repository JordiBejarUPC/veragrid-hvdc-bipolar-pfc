# Product

The Product block multiplies numerator inputs and divides by denominator
inputs. General options controls how many ports participate in each group.

## Characteristic equation

$$
y = \frac{\prod_i u_i}{\prod_j v_j}
$$

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `mul_i` | Numerator factors | model-dependent |
| Input | `div_j` | Denominator factors | model-dependent |
| Output | `y` | Algebraic product or ratio | derived from inputs |

The model author must ensure that denominator signals do not reach zero.
