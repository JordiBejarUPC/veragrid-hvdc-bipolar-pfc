# VeraGrid Qt stability audit

Date: 2026-09-07

## Scope and interpretation

This is a static audit of the main GUI, session ownership, worker-thread coordination, diagram lifetime, server integration, AI dialogue, file I/O, and adjacent Qt-facing code. No production code was changed and no crash was reproduced as part of this audit.

The report concentrates on failures that can end the process with no preceding GUI warning: `QThread` destruction while running, forced asynchronous thread termination, GUI/model access from worker threads, Qt object finalization on the wrong thread, nested event-loop reentrancy, and native-library failures. Ordinary Python exceptions are included only where the desktop launcher can hide stderr or where they leave the GUI in a state that makes a later native failure more likely.

Severity means:

- **Critical**: a concrete current path can violate a Qt/native lifetime rule and terminate or corrupt the process.
- **High**: a concrete current race or affinity violation can plausibly terminate the process under timing or platform conditions.
- **Medium**: a real coordination defect that usually causes exceptions, stale state, or hangs, but can feed a native failure.
- **Low**: a smaller residual lifetime gap or future regression trap.

## Executive summary

The most likely current clean-crash chains are:

1. Starting a study when an old worker of the same type still exists calls `QThread.terminate()` and immediately removes the only session reference to it.
2. Cancel emits the study's completion signal before the worker has stopped. GUI post-processing can run synchronously against results that the worker is still modifying, and it runs a second time when `GcThread.run()` returns.
3. Project replacement, result clearing, and scenario activation replace the circuit/diagrams/drivers without stopping or rebinding live session threads. Old callbacks then target a new GUI generation.
4. Application shutdown waits only five seconds, ignores timeout results, and uses `quit()` on `QThread` subclasses whose blocking `run()` methods have no Qt event loop. The window is accepted even if workers remain alive.
5. `ServerDriver` directly changes a `QLabel` and resets a GUI-owned `QAbstractTableModel` from its worker thread.
6. Server remote jobs and the AI worker are not covered by the main thread registry. AI cancellation cannot be delivered while its worker slot is busy, and shutdown can block the GUI while the worker is making a blocking call back to it.

These defects reinforce each other. For example, clearing results detaches a live thread; rerunning the same study then reaches forced termination; cancellation can meanwhile invoke post-processing on a different circuit.

## Case study: a calculation crashes, but succeeds later in a new instance

**Observed behavior:** a calculation closes VeraGrid without warning, while the same calculation and input data work normally after starting a new VeraGrid process.

This pattern is evidence against a purely deterministic model or numerical-input error. It points instead to process state, object lifetime, thread timing, or native-library state that is discarded by restarting VeraGrid.

The strongest session-related failure sequence is:

1. An earlier calculation is cancelled, cleared, or logically reported as complete.
2. Its `GcThread` is still executing because cancellation does not wait for `run()` to return.
3. Results are cleared, a project/scenario is replaced, or another calculation is launched.
4. The session's driver dictionary, thread dictionary, running-state list, active circuit, and diagrams no longer describe the same generation of work.
5. The old worker emits a delayed completion callback, continues writing result arrays, or is forcibly terminated by `SimulationSession.run()`.
6. Old and new code paths concurrently access native solver/NumPy state or Qt models, diagrams, and wrappers. The process can then terminate through SIGABRT or SIGSEGV rather than a handled Python exception.

A new instance removes every part of that contaminated state: there are no orphaned workers, queued signals from an earlier circuit, stale PySide wrappers, inconsistent session dictionaries, or previously interrupted native solver state. Consequently, the identical calculation can run successfully.

The timing of the failure is nondeterministic. Thread scheduling, solver duration, queued-signal delivery, garbage collection, and user actions determine whether the stale worker reaches shared state during the dangerous window. “It worked after restarting” therefore does not clear the model, solver, or calculation path; it is itself a useful indicator of a lifecycle race.

### Diagnostic interpretation

- If the crash occurs after cancelling, clearing results, opening/creating a project, changing scenario, or rerunning a study, F-01, F-02, and F-04 form the leading explanation.
- If VeraGrid has been open for a long time or has run several studies, accumulated workers, duplicate completion callbacks, and stale diagrams make the same explanation more likely.
- If the crash happens on the first calculation immediately after process start, with no preceding GUI operation, stale session state is less likely. A native solver/BLAS failure, a calculation-specific extension, server-thread affinity violation, or platform-specific issue should be investigated instead.
- If only the GUI disappears while a terminal launch shows `QThread: Destroyed while thread is still running`, the worker ownership/shutdown findings are directly implicated.
- If the terminal reports SIGSEGV with a BLAS/NumPy stack on ARM macOS, H-02 is a stronger match.
- If the failure follows Cancel and the post-processing UI briefly updates before exit, premature `done_signal` delivery in F-02 is the strongest match.

## Current findings

### F-01 - Critical: a rerun forcibly terminates the previous simulation thread

**Locations:**

- `src/VeraGrid/Session/session.py:229-320`
- In particular `session.py:260-285`

`SimulationSession.run()` looks up the old `GcThread`. If it is running, both branches call `previous_thread.terminate()` (`272` and `282`) and then delete the thread from `self.threads` (`276` and `285`) without requesting cooperative cancellation or waiting for actual completion.

`QThread.terminate()` is asynchronous and unsafe: execution can stop while Python, NumPy, a solver, BLAS, a file parser, or Qt holds a lock or is mutating shared memory. The next worker is started immediately against the same session and frequently the same circuit. Removing the registry reference before the old thread has finished also permits the wrapper to be destroyed while the native thread is live, which is a standard `QThread: Destroyed while thread is still running` abort path.

This path becomes reachable even though most launch actions first check `is_this_running()`: F-03 and F-04 can make GUI/session state say that work is done or absent while the old native worker is still active.

### F-02 - Critical: cancellation reports completion while work is still running

**Locations:**

- `src/VeraGrid/Session/session.py:78-163`
- `src/VeraGridEngine/Simulations/driver_template.py:179-206`
- `src/VeraGrid/Gui/Main/SubClasses/base_gui.py:1221-1244`
- Representative post handlers: `src/VeraGrid/Gui/Main/SubClasses/simulations.py:1601-1626`, `2989-3023`, `3624-3699`, `4074-4147`, `4211-4302`

`GcThread` assigns its Qt `done_signal` to the engine driver. The default `DriverTemplate.cancel()` sets a flag and calls `report_done("Cancelled!")`, which emits that same signal. The GUI cancel action calls `GcThread.cancel()` on the GUI thread. Because the signal is emitted while caller and receivers are on the GUI thread, the connected post handler can execute immediately and reentrantly, before `set_cancel_state()` has returned and while `GcThread.run()` is still modifying results.

When the worker eventually returns, `GcThread.run()` emits `done_signal` again at `session.py:147`. Several drivers also call `report_done()` from normal `run()` or from their own `cancel()` implementations, including catalogue optimization, node groups, topology reduction, stochastic power flow, investments, and blackout/reliability. Therefore completion handlers may run twice even without a cancellation.

Post handlers do more than update text. They read result arrays, rebuild models, colour diagrams, show dialogs, mutate the active circuit, and in investments create a new diagram. Reading NumPy/native result buffers while a solver writes them is a data race outside Python's normal object-safety assumptions. Repeating GUI teardown/rebuild operations also exposes stale PySide wrappers and QGraphics items.

Cancellation must mean “request sent,” not “worker finished.” Only the worker's actual return or `QThread.finished` is a valid completion boundary.

### F-03 - Critical: shutdown accepts the close with live workers

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/base_gui.py:547-617`
- `src/VeraGrid/Gui/Main/VeraGridMain.py:177-205`

`stop_all_threads()` calls cooperative `cancel()` only for `GcThread`. For every running object it then calls `quit()` and `wait(5000)`, but ignores the boolean result of `wait()`.

Most listed workers subclass `QThread` and override `run()` with blocking computation, parsing, export, or sleep loops. They do not run the default Qt event loop, so `quit()` does not stop the work. `FileOpenThread`, `FileSaveThread`, and `ExportAllThread` are not cancelled at all. `FileSyncThread` has a cooperative flag, but `stop_all_threads()` does not call its `cancel()`.

`VeraGridMainGUI.closeEvent()` accepts the close unconditionally after this bounded wait. If any operation exceeds five seconds, main-window and application teardown proceeds while QThreads and native libraries still reference the circuit, signals, and GUI receivers. Destruction of a live QThread can abort the process; native work continuing during interpreter/Qt teardown can also segfault.

### F-04 - High: project, result, and scenario replacement leave old session workers alive

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/simulations.py:683-705`
- `src/VeraGrid/Session/session.py:194-210`
- `src/VeraGrid/Gui/Main/SubClasses/io.py:290-344`
- `src/VeraGrid/Gui/Main/SubClasses/Model/scenarios.py:464-503`

`clear_results()` calls `SimulationSession.clear()`, but `clear()` only replaces the drivers dictionary. It does not stop or clear `session.threads`.

`new_project_now()` replaces `self.circuit`, destroys diagrams, and then executes:

```python
for thread in self.get_all_threads():
    thread = None
```

This only rebinds a local loop variable. It neither stops a thread nor clears the attribute/dictionary holding it. The method then clears the running-state list and drivers, so the GUI loses the evidence that an old worker is active while the worker and callback remain connected.

Scenario activation similarly swaps to `node.drivers` but does not stop, clear, or associate `session.threads` with the selected scenario. The thread dictionary can consequently describe the previous scenario while the driver dictionary and GUI describe the new one.

An old completion callback may then colour deleted diagrams, index results using a differently shaped circuit, mutate the new project, or unlock a newer operation. A rerun of the same simulation type can also reach F-01 and terminate the detached worker.

### F-05 - High: `ServerDriver` performs GUI and model operations from its worker thread

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/Server/server.py:28-33`, `101-120`
- `src/VeraGrid/Session/server_driver.py:25-55`, `203-210`, `447-473`, `579-621`

The main thread creates `ServerDriver.data_model` and installs it directly on `server_tableView`. When server mode starts, the GUI passes `self.ui.server_status_label.setText` as a plain callback. `ServerDriver.run()` calls `report_status()`, which directly invokes that bound widget method from the worker thread.

The same worker calls `get_jobs()`, which invokes `JobsModel.parse_data()`. That function mutates the list and calls `beginResetModel()`/`endResetModel()` on a model being consumed by a GUI view. It even clears `jobs` before `beginResetModel()`.

Qt widgets and GUI-owned item models are not thread-safe. These are direct, concrete affinity violations and can fail inside Qt's model/view or platform code without a catchable Python exception. Status and response data must cross the boundary as signals; the GUI thread must update the label and model.

### F-06 - High: server and remote-job workers are absent from application shutdown

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/base_gui.py:557-578`
- `src/VeraGrid/Gui/Main/SubClasses/Server/server.py:28-31`
- `src/VeraGrid/Gui/Main/SubClasses/simulations.py:4316-4354`
- `src/VeraGrid/Session/server_driver.py:656-734`

`get_all_threads()` includes session simulation threads and a fixed process-worker list, but not `self.server_driver` or the `RemoteJobDriver` objects in `self._remote_jobs`. Closing VeraGrid during connection, upload, result parsing, or network timeout does not request cancellation or wait for either class.

`RemoteJobDriver.run()` also calls `self.session.register_driver()` directly from its worker thread. This mutates the session driver dictionary while GUI code can iterate it or rebuild result/diagram models. In ordinary Python this can raise “dictionary changed size during iteration”; combined with stale result objects and Qt callbacks it is an avoidable cross-generation race.

The custom remote `done_signal` is emitted immediately before `run()` returns. `post_run_remote()` removes the final application-held dictionary reference without checking `QThread.finished` or calling `wait()`. The executing method usually keeps a temporary Python reference alive, but relying on that implementation detail is not a valid QThread lifetime guarantee.

### F-07 - High: the AI worker cannot be cancelled while busy and can deadlock with close

**Locations:**

- `src/VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:3114-3320`
- `src/VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:2740-2880`
- `src/VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:5058-5073`, `6008-6033`, `6542-6551`
- `src/VeraGrid/Gui/Main/SubClasses/base_gui.py:1087-1098`

`AiTurnWorker` is moved to a dedicated thread and its long `run_request()` occupies that thread's event loop. Cancellation is sent as a queued signal to `request_cancellation()`, a slot on the same worker. The slot cannot run until `run_request()` returns, so the cancellation flag checked by the long operation cannot normally be changed during the operation.

Shutdown calls `quit()` and `wait(2000)` and ignores timeout. `quit()` likewise cannot interrupt the currently executing slot. The thread is parented to the dialog, so allowing dialog/application destruction after the timeout creates another live-QThread destruction path.

There is an additional close-time deadlock window. `MainThreadSimulationRunner` correctly uses `BlockingQueuedConnection` to query or command the GUI from the AI worker. During `closeEvent()`, however, the GUI thread blocks in `wait(2000)`. If the AI worker is simultaneously blocked emitting one of those calls, neither can progress until the GUI wait times out. Teardown can then continue while the worker resumes against a closing/deleted main window.

### F-08 - High: explicit `processEvents()` permits destructive nested reentrancy

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/base_gui.py:381-389`
- `src/VeraGrid/Gui/Main/SubClasses/simulations.py`, including `1530`, `1539`, `1573`, `1643`, `1989`, `2681`, `2947`, `3635`, `4057`, `4174`, `4386`, and `4684`
- `src/VeraGrid/Gui/dialog_lifecycle.py:27-46`

`LOCK()` only changes progress-frame visibility and then processes all queued GUI events. It does not disable project replacement, scenario selection, close, diagram deletion, or a different study launch. Simulation launch methods call `processEvents()` again between marking a study as running and constructing/registering its driver. For example, power-flow launch does this at `1530` and `1539` before `session.run()`.

A user action, timer, old worker completion, or close event can therefore run in the middle of the outer method. The nested action can replace `self.circuit`, clear the running marker, delete diagrams/dialogs, or accept application close. The outer stack then resumes using assumptions and PySide wrappers captured before the nested event.

`delete_dialog_safely()` also calls `deleteLater()`, explicitly flushes deferred deletion, and then processes all application events from inside caller cleanup. The validity check prevents a simple double delete, but processing unrelated events before the caller unwinds remains a reentrancy hazard.

### F-09 - High on macOS: remaining `pyplot.show()` calls can start a second GUI loop

**Locations:**

- Current warning/fixed pattern: `src/VeraGrid/Gui/Main/SubClasses/Results/dynamics_results_handler.py:5060-5092`
- Remaining Main paths: `src/VeraGrid/Gui/Main/SubClasses/Results/results.py:852-866`, `Model/compiled_arrays.py:105-129`, `Model/time_events.py:500-523`, `Model/data_base.py:2148-2161`
- Remaining diagram paths: `src/VeraGrid/Gui/Diagrams/base_diagram_widget.py:752-754`, `802-804`; `MapWidget/grid_map_widget.py:1997`; `SchematicWidget/schematic_widget.py:6283`, `6338`

The dynamics result handler explicitly documents that `pyplot.show()` started a second GUI event loop and caused a hard crash on macOS; that path now embeds the canvas in a retained Qt dialog. Several sibling actions still call `plt.show()` directly while VeraGrid's Qt event loop is already running.

This is platform/backend dependent, but it is a known in-repository clean-crash mechanism rather than a theoretical concern. All Matplotlib windows launched by the main GUI should use the same retained Qt-dialog pattern or a verified non-blocking integration.

### F-10 - Medium: custom “done” signals are not actual QThread completion

**Locations:**

- `src/VeraGrid/Session/file_handler.py:92-147`, `221-254`
- `src/VeraGrid/Session/export_results_driver.py:45-62`
- `src/VeraGrid/Session/server_driver.py:692-734`
- `src/VeraGrid/Gui/GridMerge/grid_diff.py:32-279`

Multiple workers emit an application-defined `done_signal` from inside `run()`. GUI slots then clear running flags, replace object references, close dialogs, or update shared models before the QThread has emitted its built-in `finished` signal. Usually only a few Python instructions remain, but the code treats logical completion and native thread completion as the same state.

This is the architectural source of several narrow destruction windows. Ownership release and teardown should be tied to `QThread.finished` (or an explicit successful `wait()`), while a separate result signal carries payload/error state.

### F-11 - Low: video export uses a QThread-shaped object synchronously, creating a regression trap

**Locations:**

- `src/VeraGrid/Gui/Main/SubClasses/Model/diagrams.py:63-175`, `3021-3070`
- `src/VeraGrid/Gui/Diagrams/base_diagram_widget.py:868-885`, `1142-1175`

`VideoExportWorker` is a QThread subclass whose `run()` recolours live diagrams, renders Qt images, and writes through OpenCV. The caller deliberately invokes `self.video_thread.run()` directly rather than `start()`, so current execution stays on the GUI thread. The audited colouring path does not itself call `processEvents()`, so no current cross-thread or reentrant-deletion defect was found in this path. It does block the GUI and does not create a real worker lifecycle.

The class shape is nevertheless a serious regression trap: changing the call to the apparently normal `start()` would move all QGraphics/QImage/widget access to a worker thread and make it invalid immediately. It should remain explicitly synchronous unless GUI capture and worker-side encoding are separated.

### F-12 - Medium: file-open failure can be silent and leave GUI lifecycle state stuck

**Locations:**

- `src/VeraGridEngine/IO/file_open.py:54-102`
- `src/VeraGrid/Session/file_handler.py:92-147`

`FileOpenOptions.crash_on_errors` defaults to `True`. In that branch, `FileOpenThread.run()` catches `FileNotFoundError` but lets other Python exceptions escape without a `finally` that emits `done_signal`. This normally terminates only the worker, not the process, but leaves the GUI locked/running marker uncleared and prints diagnostics only to stderr. If the parser fails in a C/C++ extension instead, the same unguarded path can terminate the process.

`ExportAllThread.run()` similarly has no exception/finally boundary, so failure can strand GUI state. `FileSaveThread` now has a broad exception/finally path and is better behaved.

### F-13 - Medium: no process-level crash diagnostics explain the “no warning” symptom

**Locations:**

- `src/VeraGrid/Gui/Main/VeraGridMain.py:300-338`
- `src/VeraGrid/setup.py:115-120`

The entry point creates the application and directly exits with `sys.exit(app.exec())`. There is no `faulthandler`, uncaught-exception hook, Qt message handler, fatal-signal log, or last-running-worker record in `src/VeraGrid`/`src/VeraGridEngine`.

VeraGrid is installed through `gui_scripts`. A desktop launch commonly has no visible terminal, so Qt warnings such as cross-thread QObject access or “QThread destroyed while running,” Python worker tracebacks, SIGABRT, and SIGSEGV disappear with the process. This is not a crash cause, but it turns the causes above into apparently warning-free exits and makes reports difficult to correlate with the active worker.

### F-14 - Low: tile-worker shutdown ignores failed waits and leaves queued deliveries connected

**Locations:**

- `src/VeraGrid/Gui/Diagrams/MapWidget/Tiles/tile_worker.py:43-125`
- `src/VeraGrid/Gui/Diagrams/MapWidget/Tiles/tiles.py:390-405`, `440-486`
- `src/VeraGrid/Gui/Main/SubClasses/Model/diagrams.py:378-402`

The map implementation correctly emits raw bytes and constructs `QPixmap` in the GUI thread. Diagram shutdown also stops workers and waits up to six seconds, which is materially safer than the general worker handling.

Residual issues are that the wait result is ignored and queued `tile_available` deliveries are not disconnected or rejected when `_shutdown` is true. `tile_is_available()` can still build/cache a pixmap after shutdown, although the map callback has been cleared. The network timeout is five seconds, so the six-second wait usually covers the active request; this is a lower-risk race, not a primary crash suspect.

## Worker coordination matrix

| Worker | Main shutdown coverage | Cooperative stop used | Completion guaranteed before teardown | Main risk |
|---|---|---|---|---|
| `GcThread` | Yes | Yes, but cancel emits false completion | No; 5 s result ignored; rerun uses `terminate()` | Critical |
| `FileOpenThread` | Yes | No | No; `quit()` cannot stop blocking `run()` | High |
| `FileSaveThread` | Yes | No | No; `quit()` cannot stop blocking `run()` | High |
| `ExportAllThread` | Yes | No | No; cancel flag is unused by export | High |
| `FileSyncThread` | Listed, apparently dormant in current Main flow | No from shutdown | No; sleep/open loop ignores `quit()` | Medium |
| `ServerDriver` | No | No during app close | No | High; direct GUI/model access |
| `RemoteJobDriver` | No | No cancellation API | No; removed on custom signal | High |
| AI `QThread`/`AiTurnWorker` | Separate 2 s shutdown | Cancellation queue is blocked by active slot | No | High |
| `TileWorker` | Yes, through diagram shutdown | Yes | Usually; 6 s result ignored | Low |
| `VideoExportWorker` | No, but currently calls `run()` synchronously | Not applicable | GUI is blocked until return | Low/latent |
| Grid-diff/profile modal workers | Local dialog ownership/guards | Varies | Mostly guarded locally | Low/residual |

## Known historical or external clean-crash mechanisms

### H-01 - Off-main-thread cyclic GC during file save

Commit `035186141` documented a save-time segmentation fault: process-global cyclic GC could run in `FileSaveThread`, finalize orphaned Qt/QGraphics wrappers on the worker thread, mutate a main-thread scene, and corrupt the heap. It temporarily disabled GC before starting a save and re-enabled it in the GUI callback.

Commit `6b6d8e67b` removed that workaround while adding `prepare_to_delete()`/`dispose_diagram_widget()` to eagerly clear scenes, detach widgets, and call `deleteLater()` on the GUI thread. Current code therefore contains a structural mitigation, and this audit does **not** classify the old save crash as a proven current defect. It remains a regression risk if any diagram/dialog path bypasses disposal or leaves a Qt reference cycle for a worker allocation to collect. The stale comment at `src/VeraGrid/Session/file_handler.py:244-246` still says `post_file_save()` re-enables GC even though current code no longer disables or enables it.

### H-02 - ARM macOS NumPy/OpenBLAS native crashes

`doc/md_source/installation.md:95-109` documents clean ARM macOS exits when NumPy is linked against OpenBLAS rather than Apple's Accelerate framework. This is independent of Qt/session ownership but can be indistinguishable to a user because it is a native process failure during numerical work.

### H-03 - Repository history corroborates cancellation and pointer lifetime as real crash classes

Relevant history includes `401967878` (“Fixed issue with crashing when cancelling”), `eb21f0fd2` (“added cancelling ... crashing, so investigate”), `5dc182866` (“Improved thread synchronization on cancel”), `ee81479c2` (a modeless GUI lacking a retained pointer caused clean crashes), `81863c6e0` (macOS dynamic-editor GUI pointer crash), `1ca918bd8` (dynamics GUI crash fixes), and `035186141` (save/diagram deletion crash). These commits do not prove every current path crashes, but they show the failure mechanisms have occurred in VeraGrid rather than being generic Qt speculation.

## Existing safeguards reviewed

The following areas already contain useful lifetime controls and should not be treated as the primary current defect without a reproduction:

- Diagram deletion routes through `prepare_to_delete()` and `dispose_diagram_widget()`, clearing scenes and models before `deleteLater()`.
- Dynamic result plot dialogs are retained in `_open_plot_dialogs`, use `WA_DeleteOnClose`, and embed Matplotlib rather than calling `pyplot.show()`.
- `dialog_lifecycle.is_dialog_available()` checks `shiboken6.isValid()` before reusing a PySide wrapper.
- Plugin windows are retained in `plugin_windows_list`; PSS/E, DGS, MATPOWER, UCTE, CGMES, analysis, Rosetta, and AI modeless windows are held on `self`.
- Schematic delayed branch callbacks include PySide validity checks introduced for prior clean-crash reports.
- Tile workers return bytes rather than constructing `QPixmap` off-thread, and map shutdown is invoked before the general thread shutdown.
- The subprocess “clean crash” GUI tests wait for file/simulation workers before deleting the main window. They validate orderly successful flows, but do not exercise close/cancel/project replacement while work is active, forced reruns, server mode, or the AI shutdown deadlock window.

## Highest-value reproduction targets

1. Run a long time-series study, press Cancel, and immediately start the same study again. Record whether the first worker is still running when `SimulationSession.run()` reaches `terminate()`.
2. Run a long study, then create/open a new project or activate another scenario before completion. Observe which circuit and diagrams the old post callback touches.
3. Close VeraGrid during a long save, open, export, RMS/EMT run, or solver call lasting more than five seconds. Capture Qt stderr and the return values of every `wait()`.
4. Enable server mode while a job list response is arriving and interact with/close the server table. Use Qt fatal warnings or a thread-affinity assertion to expose the model/widget calls.
5. Start an AI request or AI-triggered simulation, request cancellation, and close during its blocking main-thread status query.
6. On macOS, exercise each remaining Main/diagram plotting action that calls `plt.show()`.
7. Repeat save/open/delete-diagram cycles with GC thresholds lowered in a diagnostic build to check whether any orphaned QGraphics wrapper still finalizes in a worker.

Each crash reproduction should run in a child process, as the existing clean-crash tests do, so SIGABRT/SIGSEGV and exit codes can be distinguished from Python exceptions.

## Remediation order (recommendations only)

1. Remove `terminate()` from session control. Refuse a same-type rerun until cooperative cancellation has reached actual thread completion.
2. Split `cancel_requested`, `result_ready`, and native `QThread.finished`. Never emit completion from `DriverTemplate.cancel()` or from the GUI thread.
3. Give all workers one application-owned registry with explicit state. Project/scenario replacement and close must either wait for every worker or refuse/defer the destructive action.
4. Move server status and job payloads across queued signals; reset the label/model only in the GUI thread.
5. Include server, remote-job, AI, tile, and any future worker in the same shutdown contract. Treat a failed wait as a failed close, not as permission to destroy the worker.
6. Make AI cancellation state reachable without a queued slot behind the long operation, and remove the GUI-thread/worker `BlockingQueuedConnection` shutdown deadlock.
7. Remove broad `processEvents()` calls from launch/cleanup paths. Prefer natural event-loop return and explicit state transitions.
8. Replace remaining `plt.show()` GUI paths with the retained embedded-dialog pattern already used by dynamics results.
9. Add persistent fatal/Qt/Python diagnostics containing the active project generation and worker states before attempting broader defensive changes.

The first four items address concrete root causes shared by most of the findings; adding isolated pointer-validity checks to individual post handlers would only mask particular symptoms.
