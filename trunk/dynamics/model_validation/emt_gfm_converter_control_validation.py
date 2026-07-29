#!/usr/bin/env python3
"""Run converter-control experiments using the EMT GFM validation harness.

This script intentionally reuses ``emt_gfm_model_validation.py`` as the base
case. Differences should stay limited to converter-control parameters exposed by
``build_emt_gfm_aggregated_model`` so experiments do not fork the grid, source,
line, plotting, or diagnostic logic.
"""

from __future__ import annotations

import os


def set_default(name: str, value: str) -> None:
    os.environ.setdefault(name, value)


# Keep these aligned with the current stable defaults in
# ``build_emt_gfm_aggregated_model``. Override them from the shell for sweeps.
set_default("VERAGRID_GFM_EMT_KP_ICL", "0.001")
set_default("VERAGRID_GFM_EMT_KI_ICL", "1.0")
set_default("VERAGRID_GFM_EMT_KDP", "0.05")
set_default("VERAGRID_GFM_EMT_KDQ", "0.005")

# The shorter horizon is the useful control-debug default; callers can override.
set_default("VERAGRID_GFM_EMT_SIM_TIME", "0.1")
set_default("VERAGRID_GFM_EMT_TIME_STEP", "0.0001")
set_default("VERAGRID_GFM_EMT_WARMUP_TIME", "0")
set_default(
    "VERAGRID_GFM_EMT_PLOT_OUTPUT_DIR",
    os.path.join(os.path.dirname(__file__), "emt_gfm_converter_control_validation_plots"),
)

from emt_gfm_model_validation import main  # noqa: E402


if __name__ == "__main__":
    main()
