from pathlib import Path

import yaml

from src.parameters import load_config
from src.pipeline import _extract_tuple_telemetry, collect_sanity_results, generate_html_report
from src.validators import run_sanity_checks

CONFIG_PATH = "config/blsn_config.yaml"


def _load_full_config() -> dict:
    return yaml.safe_load(Path(CONFIG_PATH).read_text(encoding="utf-8"))


def test_load_config_has_required_limits() -> None:
    params = load_config(CONFIG_PATH)

    assert isinstance(params, dict)
    nominal = params["nominal_mass_flow_g_s"]
    maximum = params["max_limit_g_s"]
    minimum = params["min_limit_g_s"]

    assert isinstance(nominal, (int, float))
    assert isinstance(maximum, (int, float))
    assert isinstance(minimum, (int, float))
    assert minimum < nominal < maximum


def test_ssot_contains_system_parameter_boundaries() -> None:
    config_data = _load_full_config()
    system = config_data["system_parameters"]

    assert "nitrogen_precooling" in system
    assert "turbine_stage_1" in system
    assert "turbine_stage_2" in system
    assert "helium_loop" in system
    assert "cold_box" in system


def test_ssot_contains_tuple_telemetry_targets() -> None:
    config_data = _load_full_config()
    telemetry = config_data["telemetry"]["tuple_execution_targets"]

    assert "ci_total_runtime_s" in telemetry
    assert "pytest_runtime_s" in telemetry
    assert all(isinstance(value, list) and len(value) == 3 for value in telemetry.values())


def test_sanity_checks_execute_without_error() -> None:
    params = load_config(CONFIG_PATH)

    assert run_sanity_checks(params) is None


def test_generate_html_report_renders_visuals_and_tuple_telemetry() -> None:
    config_data = _load_full_config()
    params = load_config(CONFIG_PATH)
    sanity_results = collect_sanity_results(params)
    telemetry_tuples = _extract_tuple_telemetry(config_data)
    html = generate_html_report(params, sanity_results, telemetry_tuples)

    assert "Sanity Check Telemetry" in html
    assert "Tuple Execution Telemetry Targets" in html
    assert "<table>" in html
    assert any(token in html for token in ["PASS", "WARN", "FAIL"])
    assert "tr.pass" in html
    assert "ci_total_runtime_s" in html
