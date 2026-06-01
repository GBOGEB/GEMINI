from src.parameters import load_config
from src.validators import run_sanity_checks

CONFIG_PATH = "config/blsn_config.yaml"


def test_load_config_has_required_limits() -> None:
    params = load_config(CONFIG_PATH)

    assert isinstance(params, dict)
    assert params["nominal_mass_flow_g_s"] is not None
    assert params["max_limit_g_s"] is not None
    assert params["min_limit_g_s"] is not None


def test_sanity_checks_execute_without_error() -> None:
    params = load_config(CONFIG_PATH)

    run_sanity_checks(params)
