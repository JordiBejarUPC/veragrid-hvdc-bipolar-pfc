# VeraGrid Qt window-lifecycle audit

## Scope

This report records static findings from scanning window and dialog creation, retention, deferred deletion, parent ownership, modal execution, and callback cleanup. The findings identify opportunities for invalid PySide wrappers, use-after-destruction, and native Qt/platform crashes. They do not establish that every path will segfault in normal execution.

## Findings

### W-01 - Retained plot-dialog list can contain destroyed wrappers

Plot dialogs are appended in multiple locations, including [`results.py:1030`](VeraGrid/Gui/Main/SubClasses/Results/results.py:1030) and [`schematic_widget.py:6300`](VeraGrid/Gui/Diagrams/SchematicWidget/schematic_widget.py:6300). The list is not connected to `destroyed()` and individual dialogs are not removed when closed. Later, [`base_gui.py:512`](VeraGrid/Gui/Main/SubClasses/base_gui.py:512) iterates the list and passes entries to window-management code. A dialog destroyed through parent teardown can leave an invalid PySide wrapper in the list; subsequent method calls can raise `RuntimeError` and, during Qt teardown, can reach native invalid-object paths.

### W-02 - Dynamic plot cleanup calls methods without validity checks

[`dynamic_plots_handler.py:5325-5332`](VeraGrid/Gui/DynamicModelEditor/Plots/dynamic_plots_handler.py:5325) calls `reject()` and `deleteLater()` on every retained dialog. The list is cleared only afterward. If a parent workspace or dialog already destroyed one of these windows, this is an invalid-wrapper/use-after-destruction opportunity.

### W-03 - Main plot cleanup has the same stale-reference risk

The main GUI retains plot dialogs in `_open_plot_dialogs`, while `close_open_child_windows()` relies on `is_dialog_available()` only at the point of closing. Other cleanup paths directly invoke dialog methods. The lifecycle is split between [`dialog_lifecycle.py:25-43`](VeraGrid/Gui/dialog_lifecycle.py:25) and ad hoc `reject()/deleteLater()` calls, so the registry can outlive the native objects.

### W-04 - Deferred deletion is exposed to nested callback delivery

[`dialog_lifecycle.py:88-103`](VeraGrid/Gui/dialog_lifecycle.py:88) schedules deletion after `exec()`. Callers may retain and reuse the dialog during the same nested event-loop period. A queued callback or parent close can destroy the C++ object before a later Python callback uses the wrapper.

### W-05 - Child cleanup can invalidate objects during iteration

[`dialog_lifecycle.py:47-68`](VeraGrid/Gui/dialog_lifecycle.py:47) collects child widgets, then calls `child.close()` and `child.deleteLater()` sequentially. `close()` can synchronously emit signals that delete or reparent other children. The original validity check does not protect the later `deleteLater()` call from intervening destruction.

### W-06 - Non-modal file dialogs use `WA_DeleteOnClose` while callbacks retain them

[`plot_dialogue.py:882-887`](VeraGrid/Gui/PlotDialogue/plot_dialogue.py:882) and [`qt_chart_widget.py:1732-1741`](VeraGrid/Gui/Widgets/qt_chart_widget.py:1732) create file dialogs with `WA_DeleteOnClose`, store them in `_active_save_dialog`, and rely on `finished` to clear the reference. A close callback, parent destruction, or nested event delivery can leave the stored wrapper invalid before code such as `selectedNameFilter()`, `raise_()`, or `activateWindow()` executes.

### W-07 - Chart disposal closes an active file dialog without verifying native lifetime

[`qt_chart_widget.py:1462-1483`](VeraGrid/Gui/Widgets/qt_chart_widget.py:1462) calls `_active_save_dialog.close()` and immediately clears the reference. A queued `fileSelected` or `finished` delivery may still target the chart while its parent is being disposed. The risk increases during application shutdown or diagram replacement.

### W-08 - Dynamic editor workspace replacement deletes widgets while callbacks remain connected

[`dynamic_editor_workspace_window.py:830-836`](VeraGrid/Gui/DynamicModelEditor/Workspace/dynamic_editor_workspace_window.py:830) calls `prepare_to_delete()`, detaches the page, and schedules `deleteLater()`. Any queued model, breadcrumb, timer, or editor callback that retains the page can run after detachment and access deleted child widgets or models.

### W-09 - Dynamic editor tab replacement has the same queued-callback window

[`dynamic_editor_tab.py:500-508`](VeraGrid/Gui/DynamicModelEditor/Workspace/Tabs/dynamic_editor_tab.py:500) detaches and deletes the editor after cleanup. The code disconnects selected signals but does not establish a general destroyed-state guard for all queued callbacks owned by the editor.

### W-10 - Window close can continue after a child refuses or outlives close

[`base_gui.py:535-554`](VeraGrid/Gui/Main/SubClasses/base_gui.py:535) treats `window.close()` as sufficient unless it returns false. A successful close does not mean the C++ object has been destroyed or that queued callbacks have drained. Subsequent main-window teardown can therefore race deferred deletion and worker callbacks.

### W-11 - AI dialogue intentionally remains non-delete-on-close

[`ai_chat_dialogue.py:5034-5041`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:5034) sets `WA_DeleteOnClose` to `False`, while the dialogue owns worker/thread state and is shown modelessly at [`ai_chat_dialogue.py:7095-7102`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:7095). This avoids one deletion path, but leaves a live window and callbacks during shutdown. If the parent/main window is destroyed before the AI worker stops, queued callbacks can target an invalid dialogue or its child widgets.

### W-12 - Modeless windows are not consistently paired with retained ownership or destroyed cleanup

Examples include [`ai_chat_dialogue.py:7097`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:7097) and dynamic editor workspace creation in [`base_gui.py`](VeraGrid/Gui/Main/SubClasses/base_gui.py). Where the caller does not retain the window or connect `destroyed()` to clear the owner reference, later reuse can operate on an already-deleted wrapper.

### W-13 - Nested modal execution increases reentrancy exposure

[`dialog_lifecycle.py:93`](VeraGrid/Gui/dialog_lifecycle.py:93) invokes `dialog.exec()`, creating a nested event loop. During that loop, project replacement, parent closure, worker completion, or explicit cleanup can destroy or reparent the dialog or its owner. Code after `exec()` assumes the wrapper remains valid except for the narrow final check.

### W-14 - Plot-dialog close paths do not consistently remove ownership references

[`dynamic_plots_handler.py:5325-5332`](VeraGrid/Gui/DynamicModelEditor/Plots/dynamic_plots_handler.py:5325) and the main `_open_plot_dialogs` registry use bulk cleanup, but no `destroyed` connection removes individual entries. Repeated open/close cycles therefore accumulate stale or closed window references, increasing the probability of invalid-wrapper calls during later cleanup.

### W-15 - Window teardown combined with live workers is the highest-risk native crash chain

A dialog or diagram can be deleted through `deleteLater()` while a simulation, server, AI, or remote worker still emits callbacks into it. The window-lifecycle code has validity checks in some paths, but those checks do not establish callback disconnection or worker completion before destruction. This creates the most plausible route from a stale window pointer to a native Qt/platform segfault.

