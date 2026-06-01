"""Wave 12 statistical process control and DoE foundation engine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PYTEST_TELEMETRY_PATH = DOCS_DIR / "pytest_telemetry.json"
LEDGER_PATH = DOCS_DIR / "historical_telemetry_ledger.json"
DOE_MATRIX_PATH = DOCS_DIR / "experimental_design_matrix.json"
KPI_DASHBOARD_PATH = DOCS_DIR / "kpi_dashboard.json"


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

    LEDGER_PATH.write_text(json.dumps(updated_ledger, indent=2), encoding="utf-8")
    DOE_MATRIX_PATH.write_text(json.dumps(doe_matrix, indent=2), encoding="utf-8")

    kpi_dashboard = _load_json(KPI_DASHBOARD_PATH, default={})
    kpi_dashboard["pca_mathematical_proof"] = pca_proof
    KPI_DASHBOARD_PATH.write_text(json.dumps(kpi_dashboard, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
