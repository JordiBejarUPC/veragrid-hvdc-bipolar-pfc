# Select and switch blocks

### Purpose

Select and switch blocks route one of several candidate signals to the output.

### Behavior

- Receives signal candidates plus a selector or boolean control.
- Outputs the selected signal.
- Can be used for control-mode changes, bypass logic, fallback behavior, or operating-region selection.

### Characteristics

- Useful in supervisory logic and multi-mode controllers.
- Includes variants with fixed selection, signal-based selection, and boolean switching.

## Interface table

| Category | Name | Meaning | Units |
| --- | --- | --- | --- |
| Input | `s1` | First candidate signal | model-dependent |
| Input | `s2` | Second candidate signal | model-dependent |
| Input | `s3` | Third candidate signal in multi-input variants | model-dependent |
| Input | `sw` | Selector or switching signal | boolean, integer, or model-dependent |
| Output | `yo` | Selected output signal | model-dependent |
| Parameter | `sel` | Fixed selector parameter in constant-selection variants | integer or boolean |

## How to use it

- Use these blocks when a model must choose between operating modes or alternate signal paths.
- Check the exact variant to see whether switching is signal-driven or parameter-driven.
