"""Wave 12/15 statistical process control, DoE foundation, and drift detection engine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go

try:
    from scipy import stats as _scipy_stats  # type: ignore[import-untyped]

    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional at import time
    _scipy_stats = None  # type: ignore[assignment]
    _SCIPY_AVAILABLE = False

# Standardized dashboard palette (Tailwind Cyan / Emerald / Rose / Slate)
COLORS = {
    "primary": "#06b6d4",               # Cyan 500
    "success": "#10b981",               # Emerald 500
    "danger": "#f43f5e",                # Rose 500
    "text": "#64748b",                  # Slate 500
    "grid": "rgba(100, 116, 139, 0.2)",
}

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PYTEST_TELEMETRY_PATH = DOCS_DIR / "pytest_telemetry.json"
LEDGER_PATH = DOCS_DIR / "historical_telemetry_ledger.json"
DOE_MATRIX_PATH = DOCS_DIR / "experimental_design_matrix.json"
KPI_DASHBOARD_PATH = DOCS_DIR / "kpi_dashboard.json"
VISUALS_DIR = DOCS_DIR / "visuals"
PLOTLY_PAYLOAD_PATH = VISUALS_DIR / "plotly_payloads.json"
DRIFT_ALERTS_PATH = DOCS_DIR / "_data" / "drift_alerts.json"

# Wave 15 constants
_DRIFT_WINDOW = 10        # number of historical runs used for the moving baseline
_DRIFT_SIGMA = 3.0        # Z-score threshold (3σ rule)
_TTEST_ALPHA = 0.05       # significance level for regression T-test


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

    return data if isinstance(data, dict) else default


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _collect_run_context() -> dict[str, str]:
    os_factor = os.getenv("BLSN_MATRIX_OS") or os.getenv("RUNNER_OS") or "unknown-os"
    py_factor = os.getenv("BLSN_MATRIX_PYTHON") or os.getenv("PYTHON_VERSION") or "unknown-python"
    load_factor = os.getenv("BLSN_LOAD_PARAMETER") or os.getenv("BLSN_LOAD") or "default-load"

    return {
        "os_type": str(os_factor),
        "python_version": str(py_factor),
        "load_parameter": str(load_factor),
    }


def _build_run_record(pytest_report: dict) -> dict:
    summary = pytest_report.get("summary", {}) if isinstance(pytest_report, dict) else {}
    summary = summary if isinstance(summary, dict) else {}

    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    skipped = int(summary.get("skipped", 0) or 0)
    total = int(summary.get("total", 0) or passed + failed + skipped)

    runtime = pytest_report.get("duration", summary.get("duration", 0.0))
    try:
        runtime_seconds = float(runtime)
    except (TypeError, ValueError):
        runtime_seconds = 0.0

    run_id = os.getenv("GITHUB_RUN_ID")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
    matrix = _collect_run_context()
    matrix_key = f"{matrix['os_type']}|{matrix['python_version']}|{matrix['load_parameter']}"
    resolved_run_id = (
        f"gh-{run_id}-{run_attempt}-{matrix_key}" if run_id else f"local-{datetime.now(timezone.utc).isoformat()}"
    )

    return {
        "run_id": resolved_run_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "factors": matrix,
        "runtime_seconds": round(runtime_seconds, 6),
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "pass_rate": _safe_rate(passed, total),
        "fail_rate": _safe_rate(failed, total),
        "skip_rate": _safe_rate(skipped, total),
        "success": failed == 0,
    }


def _normalize_ledger(ledger: dict) -> dict:
    runs = ledger.get("runs", []) if isinstance(ledger, dict) else []
    if not isinstance(runs, list):
        runs = []

    normalized = {
        "meta": {
            "total_attempts": 0,
            "total_successful_runs": 0,
            "success_rate": 0.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "runs": [run for run in runs if isinstance(run, dict)],
    }

    attempts = len(normalized["runs"])
    successful = len([run for run in normalized["runs"] if bool(run.get("success", False))])
    normalized["meta"]["total_attempts"] = attempts
    normalized["meta"]["total_successful_runs"] = successful
    normalized["meta"]["success_rate"] = _safe_rate(successful, attempts)

    return normalized


def _upsert_run(ledger: dict, current_run: dict) -> dict:
    existing_runs = [run for run in ledger.get("runs", []) if isinstance(run, dict)]
    filtered_runs = [run for run in existing_runs if run.get("run_id") != current_run.get("run_id")]
    filtered_runs.append(current_run)

    updated = {
        "meta": ledger.get("meta", {}),
        "runs": filtered_runs,
    }
    return _normalize_ledger(updated)


def calculate_deltas(current_run: dict, previous_runs: list[dict]) -> dict:
    if not previous_runs:
        return {
            "runtime_delta_vs_moving_avg": round(float(current_run.get("runtime_seconds", 0.0)), 6),
            "pass_rate_delta_vs_moving_avg": round(float(current_run.get("pass_rate", 0.0)), 6),
            "fail_rate_delta_vs_moving_avg": round(float(current_run.get("fail_rate", 0.0)), 6),
            "previous_runtime_moving_avg": 0.0,
            "previous_pass_rate_moving_avg": 0.0,
            "previous_fail_rate_moving_avg": 0.0,
        }

    runtime_avg = sum(float(run.get("runtime_seconds", 0.0)) for run in previous_runs) / len(previous_runs)
    pass_rate_avg = sum(float(run.get("pass_rate", 0.0)) for run in previous_runs) / len(previous_runs)
    fail_rate_avg = sum(float(run.get("fail_rate", 0.0)) for run in previous_runs) / len(previous_runs)

    current_runtime = float(current_run.get("runtime_seconds", 0.0))
    current_pass_rate = float(current_run.get("pass_rate", 0.0))
    current_fail_rate = float(current_run.get("fail_rate", 0.0))

    return {
        "runtime_delta_vs_moving_avg": round(current_runtime - runtime_avg, 6),
        "pass_rate_delta_vs_moving_avg": round(current_pass_rate - pass_rate_avg, 6),
        "fail_rate_delta_vs_moving_avg": round(current_fail_rate - fail_rate_avg, 6),
        "previous_runtime_moving_avg": round(runtime_avg, 6),
        "previous_pass_rate_moving_avg": round(pass_rate_avg, 6),
        "previous_fail_rate_moving_avg": round(fail_rate_avg, 6),
    }


def detect_drift(
    current_run: dict[str, Any],
    historical_ledger: dict[str, Any],
    window: int = _DRIFT_WINDOW,
    sigma_threshold: float = _DRIFT_SIGMA,
) -> dict[str, Any]:
    """Wave 15: Z-Score drift detection on ``runtime_seconds``.

    Compares the current run's runtime against the rolling mean and standard
    deviation of the most recent *window* historical runs.  A run is flagged as
    a "Performance Drift" event when its Z-score exceeds *sigma_threshold*.

    Returns a result dict that is always safe to serialise to JSON.
    """
    runs = historical_ledger.get("runs", []) if isinstance(historical_ledger, dict) else []
    runs = [r for r in runs if isinstance(r, dict)]

    # Exclude the current run from the baseline window so we don't self-compare.
    current_run_id = current_run.get("run_id")
    baseline_runs = [r for r in runs if r.get("run_id") != current_run_id]
    baseline_window = baseline_runs[-window:] if len(baseline_runs) > window else baseline_runs

    current_runtime = float(current_run.get("runtime_seconds", 0.0) or 0.0)

    insufficient_data = len(baseline_window) < 2
    if insufficient_data:
        return {
            "drift_detected": False,
            "z_score": 0.0,
            "mean_runtime_s": 0.0,
            "std_runtime_s": 0.0,
            "current_runtime_s": round(current_runtime, 6),
            "delta_pct": 0.0,
            "window_size": len(baseline_window),
            "sigma_threshold": sigma_threshold,
            "insufficient_data": True,
            "details": f"Insufficient baseline data ({len(baseline_window)} runs; need ≥2).",
        }

    baseline_runtimes = np.array(
        [float(r.get("runtime_seconds", 0.0) or 0.0) for r in baseline_window], dtype=float
    )
    mean_rt = float(np.mean(baseline_runtimes))
    std_rt = float(np.std(baseline_runtimes, ddof=1))  # sample std

    if std_rt <= 0.0:
        z_score = 0.0
    else:
        z_score = (current_runtime - mean_rt) / std_rt

    drift_detected = abs(z_score) > sigma_threshold
    delta_pct = ((current_runtime - mean_rt) / mean_rt * 100.0) if mean_rt != 0.0 else 0.0

    details = (
        f"Performance Drift Detected: {delta_pct:+.1f}% runtime change vs. mean "
        f"({current_runtime:.3f}s vs. μ={mean_rt:.3f}s, σ={std_rt:.3f}s, Z={z_score:.2f})"
        if drift_detected
        else f"No drift detected (Z={z_score:.2f}, threshold=±{sigma_threshold}σ)."
    )

    return {
        "drift_detected": drift_detected,
        "z_score": round(z_score, 6),
        "mean_runtime_s": round(mean_rt, 6),
        "std_runtime_s": round(std_rt, 6),
        "current_runtime_s": round(current_runtime, 6),
        "delta_pct": round(delta_pct, 4),
        "window_size": len(baseline_window),
        "sigma_threshold": sigma_threshold,
        "insufficient_data": False,
        "details": details,
    }


def analyze_matrix_regression(doe_matrix: dict[str, Any]) -> dict[str, Any]:
    """Wave 15: T-test regression analysis across CI matrix factor levels.

    Groups ``pca_ready_rows`` by ``python_version`` (Factor A) and performs
    pairwise Welch's T-tests (unequal variance) on ``runtime_seconds``.  Any
    pair whose p-value falls below *_TTEST_ALPHA* is flagged as a statistically
    significant regression.

    Returns a result dict that is always safe to serialise to JSON.
    """
    rows = doe_matrix.get("pca_ready_rows", []) if isinstance(doe_matrix, dict) else []
    rows = [r for r in rows if isinstance(r, dict)]

    # Group runtimes by python_version factor level.
    groups: dict[str, list[float]] = {}
    for row in rows:
        label = str(row.get("python_version", "unknown"))
        groups.setdefault(label, []).append(float(row.get("runtime_seconds", 0.0) or 0.0))

    factor_levels = sorted(groups.keys())
    comparisons: list[dict[str, Any]] = []
    regression_detected = False

    for i in range(len(factor_levels)):
        for j in range(i + 1, len(factor_levels)):
            level_a = factor_levels[i]
            level_b = factor_levels[j]
            samples_a = groups[level_a]
            samples_b = groups[level_b]

            if len(samples_a) < 2 or len(samples_b) < 2:
                comparisons.append(
                    {
                        "factor": "python_version",
                        "group_a": level_a,
                        "group_b": level_b,
                        "n_a": len(samples_a),
                        "n_b": len(samples_b),
                        "t_statistic": None,
                        "p_value": None,
                        "significant": False,
                        "note": "Insufficient samples for T-test (need ≥2 per group).",
                    }
                )
                continue

            if _SCIPY_AVAILABLE and _scipy_stats is not None:
                t_stat, p_val = _scipy_stats.ttest_ind(samples_a, samples_b, equal_var=False)
            else:
                # Welch's T-test manual fallback (no scipy).
                arr_a = np.array(samples_a, dtype=float)
                arr_b = np.array(samples_b, dtype=float)
                mean_a, mean_b = float(np.mean(arr_a)), float(np.mean(arr_b))
                var_a = float(np.var(arr_a, ddof=1))
                var_b = float(np.var(arr_b, ddof=1))
                se = (var_a / len(arr_a) + var_b / len(arr_b)) ** 0.5
                t_stat = (mean_a - mean_b) / se if se > 0 else 0.0
                # Approximate p-value via normal CDF (conservative for small n).
                p_val = float(2.0 * (1.0 - float(np.exp(-0.5 * t_stat**2) / (2.0 * np.pi) ** 0.5)))
                p_val = min(max(p_val, 0.0), 1.0)

            t_stat_f = float(t_stat)
            p_val_f = float(p_val)
            significant = p_val_f < _TTEST_ALPHA
            if significant:
                regression_detected = True

            comparisons.append(
                {
                    "factor": "python_version",
                    "group_a": level_a,
                    "group_b": level_b,
                    "n_a": len(samples_a),
                    "n_b": len(samples_b),
                    "t_statistic": round(t_stat_f, 6),
                    "p_value": round(p_val_f, 6),
                    "significant": significant,
                    "alpha": _TTEST_ALPHA,
                    "note": (
                        f"Significant regression between {level_a} and {level_b} "
                        f"(p={p_val_f:.4f} < α={_TTEST_ALPHA})."
                        if significant
                        else f"No significant regression (p={p_val_f:.4f} ≥ α={_TTEST_ALPHA})."
                    ),
                }
            )

    summary = (
        f"Regression detected in {sum(1 for c in comparisons if c.get('significant'))} "
        f"of {len(comparisons)} factor-level comparison(s)."
        if comparisons
        else "No factor-level comparisons available (need ≥2 distinct python_version levels with ≥2 samples each)."
    )

    return {
        "regression_detected": regression_detected,
        "factor_levels_analyzed": factor_levels,
        "comparisons": comparisons,
        "scipy_available": _SCIPY_AVAILABLE,
        "summary": summary,
    }


def build_drift_alerts_payload(
    drift_result: dict[str, Any],
    regression_result: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the consolidated Wave 15 alert payload for the dashboard and Jekyll."""
    any_alert = drift_result.get("drift_detected", False) or regression_result.get("regression_detected", False)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wave": "15",
        "any_alert": any_alert,
        "drift": drift_result,
        "regression": regression_result,
    }


def generate_doe_matrix(runs: list[dict]) -> dict:
    factors = {
        "A": "python_version",
        "B": "os_type",
        "C": "load_parameter",
    }

    levels = {
        "A": sorted({str(run.get("factors", {}).get("python_version", "unknown")) for run in runs}),
        "B": sorted({str(run.get("factors", {}).get("os_type", "unknown")) for run in runs}),
        "C": sorted({str(run.get("factors", {}).get("load_parameter", "unknown")) for run in runs}),
    }

    grouped: dict[str, list[float]] = {}
    for run in runs:
        run_factors = run.get("factors", {}) if isinstance(run.get("factors"), dict) else {}
        key = "|".join(
            [
                str(run_factors.get("python_version", "unknown")),
                str(run_factors.get("os_type", "unknown")),
                str(run_factors.get("load_parameter", "unknown")),
            ]
        )
        grouped.setdefault(key, []).append(float(run.get("runtime_seconds", 0.0)))

    runs_with_replicates = []
    for combination, runtimes in grouped.items():
        py_ver, os_type, load = combination.split("|", maxsplit=2)
        for replicate_index, runtime in enumerate(runtimes, start=1):
            runs_with_replicates.append(
                {
                    "factors": {"A": py_ver, "B": os_type, "C": load},
                    "response": {"runtime_seconds": round(runtime, 6)},
                    "replicate": replicate_index,
                }
            )

    anova_ready_groups = [runtimes for runtimes in grouped.values() if runtimes]

    pca_ready_rows = [
        {
            "python_version": str(run.get("factors", {}).get("python_version", "unknown")),
            "os_type": str(run.get("factors", {}).get("os_type", "unknown")),
            "load_parameter": str(run.get("factors", {}).get("load_parameter", "unknown")),
            "runtime_seconds": float(run.get("runtime_seconds", 0.0)),
            "pass_rate": float(run.get("pass_rate", 0.0)),
            "fail_rate": float(run.get("fail_rate", 0.0)),
        }
        for run in runs
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "factor_map": factors,
        "strict_independence_note": "Factors A, B, and C are treated as independent CI matrix variables.",
        "levels": levels,
        "runs_with_replicates": runs_with_replicates,
        "anova_ready_groups": anova_ready_groups,
        "pca_ready_rows": pca_ready_rows,
    }


def _build_telemetry_matrix(runs: list[dict]) -> tuple[np.ndarray, list[str]]:
    variable_names = ["runtime_seconds", "pass_rate", "fail_rate", "skip_rate", "total_tests"]
    rows: list[list[float]] = []
    for run in runs:
        rows.append(
            [
                float(run.get("runtime_seconds", 0.0)),
                float(run.get("pass_rate", 0.0)),
                float(run.get("fail_rate", 0.0)),
                float(run.get("skip_rate", 0.0)),
                float(run.get("total_tests", 0.0)),
            ]
        )

    if not rows:
        rows = [[0.0 for _ in variable_names]]

    return np.array(rows, dtype=float), variable_names


def calculate_explicit_pca(telemetry_matrix: np.ndarray) -> dict:
    matrix = np.asarray(telemetry_matrix, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("telemetry_matrix must be a 2D array")

    if matrix.shape[0] < 2:
        matrix = np.vstack([matrix, matrix])

    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    covariance_matrix = np.cov(centered, rowvar=False)

    if np.ndim(covariance_matrix) == 0:
        covariance_matrix = np.array([[float(covariance_matrix)]], dtype=float)
    elif np.ndim(covariance_matrix) == 1:
        covariance_matrix = np.diag(covariance_matrix.astype(float))

    eigenvalues, eigenvectors = np.linalg.eigh(covariance_matrix)
    sort_indices = np.argsort(eigenvalues)[::-1]
    sorted_eigenvalues = eigenvalues[sort_indices]
    sorted_eigenvectors = eigenvectors[:, sort_indices]

    total_eigenvalue = float(np.sum(sorted_eigenvalues))
    if total_eigenvalue <= 0:
        explained_variance_ratio = np.zeros_like(sorted_eigenvalues)
    else:
        explained_variance_ratio = sorted_eigenvalues / total_eigenvalue

    return {
        "covariance_matrix": covariance_matrix.tolist(),
        "eigenvalues": sorted_eigenvalues.tolist(),
        "eigenmatrix": sorted_eigenvectors.tolist(),
        "explained_variance_ratio": explained_variance_ratio.tolist(),
    }


def _transparent_layout(title: str, is_empty: bool = False) -> dict:
    """SSOT transparent layout for seamless light/dark mode switching."""
    layout: dict = {
        "title": {"text": title, "font": {"color": COLORS["text"]}},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text"]},
        "xaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
        "yaxis": {"gridcolor": COLORS["grid"], "zerolinecolor": COLORS["grid"]},
        "margin": {"l": 40, "r": 40, "t": 60, "b": 40},
    }
    if is_empty:
        layout.update(
            {
                "xaxis": {"visible": False},
                "yaxis": {"visible": False},
                "annotations": [
                    {
                        "text": "No telemetry data available for this context",
                        "showarrow": False,
                        "xref": "paper",
                        "yref": "paper",
                        "x": 0.5,
                        "y": 0.5,
                        "font": {"color": COLORS["text"]},
                    }
                ],
            }
        )
    return layout


def _empty_figure_payload(title: str) -> dict:
    figure = go.Figure()
    figure.update_layout(**_transparent_layout(title, is_empty=True))
    return json.loads(figure.to_json())


def generate_plotly_json(telemetry_data: dict, pca_data: dict) -> dict:
    runs = telemetry_data.get("runs", []) if isinstance(telemetry_data, dict) else []
    runs = [run for run in runs if isinstance(run, dict)]

    telemetry_labels: list[str] = []
    runtime_seconds: list[float] = []
    passed_counts: list[int] = []
    failed_counts: list[int] = []

    for run in runs:
        telemetry_labels.append(str(run.get("captured_at") or run.get("run_id") or f"run-{len(telemetry_labels) + 1}"))
        runtime_seconds.append(float(run.get("runtime_seconds", 0.0) or 0.0))
        passed_counts.append(int(run.get("passed", 0) or 0))
        failed_counts.append(int(run.get("failed", 0) or 0))

    # --- EXECUTIVE VIEW: Telemetry combo (health + duration) ---
    if telemetry_labels:
        telemetry_figure = go.Figure()
        telemetry_figure.add_trace(
            go.Bar(x=telemetry_labels, y=passed_counts, name="Passed", marker_color=COLORS["success"])
        )
        telemetry_figure.add_trace(
            go.Bar(x=telemetry_labels, y=failed_counts, name="Failed", marker_color=COLORS["danger"])
        )
        telemetry_figure.add_trace(
            go.Scatter(
                x=telemetry_labels,
                y=runtime_seconds,
                mode="lines+markers",
                name="Execution Time (s)",
                yaxis="y2",
                line={"color": COLORS["primary"], "width": 3},
            )
        )

        density_menus = [
            {
                "type": "buttons",
                "direction": "right",
                "x": 1.0,
                "y": 1.15,
                "buttons": [
                    {"label": "Grouped", "method": "relayout", "args": [{"barmode": "group"}]},
                    {"label": "Stacked", "method": "relayout", "args": [{"barmode": "stack"}]},
                ],
            }
        ]

        layout = _transparent_layout("Execution Health & Duration")
        layout.update(
            {
                "barmode": "group",
                "updatemenus": density_menus,
                "yaxis2": {
                    "title": "Time (s)",
                    "overlaying": "y",
                    "side": "right",
                    "gridcolor": COLORS["grid"],
                },
                "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
            }
        )
        telemetry_figure.update_layout(**layout)
        telemetry_payload = json.loads(telemetry_figure.to_json())
    else:
        telemetry_payload = _empty_figure_payload("Execution Health & Duration")

    # --- ENGINEERING VIEW: PCA bottleneck contribution ---
    pca_payload = _empty_figure_payload("PCA Bottleneck Contribution (PC1)")
    if isinstance(pca_data, dict):
        variable_names = pca_data.get("variable_names", [])
        eigenmatrix = pca_data.get("eigenmatrix", [])
        variable_names = [str(name) for name in variable_names] if isinstance(variable_names, list) else []
        eigenmatrix = eigenmatrix if isinstance(eigenmatrix, list) else []

        bottleneck_scores: list[tuple[str, float]] = []
        for variable_index, variable_name in enumerate(variable_names):
            if variable_index >= len(eigenmatrix):
                continue
            vector = eigenmatrix[variable_index]
            if not isinstance(vector, list) or not vector:
                continue
            bottleneck_scores.append((variable_name, abs(float(vector[0] or 0.0))))

        if bottleneck_scores:
            bottleneck_scores.sort(key=lambda item: item[1], reverse=True)
            pca_figure = go.Figure(
                data=[
                    go.Bar(
                        x=[name for name, _ in bottleneck_scores],
                        y=[score for _, score in bottleneck_scores],
                        name="|PC1 loading|",
                        marker_color=COLORS["primary"],
                    )
                ]
            )
            pca_figure.update_layout(**_transparent_layout("PCA Bottleneck Contribution (PC1)"))
            pca_payload = json.loads(pca_figure.to_json())

    # Payload structured by audience intent
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audience": {
            "executive": {"telemetry_combo": telemetry_payload},
            "engineering": {"pca_bottlenecks": pca_payload},
        },
    }


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    pytest_report = _load_json(PYTEST_TELEMETRY_PATH, default={})
    ledger = _normalize_ledger(_load_json(LEDGER_PATH, default={"meta": {}, "runs": []}))

    current_run = _build_run_record(pytest_report)
    previous_runs = [run for run in ledger.get("runs", []) if run.get("run_id") != current_run.get("run_id")]

    updated_ledger = _upsert_run(ledger, current_run)

    deltas = calculate_deltas(current_run, previous_runs)
    updated_ledger["meta"]["latest_deltas"] = deltas

    doe_matrix = generate_doe_matrix(updated_ledger.get("runs", []))
    doe_matrix["latest_deltas"] = deltas
    doe_matrix["current_run"] = current_run

    telemetry_matrix, variable_names = _build_telemetry_matrix(updated_ledger.get("runs", []))
    pca_proof = calculate_explicit_pca(telemetry_matrix)
    pca_proof["variable_names"] = variable_names
    doe_matrix["pca_variable_names"] = variable_names

    # ── Wave 15: Drift detection & regression analysis ───────────────────
    drift_result = detect_drift(current_run, updated_ledger)
    regression_result = analyze_matrix_regression(doe_matrix)
    drift_alerts_payload = build_drift_alerts_payload(drift_result, regression_result)
    updated_ledger["meta"]["drift_alerts"] = drift_alerts_payload

    LEDGER_PATH.write_text(json.dumps(updated_ledger, indent=2), encoding="utf-8")
    DOE_MATRIX_PATH.write_text(json.dumps(doe_matrix, indent=2), encoding="utf-8")

    kpi_dashboard = _load_json(KPI_DASHBOARD_PATH, default={})
    kpi_dashboard["pca_mathematical_proof"] = pca_proof
    KPI_DASHBOARD_PATH.write_text(json.dumps(kpi_dashboard, indent=2), encoding="utf-8")

    VISUALS_DIR.mkdir(parents=True, exist_ok=True)
    plotly_payloads = generate_plotly_json(updated_ledger, pca_proof)
    PLOTLY_PAYLOAD_PATH.write_text(json.dumps(plotly_payloads, indent=2), encoding="utf-8")

    # Write Jekyll-ingestible _data file for the drift alert banner.
    DRIFT_ALERTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRIFT_ALERTS_PATH.write_text(json.dumps(drift_alerts_payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
