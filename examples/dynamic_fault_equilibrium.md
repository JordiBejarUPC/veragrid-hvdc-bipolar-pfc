# A persistent fault as an RMS equilibrium

Run from the repository root:

```bash
.venv/bin/python examples/dynamic_fault_equilibrium.py
```

The example writes `comparison.png`, `results.json`, `rms_trajectory.csv`,
`equilibrium_convergence.csv`, and a native `two_bus.veragrid` file with component
models and the fault event to `output/dynamic_fault_equilibrium/`.

The comparison plot shows converter voltage, current, active power and reactive
power. Each panel distinguishes the blue time-domain trajectory, an orange square
for the legacy WECC steady-state result, and a green diamond for the direct
equilibrium of the dynamic equations (`dx/dt = 0`, `t → ∞`). The two markers appear
in a separate shaded panel on the same vertical scale, so matching results remain
visible. Those categorical positions represent independent solves, not additional
physical time samples. The dynamic equilibrium is computed before time integration.

## System and models

There are exactly two AC buses on a 100 MVA base. A generator's fixed internal
EMF feeds the first bus through `0.01 + j0.15` p.u. The second bus connects through
a `0.01 + j0.25` p.u. line and hosts a 50 MVA converter initially injecting 40 MW.
A shunt event at 0.1 seconds applies a permanent 0.15 p.u. resistive fault there.
At 20 kV, that fault resistance is 0.6 ohm.

| Component / capability | Reused implementation |
| --- | --- |
| Buses and model connections | `initialize_bus_rms`, `set_rms_model` |
| Source behind fixed EMF | `build_thevenin_voltage_source` |
| AC line | `get_line_rms_template` |
| Permanent fault | `ShuntLoadBuild`, `RmsEvent`, `RmsEventsGroup` |
| System assembly, initialization, compiled residuals and sparse Jacobians | `RmsProblemDae` |
| Consistent pre-fault algebraic variables | `project_initial_algebraic_state` |
| Numerical Newton correction | `solve_rms_newton_correction` |
| Physical time integration | `BackEulerImplicitIntegration` |
| Voltage blocking | Block-attached `SampledValueLogic` |

The new WECC-like block expresses the existing simplified WECC law with three
first-order differential states: measured terminal voltage, active current, and
reactive current. It includes voltage-support deadband, reactive-current
priority, the existing VDL curve, the 1.3 p.u. current limit, and voltage blocking.
All three converter states are solved freely; none is held at its pre-fault value.
The pre-fault values are initialization guesses only. The voltage and power
reference settings are ordinary controller parameters, initialized consistently
with the legacy WECC comparison; this prototype does not add plant-level reference
dynamics or DC-link energy states.

## The small extension to dynamics

The equilibrium calculation receives an already compiled RMS problem. It applies
the permanent fault event, sets the derivative vector to zero, and solves the
concatenation of `rhs_state` and `rhs_algebraic` for **all** state and algebraic
variables simultaneously. It uses the continuous-time Jacobian blocks and a
damped Newton iteration. It does not generate a separate set of network equations
or eliminate the converter states by hand.

The blocking mode is held fixed during each continuous Newton solve, then the
existing procedural updater checks it against the resulting state. If it changes,
the equations are solved again. This is a narrowly scoped mode-consistency loop
for this model's memoryless rule, not a general interpretation of timers or latches.
Mode cycling and numerical nonconvergence raise errors.

Separately, the existing backward-Euler RMS integrator starts from the pre-fault
state and evolves the **same compiled problem** through the same fault event. The
script requires both the endpoint's equilibrium residual and its difference from
the direct solution to be small. The direct solution is computed first, from the
pre-fault guess, without using the time-domain endpoint as its seed. Generator EMF
parameters are checked to remain unchanged.

An equilibrium root is a candidate for the infinite-time response. The time-domain
comparison establishes convergence for these examples; this prototype does not
claim that every dynamic model or persistent fault has a stable equilibrium.

## Comparison and experiments

The default run produces 0.679490 p.u. at the source bus and 0.416333 p.u. at
the converter bus. The converter delivers 15.5101 MW and 22.1759 MVAr, at its
1.3 p.u. current limit on the 50 MVA converter base. Fault current is 2.775557 p.u.
on the 100 MVA network base. The RMS endpoint differs from the direct equilibrium
by at most `3.4e-8` across all state and algebraic variables, and the legacy SC
complex bus voltages differ by at most `1.6e-8` p.u.

The existing, unchanged `ShortCircuitDriver` supplies the hardcoded WECC reference.
That legacy path represents the converter as a VSC branch and therefore needs an
additional ideal DC supply bus. Its two AC buses, source impedance, line, converter
rating and pre-fault solution match the dynamic case. The script also checks AC
current balance independently using the terminal voltages and fixed internal EMF.

To reproduce the timing comparison:

```bash
.venv/bin/python examples/benchmark_dynamic_fault_equilibrium.py
```

The benchmark performs one first-use round and seven warm repetitions, rotating
method order and checking that every solution agrees. Both RMS methods reuse the
compiled problem and start from the pre-fault state. It writes samples, medians,
ranges, first-use timings, and setup timings to
`output/dynamic_fault_equilibrium/timing.json`. Imports, plotting and export are
outside the timers. The legacy driver timing includes numerical circuit assembly
and result extraction; its internal Newton time is reported separately.

On this machine, seven warm runs gave median solve times of 2.075 seconds for the
full 1-second trajectory at a 1 ms step, 0.0670 seconds for direct RMS equilibrium,
and 0.00841 seconds for the legacy SC driver (0.00639 seconds for its Newton solve
alone). These are prototype measurements for this small case, not scaling claims.
First-use costs differ: shared RMS preparation took 0.870 seconds; legacy grid and
pre-fault preparation took 7.438 seconds, and its first SC solve took 2.526 seconds.
The process reused existing disk caches; it was not a clean-cache startup test.

Change only the dynamic model's voltage-support gain:

```bash
.venv/bin/python examples/dynamic_fault_equilibrium.py --kqv 1 --output output/dynamic_fault_equilibrium_gain1
```

The dynamic equilibrium and time-domain endpoint should agree with one another,
while differing from the legacy reference, whose gain remains hardcoded at 2.

Change the current response time:

```bash
.venv/bin/python examples/dynamic_fault_equilibrium.py --current-tau 0.05 --duration 2 --output output/dynamic_fault_equilibrium_slower
```

The transient changes but the equilibrium does not. Use `--fault-r 0.3` for a
milder, unsaturated fault and `--blocking-voltage 0.5` to exercise voltage blocking
at the default fault resistance. That blocking case is checked against the exact
passive-network solution as well as the RMS endpoint. The legacy SC solver can
fail at the blocking discontinuity; the report explicitly excludes its result
when it does not converge. An
insufficient `--duration` fails the settling check rather than labelling an
unsettled trajectory as an infinite-time result.

One limitation discovered by the tests is important for the next implementation:
the inherited polar power-balance formulation has spurious zero-voltage roots.
For a much deeper 0.02 p.u. fault, the small Newton prototype heads toward that
branch and now explicitly rejects it through its voltage-domain constraint.
The unmodified time integrator can encounter that degeneracy too. This is a
numerical limitation, not evidence that the physical equilibrium does not exist.
Robust deep-fault support would benefit from current-balance equations and fault
continuation; that engine work is intentionally outside this small example.

This is a balanced RMS proof of concept. The converter is an AC injection model;
there is no DC energy balance, PLL, mechanical model, delayed protection or PWM.
For the default positive-current case the two current filters share a time
constant. They may temporarily depart from an instantaneous limiting surface in
more general scenarios. The example does not establish transient current-limit
behaviour for a full WECC model. Switched EMT and history-dependent controls need
their own periodic-state or history treatment.

Tests:

```bash
.venv/bin/python -m pytest src/tests/RMS/test_dynamic_fault_equilibrium_example.py
```

All implementation changes are confined to this example and its tests; existing
engine implementations and the short-circuit solver remain unchanged.
