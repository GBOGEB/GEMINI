"""DMAIC KPI parser for claimed-vs-actual telemetry verification."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PYTEST_TELEMETRY_PATH = DOCS_DIR / "pytest_telemetry.json"
KPI_DASHBOARD_PATH = DOCS_DIR / "kpi_dashboard.json"
MANIFEST_PATH = ROOT / "repo_manifest.yaml"
SSOT_PATH = ROOT / "config" / "blsn_config.yaml"
PIPELINE_RUNTIME_PATH = DOCS_DIR / "pipeline_runtime_seconds.txt"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}

    return content if isinstance(content, dict) else {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return content if isinstance(content, dict) else {}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_claimed_monitored_metrics_count(ssot: dict) -> int:
    telemetry = ssot.get("telemetry", {})
    if not isinstance(telemetry, dict):
        return 0

    monitored = telemetry.get("monitored_metrics")
    if isinstance(monitored, list):
        return len([item for item in monitored if isinstance(item, str)])

    tuple_targets = telemetry.get("tuple_execution_targets", {})
    if isinstance(tuple_targets, dict):
        return len([key for key in tuple_targets if isinstance(key, str)])

    return 0


def _count_validated_parameter_tests(pytest_report: dict) -> int:
    tests = pytest_report.get("tests", [])
    if not isinstance(tests, list):
        return 0

    keywords = ("parameter", "config", "limit", "telemetry", "ssot")
    matched = 0

    for test in tests:
        if not isinstance(test, dict):
            continue
        nodeid = str(test.get("nodeid", "")).lower()
        if any(keyword in nodeid for keyword in keywords):
            matched += 1

    return matched


def _load_pipeline_runtime_seconds() -> float:
    if not PIPELINE_RUNTIME_PATH.exists():
        return 0.0

    try:
        return _safe_float(PIPELINE_RUNTIME_PATH.read_text(encoding="utf-8").strip())
    except OSError:
        return 0.0


def _validation_strictness(summary: dict) -> dict:
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    skipped = int(summary.get("skipped", 0) or 0)
    total = int(summary.get("total", 0) or passed + failed + skipped)

    if total <= 0:
        ratios = {"pass_ratio": 0.0, "fail_ratio": 0.0, "skip_ratio": 0.0}
    else:
        ratios = {
            "pass_ratio": round(passed / total, 4),
            "fail_ratio": round(failed / total, 4),
            "skip_ratio": round(skipped / total, 4),
        }

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total": total,
        "ratios": ratios,
    }


def build_kpi_dashboard() -> dict:
    manifest = _load_yaml(MANIFEST_PATH)
    ssot = _load_yaml(SSOT_PATH)
    pytest_report = _load_json(PYTEST_TELEMETRY_PATH)

    summary = pytest_report.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}

    pytest_runtime_seconds = _safe_float(pytest_report.get("duration", summary.get("duration", 0.0)))
    python_engine_runtime_seconds = _load_pipeline_runtime_seconds()
    total_runtime_seconds = round(pytest_runtime_seconds + python_engine_runtime_seconds, 4)

    strictness = _validation_strictness(summary)

    claimed_monitored_metrics = _load_claimed_monitored_metrics_count(ssot)
    actual_validated_parameter_tests = _count_validated_parameter_tests(pytest_report)
    coverage_status = (
        "VERIFIED" if claimed_monitored_metrics == actual_validated_parameter_tests else "DRIFT"
    )

    version_control = manifest.get("version_control", {}) if isinstance(manifest, dict) else {}
    bios = manifest.get("bios", {}) if isinstance(manifest, dict) else {}

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "execution_velocity": {
            "pytest_runtime_seconds": round(pytest_runtime_seconds, 4),
            "python_engine_runtime_seconds": round(python_engine_runtime_seconds, 4),
            "total_runtime_seconds": total_runtime_seconds,
        },
        "validation_strictness": strictness,
        "coverage_gap": {
            "claimed_monitored_metrics": claimed_monitored_metrics,
            "actual_validated_parameter_tests": actual_validated_parameter_tests,
            "status": coverage_status,
        },
        "claimed_intent": {
            "manifest_version": str(version_control.get("manifest_version", "unknown")),
            "primary_function": str(bios.get("primary_function", "unknown")),
        },
    }


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        dashboard = build_kpi_dashboard()
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Telemetry parser fallback activated: {exc}", file=sys.stderr)
        dashboard = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution_velocity": {
                "pytest_runtime_seconds": 0.0,
                "python_engine_runtime_seconds": 0.0,
                "total_runtime_seconds": 0.0,
            },
            "validation_strictness": {
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "total": 0,
                "ratios": {"pass_ratio": 0.0, "fail_ratio": 0.0, "skip_ratio": 0.0},
            },
            "coverage_gap": {
                "claimed_monitored_metrics": 0,
                "actual_validated_parameter_tests": 0,
                "status": "UNKNOWN",
            },
            "claimed_intent": {
                "manifest_version": "unknown",
                "primary_function": "unknown",
            },
        }

    KPI_DASHBOARD_PATH.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
