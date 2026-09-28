## Reporting a bug

- [x] I have tried using the latest released version of Numba. I am using Numba `0.67.0`, which appears to be the latest release listed in the Numba release notes / PyPI.
- [x] I have included a self contained code sample to reproduce the problem. It can be run as `python bug.py`.
- [x] I have read and understood Numba's AI tool use policy.

### Summary

On macOS arm64, first-time JIT compilation inside a `PySide6.QtCore.QThread` can terminate the Python process with `SIGBUS`.

The same function compiles and runs successfully on the main thread. The crash happens during llvmlite/LLVM object finalization, not as a Python exception.

### Environment

```text
Python: 3.14.3
Platform: macOS-27.0-arm64-arm-64bit-Mach-O
Machine: arm64
NumPy: 2.5.3
Numba: 0.67.0
llvmlite: 0.49.0
PySide6: 6.11.2
```

Numba 0.67.0 is listed as the latest release in the Numba release notes and PyPI:

- https://numba.readthedocs.io/en/latest/release-notes-overview.html
- https://pypi.org/project/numba/

### Reproducer

Save the attached script as `bug.py`.

The script contains no application-specific imports. It defines:

- a Numba `jitclass` sparse matrix type,
- several `@njit` helpers,
- a `@jit(nopython=True)` function returning the jitclass,
- a PySide6 `QThread` that calls the function for the first time.

### Commands

This succeeds:

```bash
python bug.py --main-thread --no-cache
```

This crashes the process:

```bash
python bug.py --no-cache
```

### Expected behavior

The function should compile and run successfully from the Qt worker thread, or raise a Python exception if this usage is unsupported.

### Actual behavior

The process terminates natively.

Typical output:

```text
worker started on Python thread ..., Qt thread object ...
calling create_jacobian_like on Python thread ...
Bus error
```

In the original application, `faulthandler` showed the crash inside llvmlite/LLVM finalization:

```text
Fatal Python error: Bus error

Current thread ... [GcThread]
  File ".../llvmlite/binding/ffi.py", line 212 in __call__
  File ".../llvmlite/binding/executionengine.py", line 99 in finalize_object
  File ".../numba/core/codegen.py", line 1071 in wrapper
  File ".../numba/core/codegen.py", line 1010 in _finalize_specific
  File ".../numba/core/codegen.py", line 808 in _finalize_final_module
  File ".../numba/core/codegen.py", line 776 in finalize
  ...
```

The native stack included:

```text
libllvmlite.dylib ... AArch64AsmPrinter::emitEndOfAsmFile
libllvmlite.dylib ... llvm::MCJIT::finalizeObject
LLVMPY_FinalizeObject
```

### Notes

This appears to be specific to first compilation from a Qt worker thread on macOS arm64. Precompiling the same function on the main thread avoids the crash in the reproducer, but that is not a reliable application-level fix.

The self-contained reproducer used for this report is:

```text
trunk/qt_related/numba_qthread_jitclass_sigbus_repro.py
```
