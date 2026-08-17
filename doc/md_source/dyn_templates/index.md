# Dynamic model library

This library is the entry point for the dynamic models and reusable blocks available in VeraGrid. Use the sections below to browse device-level templates for RMS and EMT simulations, the lower-level blocks used to assemble those models, and the procedural logic evaluated between accepted simulation steps.

## Device templates

Device templates represent complete electrical devices or composite dynamic models that can be assigned to grid elements.

```{toctree}
:maxdepth: 2

RMS/index
EMT/index
```

## Reusable blocks and logic

The dynamic library contains the reusable mathematical and electrical building blocks used by device templates and by the graphical model editors. Runtime procedural logic covers sampled, delayed, and stateful operations that run outside continuous DAE residual evaluation.

```{toctree}
:maxdepth: 2

library/index
procedural_logic/index
```
