# VeraGrid Qt window-lifecycle audit

## Scope

This report records static findings from scanning window and dialog creation, retention, deferred deletion, parent ownership, modal execution, and callback cleanup. The findings identify opportunities for invalid PySide wrappers, use-after-destruction, and native Qt/platform crashes. They do not establish that every path will segfault in normal execution.

## Findings

### W-01 - Retained plot-dialog list can contain destroyed wrappers

Plot dialogs are appended in multiple locations, including [`results.py:1030`](VeraGrid/Gui/Main/SubClasses/Results/results.py:1030) and [`schematic_widget.py:6300`](VeraGrid/Gui/Diagrams/SchematicWidget/schematic_widget.py:6300). The list is not connected to `destroyed()` and individual dialogs are not removed when closed. Later, [`base_gui.py:512`](VeraGrid/Gui/Main/SubClasses/base_gui.py:512) iterates the list and passes entries to window-management code.

Concrete trigger: open a plot, close/destroy its parent diagram or main window, then invoke any path that calls `get_open_lock_managed_windows()`. The stale list entry is passed to `append_lock_managed_window()` and can later be used by `close_open_child_windows()`.

### W-02 - Dynamic plot cleanup calls methods without validity checks

[`dynamic_plots_handler.py:5325-5332`](VeraGrid/Gui/DynamicModelEditor/Plots/dynamic_plots_handler.py:5325) calls `reject()` and `deleteLater()` on every retained dialog. The list is cleared only afterward.

Concrete trigger: show a dynamic plot, close its workspace so Qt destroys the child dialog, then close the dynamic editor or activate another plot group. `close_plot_dialogs()` can call `reject()` on the stale wrapper before clearing `_open_plot_dialogues`.

### W-03 - Main plot cleanup has the same stale-reference risk

The main GUI retains plot dialogs in `_open_plot_dialogs`, while `close_open_child_windows()` relies on `is_dialog_available()` only at the point of closing. Other cleanup paths directly invoke dialog methods.

Concrete trigger: open any plot from `results.py`, close its owning main window or parent widget, then run main-window child-window cleanup. The list still contains the dialog, but its C++ object may already be gone; any path that bypasses `is_dialog_available()` and calls `reject()`, `close()`, or `deleteLater()` can touch the invalid wrapper.

### W-04 - Deferred deletion is exposed to nested callback delivery

[`dialog_lifecycle.py:88-103`](VeraGrid/Gui/dialog_lifecycle.py:88) schedules deletion after `exec()`. `exec()` runs a nested event loop, so another callback can close the parent or invoke cleanup before the caller resumes.

Concrete trigger: call `exec_dialog_safely(dialog)`, have a timer or worker completion close the parent while the modal dialog is running, then let the original caller continue using fields or child widgets populated by the dialog. The wrapper validity is checked only in the cleanup block, not by callers using the returned object or retained references afterward.

### W-05 - Child cleanup can invalidate objects during iteration

[`dialog_lifecycle.py:47-68`](VeraGrid/Gui/dialog_lifecycle.py:47) collects child widgets, then calls `child.close()` and `child.deleteLater()` sequentially.

Concrete trigger: a child `closeEvent` or connected `finished` handler destroys another child while `delete_child_widgets_safely()` is iterating its snapshot. The snapshot still contains the destroyed wrapper; the next `shiboken6.isValid()` check protects that child, but any signal emitted by `close()` can also invalidate the current child between the check and `deleteLater()`.

### W-06 - Non-modal file dialogs use `WA_DeleteOnClose` while callbacks retain them

[`plot_dialogue.py:882-887`](VeraGrid/Gui/PlotDialogue/plot_dialogue.py:882) and [`qt_chart_widget.py:1732-1741`](VeraGrid/Gui/Widgets/qt_chart_widget.py:1732) create file dialogs with `WA_DeleteOnClose`, store them in `_active_save_dialog`, and rely on `finished` to clear the reference.

Concrete trigger: open the chart save dialog, destroy the chart/dialog parent before the file dialog's `finished` callback clears `_active_save_dialog`, then invoke `save_image()` or `_save_image_from_context_menu()` again. The `else` branch calls `raise_()` and `activateWindow()` on the stored wrapper.

### W-07 - Chart disposal closes an active file dialog without verifying native lifetime

[`qt_chart_widget.py:1462-1483`](VeraGrid/Gui/Widgets/qt_chart_widget.py:1462) calls `_active_save_dialog.close()` and immediately clears the reference.

Concrete trigger: close a chart while its save dialog is open. `dispose()` closes the dialog while `fileSelected`/`finished` deliveries may already be queued; those slots still target the chart and can execute while `dispose()` or parent destruction is in progress.

### W-08 - Dynamic editor workspace replacement deletes widgets while callbacks remain connected

[`dynamic_editor_workspace_window.py:830-836`](VeraGrid/Gui/DynamicModelEditor/Workspace/dynamic_editor_workspace_window.py:830) calls `prepare_to_delete()`, detaches the page, and schedules `deleteLater()`.

Concrete trigger: close an open dynamic-editor page while a queued breadcrumb/model update is pending. The page is removed from the workspace before deferred deletion executes, but queued callbacks can still call page-owned widgets or models after `prepare_to_delete()`.

### W-09 - Dynamic editor tab replacement has the same queued-callback window

[`dynamic_editor_tab.py:500-508`](VeraGrid/Gui/DynamicModelEditor/Workspace/Tabs/dynamic_editor_tab.py:500) detaches and deletes the editor after cleanup. The code disconnects selected signals but does not establish a general destroyed-state guard for all queued callbacks owned by the editor.

Concrete trigger: close a tab while an editor signal or timer callback is queued. `_close_editor()` sets `self._editor = None` only after `editor.deleteLater()`, so a callback already holding the editor can run during deferred destruction and access its child widgets.

### W-10 - Window close can continue after a child refuses or outlives close

[`base_gui.py:535-554`](VeraGrid/Gui/Main/SubClasses/base_gui.py:535) treats `window.close()` as sufficient unless it returns false. A successful close does not mean the C++ object has been destroyed or that queued callbacks have drained.

Concrete trigger: invoke `close_open_child_windows(delete_windows=True)` during main-window shutdown. It calls `window.close()` and then `delete_dialog_safely()`, which only schedules `deleteLater()`; shutdown can continue immediately while queued callbacks or worker signals still target that window.

### W-11 - AI dialogue intentionally remains non-delete-on-close

[`ai_chat_dialogue.py:5034-5041`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:5034) sets `WA_DeleteOnClose` to `False`, while the dialogue owns worker/thread state and is shown modelessly at [`ai_chat_dialogue.py:7095-7102`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:7095).

Concrete trigger: start an AI request, close the main window while the request is active, and allow the dialog/thread shutdown timeout to expire. The worker can continue emitting progress or completion signals to the dialogue after main-window teardown has started.

### W-12 - Modeless windows are not consistently paired with retained ownership or destroyed cleanup

Examples include [`ai_chat_dialogue.py:7097`](VeraGrid/Gui/AiAgent/ai_chat_dialogue.py:7097) and dynamic editor workspace creation in [`base_gui.py`](VeraGrid/Gui/Main/SubClasses/base_gui.py). Where the caller does not retain the window or connect `destroyed()` to clear the owner reference, later reuse can operate on an already-deleted wrapper.

Concrete trigger: create a modeless window, close it through Qt parent destruction, then invoke the owning feature a second time while its Python attribute still references the old object. The second invocation can call `show()`, `raise_()`, or child-widget methods on the invalid wrapper.

### W-13 - Nested modal execution increases reentrancy exposure

[`dialog_lifecycle.py:93`](VeraGrid/Gui/dialog_lifecycle.py:93) invokes `dialog.exec()`, creating a nested event loop.

Concrete trigger: while a modal import/options dialog is open, activate a queued project-close, scenario-change, or worker-completion callback. That callback can replace the dialog's parent or invoke global window cleanup before `exec()` returns; the original call stack then resumes with references captured before the nested event loop.

### W-14 - Plot-dialog close paths do not consistently remove ownership references

[`dynamic_plots_handler.py:5325-5332`](VeraGrid/Gui/DynamicModelEditor/Plots/dynamic_plots_handler.py:5325) and the main `_open_plot_dialogs` registry use bulk cleanup, but no `destroyed` connection removes individual entries.

Concrete trigger: repeatedly open and manually close plot dialogs, then clear results or close the main window. The registries still contain every prior dialog, so bulk cleanup traverses all historical wrappers and calls close/reject/delete operations on entries that may already have been destroyed.

### W-15 - Window teardown combined with live workers is the highest-risk native crash chain

A concrete combined trigger is: start a long simulation or AI request, open a result/plot dialog, replace the project or close the main window, allow the shutdown wait to expire, and let the worker emit its completion signal afterward. The dialog/diagram can already be scheduled for `deleteLater()` while the worker callback still invokes GUI methods. The window-lifecycle code has validity checks in some paths, but does not establish callback disconnection and worker completion before destruction. This is the most plausible route from a stale window pointer to a native Qt/platform segfault.

