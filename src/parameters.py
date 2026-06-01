"""Public interface for loading BLSN SSOT simulation parameters.

This thin shim exposes `load_config` so external callers and tests can obtain
the `simulation_parameters` block without importing private pipeline helpers.
"""

from __future__ import annotations

from src.pipeline import _load_ssot


def load_config(path: str) -> dict:
    """Load the SSOT file at *path* and return its ``simulation_parameters`` block.

    Returns an empty dict if the block is absent or not a mapping, so callers
    can safely key into the result without extra ``None`` guards.
    """
    ssot = _load_ssot(path)
    params = ssot.get("simulation_parameters", {})
    return params if isinstance(params, dict) else {}
