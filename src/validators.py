"""Public interface for running BLSN simulation-parameter sanity checks.

This thin shim exposes `run_sanity_checks` so external callers and tests can
validate parameters without importing private pipeline helpers directly.
"""

from __future__ import annotations

from src.pipeline import _fallback_sanity_checks


def run_sanity_checks(params: dict) -> None:
    """Run sanity checks on *params*; raises ``RuntimeError`` on failure.

    Delegates to the pipeline's built-in fallback checker which validates that
    ``nominal_mass_flow_g_s`` is strictly between ``min_limit_g_s`` and
    ``max_limit_g_s``.  Returns ``None`` on success.
    """
    _fallback_sanity_checks(params)
