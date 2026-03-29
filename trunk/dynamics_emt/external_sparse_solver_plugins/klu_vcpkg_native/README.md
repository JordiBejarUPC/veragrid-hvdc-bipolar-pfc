# Direct KLU Native vcpkg Plugin

This plugin loads KLU through a native Python extension that links directly
against the SuiteSparse KLU libraries installed externally with `vcpkg`.

## Goal

Avoid the fragile `cvxoptklu` path and provide a cleaner EMT-facing KLU backend.

## Expected external native runtime

By default the native plugin expects the SuiteSparse install root at:

```text
%USERPROFILE%\.VeraGrid\external_native\vcpkg\installed\x64-windows
```

## Build

Build the native plugin with:

```bat
build_native_plugin.cmd
```

The built extension is written to:

```text
native_build\klu_native_backend*.pyd
```

## Runtime

At runtime the plugin loads the native extension and uses the vcpkg-installed
KLU DLLs.
