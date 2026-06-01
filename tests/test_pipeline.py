from src.parameters import load_config
from src.validators import run_sanity_checks

CONFIG_PATH = "config/blsn_config.yaml"


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


def test_sanity_checks_execute_without_error() -> None:
    params = load_config(CONFIG_PATH)

    assert run_sanity_checks(params) is None
