"""
Backward-compatible wrapper around the shared MDHEM implementation.
"""

from __future__ import annotations

from mdhelm import *  # noqa: F401,F403
from mdhelm import run_case14_artifact_demo


if __name__ == "__main__":
    run_case14_artifact_demo()
