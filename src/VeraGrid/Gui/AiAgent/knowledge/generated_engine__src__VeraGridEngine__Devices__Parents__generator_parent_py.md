# VeraGridEngine Module: src/VeraGridEngine/Devices/Parents/generator_parent.py

- Original source path: `src/VeraGridEngine/Devices/Parents/generator_parent.py`
- Knowledge kind: generated VeraGridEngine code summary

## Module Summary

No docstring provided.

## Module Surface

- Class count: 1
- Top-level function count: 0
- Representative imports: __future__, typing, numpy, VeraGridEngine.Devices.Substation.bus, VeraGridEngine.enumerations, VeraGridEngine.basic_structures, VeraGridEngine.Devices.profile, VeraGridEngine.Devices.Parents.injection_parent, VeraGridEngine.Devices.Parents.editable_device

## Class: GeneratorParent

- Bases: InjectionParent
- Summary: Template for objects that behave like generators

### Methods

- `P(self)`
  Summary: Get the active power value
- `P(self, val)`
  Summary: Set active power value
- `P_prof(self)`
  Summary: Cost profile
- `P_prof(self, val)`
  Summary: No docstring provided.
- `get_P_at(self, t)`
  Summary: :param t:
- `srap_enabled_prof(self)`
  Summary: Control bus profile
- `srap_enabled_prof(self, val)`
  Summary: No docstring provided.
- `get_srap_enabled_at(self, t)`
  Summary: :param t:
- `Pmax_prof(self)`
  Summary: Pmax profile
- `Pmax_prof(self, val)`
  Summary: No docstring provided.
- `get_Pmax_at(self, t)`
  Summary: :param t:
- `Pmin_prof(self)`
  Summary: Pmin profile
- `Pmin_prof(self, val)`
  Summary: No docstring provided.
- `get_Pmin_at(self, t)`
  Summary: :param t:
- `get_S_with_sign(self)`
  Summary: :return:
- `get_Sprof_with_sign(self)`
  Summary: :return:
- `Pmin(self)`
  Summary: Get ``Pmin``.
- `Pmin(self, val)`
  Summary: Set ``Pmin``.
- `Pmax(self)`
  Summary: Get ``Pmax``.
- `Pmax(self, val)`
  Summary: Set ``Pmax``.
- `srap_enabled(self)`
  Summary: Get ``srap_enabled``.
- `srap_enabled(self, val)`
  Summary: Set ``srap_enabled``.
