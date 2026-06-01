"""Main engine orchestration for generating BLSN synthetic reports from SSOT config."""

from __future__ import annotations

import json
import re
import textwrap
from contextlib import redirect_stdout
from html import escape
from io import StringIO
from pathlib import Path

import yaml

try:
    from src.reporter import export_outputs as _export_outputs  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    _export_outputs = None

try:
    from src.validators import run_sanity_checks as _run_sanity_checks  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    _run_sanity_checks = None


CONFIG_PATH = "config/blsn_config.yaml"
OUTPUT_DIR = Path("docs")


def _format_sanity_results(raw_output: str, failure_message: str | None = None) -> list[str]:
    results: list[str] = []

    for line in raw_output.splitlines():
        message = line.strip()
        if not message:
            continue

        if "PASS" in message:
            results.append(f"[PASS] {message}")
        elif "WARN" in message:
            results.append(f"[WARN] {message}")
        elif "FAIL" in message:
            results.append(f"[FAIL] {message}")

    if failure_message:
        results.append(f"[FAIL] {failure_message}")

    return results or ["[PASS] Sanity checks completed without alerts."]


def _load_ssot(path: str = CONFIG_PATH) -> dict:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = "SSOT config root must be a mapping"
        raise ValueError(msg)
    return data


def _fallback_sanity_checks(params: dict) -> None:
    nominal = float(params.get("nominal_mass_flow_g_s", 0))
    minimum = float(params.get("min_limit_g_s", 0))
    maximum = float(params.get("max_limit_g_s", 0))

    if not minimum < nominal < maximum:
        raise RuntimeError("Nominal mass flow must be between min and max limits.")

    print("PASS | Nominal mass flow is bounded by configured limits")


def _run_checks(params: dict) -> None:
    if _run_sanity_checks is not None:
        _run_sanity_checks(params)
        return
    _fallback_sanity_checks(params)


def _export(params: dict) -> None:
    if _export_outputs is not None:
        _export_outputs(params)


def collect_sanity_results(params: dict) -> list[str]:
    output = StringIO()
    failure: str | None = None

    try:
        with redirect_stdout(output):
            _run_checks(params)
    except RuntimeError as exc:
        failure = str(exc)

    return _format_sanity_results(output.getvalue(), failure)


def _status_from_alert(alert: str) -> str:
    if "[FAIL]" in alert:
        return "fail"
    if "[WARN]" in alert:
        return "warn"
    return "pass"


def _extract_tuple_telemetry(ssot: dict) -> list[tuple[str, tuple[float, float, float]]]:
    telemetry = ssot.get("telemetry", {})
    metrics = telemetry.get("tuple_execution_targets", {}) if isinstance(telemetry, dict) else {}
    tuples: list[tuple[str, tuple[float, float, float]]] = []

    if not isinstance(metrics, dict):
        return tuples

    for metric_name, values in metrics.items():
        if not isinstance(metric_name, str):
            continue
        if not isinstance(values, list) or len(values) != 3:
            continue
        if not all(isinstance(value, int | float) for value in values):
            continue
        target, warn, fail = (float(values[0]), float(values[1]), float(values[2]))
        tuples.append((metric_name, (target, warn, fail)))

    return tuples


def _extract_presentation_layer(ssot: dict) -> dict[str, str | bool]:
    """Extract all presentation-layer knobs from the SSOT config.

    Returned keys:
      enable_lipstick  – whether to inject the optional CSS CDN block
      css_framework_cdn – CDN URL for the optional CSS framework (e.g. Tailwind)
      theme            – "light" | "dark" | "auto"  (auto → follows OS preference)
      density          – "compact" | "comfortable" | "spacious"
      audience         – "executive" | "manager" | "engineer"
    """
    _defaults: dict[str, str | bool] = {
        "enable_lipstick": False,
        "css_framework_cdn": "",
        "theme": "light",
        "density": "comfortable",
        "audience": "engineer",
    }

    system_meta = ssot.get("system_meta", {})
    if not isinstance(system_meta, dict):
        return _defaults

    presentation_layer = system_meta.get("presentation_layer", {})
    if not isinstance(presentation_layer, dict):
        return _defaults

    def _validated(key: str, allowed: set[str], default: str) -> str:
        """Return the config value if it is in *allowed*, otherwise *default*."""
        raw = str(presentation_layer.get(key, default)).strip().lower()
        return raw if raw in allowed else default

    theme   = _validated("theme",   {"light", "dark", "auto"},              "light")
    density = _validated("density", {"compact", "comfortable", "spacious"}, "comfortable")
    audience = _validated("audience", {"executive", "manager", "engineer"}, "engineer")

    return {
        "enable_lipstick": bool(presentation_layer.get("enable_lipstick", False)),
        "css_framework_cdn": str(presentation_layer.get("css_framework_cdn", "")).strip(),
        "theme": theme,
        "density": density,
        "audience": audience,
    }


def _extract_publishing(ssot: dict) -> dict[str, str | bool]:
    publishing = ssot.get("publishing", {})
    if not isinstance(publishing, dict):
        return {
            "generate_pdf": False,
            "generate_slides": False,
            "base_url": "",
        }

    return {
        "generate_pdf": bool(publishing.get("generate_pdf", False)),
        "generate_slides": bool(publishing.get("generate_slides", False)),
        "base_url": str(publishing.get("base_url", "")).strip(),
    }


def _load_kpi_dashboard(path: Path | None = None) -> dict:
    dashboard_path = path or (OUTPUT_DIR / "kpi_dashboard.json")
    if not dashboard_path.exists():
        return {}

    try:
        data = json.loads(dashboard_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _load_json_data(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "item"


def _metric_title(metric_name: str) -> str:
    return metric_name.replace("_", " ").strip().title()


def _join_base(base_url: str, path: str) -> str:
    if not base_url:
        return path
    return f"{base_url.rstrip('/')}/{path}"


def _render_metric_markdown(metric: str, thresholds: tuple[float, float, float]) -> str:
    target, warn, fail = thresholds
    title = _metric_title(metric)
    return (
        f"# {title}\n\n"
        f"- Metric ID: `{metric}`\n"
        f"- Target Threshold: **{target:.1f}s**\n"
        f"- Warn Threshold: **{warn:.1f}s**\n"
        f"- Fail Threshold: **{fail:.1f}s**\n"
    )


def _render_markdown_preview(markdown: str) -> str:
    """Convert a minimal metric markdown snippet into a theme-aware HTML card.

    Parses the first ``# Heading`` and ``- bullet`` lines, then wraps them in
    a card that inherits the report's CSS custom-property colour tokens so it
    adapts correctly to both light and dark modes.
    """
    lines = [line for line in markdown.splitlines() if line.strip()]
    if not lines:
        return ""

    title = ""
    bullets: list[str] = []
    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:]
        elif line.startswith("- "):
            bullets.append(line[2:])

    bullet_html = "".join(f"<li>{escape(item)}</li>" for item in bullets)
    title_html = escape(title) if title else "Metric"
    return (
        '<article style="border-radius:0.75rem;border:1px solid var(--border);'
        'background:var(--bg-card);padding:1rem;">'
        f'<h3 style="margin:0 0 0.5rem;font-size:0.95rem;font-weight:600;color:var(--text-1)">{title_html}</h3>'
        f'<ul style="margin:0;padding-left:1.25rem;font-size:0.875rem;color:var(--text-2);line-height:1.7">{bullet_html}</ul>'
        "</article>"
    )


def generate_html_report(
    params: dict,
    sanity_results: list[str],
    telemetry_tuples: list[tuple[str, tuple[float, float, float]]],
    presentation_layer: dict[str, str | bool] | None = None,
    publishing: dict[str, str | bool] | None = None,
    metric_pages: list[tuple[str, str, str]] | None = None,
    kpi_dashboard: dict | None = None,
    historical_ledger: dict | None = None,
    doe_matrix: dict | None = None,
    bt_ranking: dict | None = None,
) -> str:
    presentation = presentation_layer or {
        "enable_lipstick": False,
        "css_framework_cdn": "",
        "theme": "light",
        "density": "comfortable",
        "audience": "engineer",
    }
    publishing_cfg = publishing or {"base_url": "", "generate_pdf": False, "generate_slides": False}

    lipstick_enabled = bool(presentation.get("enable_lipstick", False))
    css_cdn = escape(str(presentation.get("css_framework_cdn", "")))
    # theme / density / audience are written into HTML data-attributes and used
    # by both the CSS token system and the JS controls bar.
    theme = escape(str(presentation.get("theme", "light")))
    density = escape(str(presentation.get("density", "comfortable")))
    audience = escape(str(presentation.get("audience", "engineer")))
    base_url = str(publishing_cfg.get("base_url", ""))

    # Optional extra CSS framework CDN (e.g. Tailwind) injected when lipstick is on.
    cdn_block = f'<script src="{css_cdn}"></script>' if lipstick_enabled and css_cdn else ""

    # ── Sanity-check table rows ──────────────────────────────────────────────
    # Each row gets a status class ("pass" / "warn" / "fail") for CSS tinting.
    sanity_rows = "\n".join(
        (
            f'<tr class="{_status_from_alert(alert)}">'
            f'<td><span class="status-{_status_from_alert(alert)}">'
            f"{_status_from_alert(alert).upper()}</span></td>"
            f"<td>{escape(alert)}</td>"
            "</tr>"
        )
        for alert in sanity_results
    )

    # ── Telemetry-target table rows ──────────────────────────────────────────
    # Target / Warn / Fail columns use colour tokens so they adapt to dark mode.
    telemetry_rows = "\n".join(
        (
            "<tr>"
            f'<td style="font-weight:500;color:var(--text-1)">{escape(metric)}</td>'
            f'<td style="color:var(--pass-text)">{target:.1f}</td>'
            f'<td style="color:var(--warn-text)">{warn:.1f}</td>'
            f'<td style="color:var(--fail-text)">{fail:.1f}</td>'
            "</tr>"
        )
        for metric, (target, warn, fail) in telemetry_tuples
    )
    telemetry_rows = (
        telemetry_rows
        or '<tr><td colspan="4" style="color:var(--text-3)">No tuple telemetry configured.</td></tr>'
    )

    # ── Metric slug links and inline previews ────────────────────────────────
    metric_links = "\n".join(
        f'<li><a style="color:var(--accent)" href="{escape(_join_base(base_url, f"{slug}.md"))}">'
        f"{escape(title)}</a></li>"
        for slug, title, _ in metric_pages or []
    ) or '<li style="color:var(--text-3)">No metric pages generated.</li>'

    previews = "\n".join(_render_markdown_preview(markdown) for _, _, markdown in metric_pages or [])

    # ── KPI Dashboard values ─────────────────────────────────────────────────
    kpi = kpi_dashboard if isinstance(kpi_dashboard, dict) else {}
    coverage_gap = kpi.get("coverage_gap", {})
    coverage_gap = coverage_gap if isinstance(coverage_gap, dict) else {}
    execution_velocity = kpi.get("execution_velocity", {})
    execution_velocity = execution_velocity if isinstance(execution_velocity, dict) else {}
    strictness = kpi.get("validation_strictness", {})
    strictness = strictness if isinstance(strictness, dict) else {}
    ratios = strictness.get("ratios", {})
    ratios = ratios if isinstance(ratios, dict) else {}

    claimed_limits = int(coverage_gap.get("claimed_monitored_metrics", 0) or 0)
    tested_limits = int(coverage_gap.get("actual_validated_parameter_tests", 0) or 0)
    verification_status = escape(str(coverage_gap.get("status", "UNKNOWN")))
    total_runtime = float(execution_velocity.get("total_runtime_seconds", 0.0) or 0.0)
    pass_ratio = float(ratios.get("pass_ratio", 0.0) or 0.0)
    fail_ratio = float(ratios.get("fail_ratio", 0.0) or 0.0)
    skip_ratio = float(ratios.get("skip_ratio", 0.0) or 0.0)

    # ── Historical ledger ────────────────────────────────────────────────────
    ledger = historical_ledger if isinstance(historical_ledger, dict) else {}
    ledger_meta = ledger.get("meta", {})
    ledger_meta = ledger_meta if isinstance(ledger_meta, dict) else {}
    total_runs = int(ledger_meta.get("total_attempts", 0) or 0)
    success_rate = float(ledger_meta.get("success_rate", 0.0) or 0.0)
    latest_deltas = ledger_meta.get("latest_deltas", {})
    latest_deltas = latest_deltas if isinstance(latest_deltas, dict) else {}
    previous_runtime = float(latest_deltas.get("previous_runtime_moving_avg", 0.0) or 0.0)

    # ── DoE factor map ───────────────────────────────────────────────────────
    doe = doe_matrix if isinstance(doe_matrix, dict) else {}
    factor_map = doe.get("factor_map", {})
    factor_map = factor_map if isinstance(factor_map, dict) else {}
    factor_a = escape(str(factor_map.get("A", "python_version")))
    factor_b = escape(str(factor_map.get("B", "os_type")))
    factor_c = escape(str(factor_map.get("C", "load_parameter")))

    # ── PCA proof table rows ─────────────────────────────────────────────────
    pca_proof = kpi.get("pca_mathematical_proof", {})
    pca_proof = pca_proof if isinstance(pca_proof, dict) else {}
    pca_eigenvalues = pca_proof.get("eigenvalues", [])
    pca_eigenvalues = pca_eigenvalues if isinstance(pca_eigenvalues, list) else []
    pca_eigenmatrix = pca_proof.get("eigenmatrix", [])
    pca_eigenmatrix = pca_eigenmatrix if isinstance(pca_eigenmatrix, list) else []
    pca_variance = pca_proof.get("explained_variance_ratio", [])
    pca_variance = pca_variance if isinstance(pca_variance, list) else []
    pca_variables = pca_proof.get("variable_names", [])
    pca_variables = (
        [str(variable) for variable in pca_variables]
        if isinstance(pca_variables, list) and pca_variables
        else ["runtime_seconds", "pass_rate", "fail_rate", "skip_rate", "total_tests"]
    )

    pca_rows: list[str] = []
    top_components = min(2, len(pca_eigenvalues))
    for component_index in range(top_components):
        eigenvalue = float(pca_eigenvalues[component_index] or 0.0)
        variance_ratio = (
            float(pca_variance[component_index] or 0.0) if component_index < len(pca_variance) else 0.0
        )
        weights = []
        for variable_index, variable_name in enumerate(pca_variables):
            if variable_index < len(pca_eigenmatrix):
                row_values = pca_eigenmatrix[variable_index]
                if isinstance(row_values, list) and component_index < len(row_values):
                    weights.append((variable_name, abs(float(row_values[component_index] or 0.0))))
        strongest_variable = max(weights, key=lambda item: item[1])[0] if weights else "N/A"
        pca_rows.append(
            "<tr>"
            f"<td>PC{component_index + 1}</td>"
            f"<td>{eigenvalue:.6f}</td>"
            f"<td>{variance_ratio:.2%}</td>"
            f"<td>{escape(str(strongest_variable))}</td>"
            "</tr>"
        )
    pca_rows_html = (
        "\n".join(pca_rows)
        if pca_rows
        else '<tr><td colspan="4" style="color:var(--text-3)">No PCA proof data available.</td></tr>'
    )

    # ── Bradley-Terry ranking table rows ────────────────────────────────────
    bt = bt_ranking if isinstance(bt_ranking, dict) else {}
    global_bt = bt.get("global_repo_ranking", [])
    global_bt = global_bt if isinstance(global_bt, list) else []
    inter_bt = bt.get("inter_category_ranking", [])
    inter_bt = inter_bt if isinstance(inter_bt, list) else []
    requirement_block = bt.get("qplant_requirements_ranking", {})
    requirement_block = requirement_block if isinstance(requirement_block, dict) else {}
    requirement_global = requirement_block.get("global", [])
    requirement_global = requirement_global if isinstance(requirement_global, list) else []

    global_bt_rows = "\n".join(
        (
            "<tr>"
            f"<td>{int(item.get('rank', 0) or 0)}</td>"
            f"<td>{escape(str(item.get('name', 'N/A')))}</td>"
            f"<td>{float(item.get('strength', 0.0) or 0.0):.6f}</td>"
            f"<td>{float(item.get('win_probability_vs_top', 0.0) or 0.0):.2f}%</td>"
            "</tr>"
        )
        for item in global_bt[:10]
        if isinstance(item, dict)
    )
    if not global_bt_rows:
        global_bt_rows = (
            '<tr><td colspan="4" style="color:var(--text-3)">No global BT ranking data.</td></tr>'
        )

    inter_bt_rows = "\n".join(
        (
            "<tr>"
            f"<td>{int(item.get('rank', 0) or 0)}</td>"
            f"<td>{escape(str(item.get('name', 'N/A')))}</td>"
            f"<td>{float(item.get('win_probability_vs_top', 0.0) or 0.0):.2f}%</td>"
            "</tr>"
        )
        for item in inter_bt
        if isinstance(item, dict)
    )
    if not inter_bt_rows:
        inter_bt_rows = (
            '<tr><td colspan="3" style="color:var(--text-3)">No inter-category BT ranking data.</td></tr>'
        )

    requirement_rows = "\n".join(
        (
            "<tr>"
            f"<td>{int(item.get('rank', 0) or 0)}</td>"
            f"<td>{escape(str(item.get('name', 'N/A')))}</td>"
            f"<td>{float(item.get('win_probability_vs_top', 0.0) or 0.0):.2f}%</td>"
            "</tr>"
        )
        for item in requirement_global[:10]
        if isinstance(item, dict)
    )
    if not requirement_rows:
        requirement_rows = (
            '<tr><td colspan="3" style="color:var(--text-3)">No QPLANT requirement ranking data.</td></tr>'
        )

    # ── Assemble and return the full HTML report ─────────────────────────────
    # The report uses CSS custom-property (token) colour system so every
    # element adapts to light / dark themes without JavaScript rewrites.
    # Data attributes on <html> drive CSS selectors for theme, density and
    # audience gating; the JS controls bar synchronises them at runtime and
    # persists choices to localStorage.
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="{theme}" data-density="{density}" data-audience="{audience}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BLSN Report — {escape(str(params.get('vehicle_name', 'N/A')))}</title>
  {cdn_block}
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    /* ── Design Tokens: Light (default) ────────────────────────────────── */
    :root, [data-theme="light"] {{
      --bg-page:    #f8fafc;
      --bg-card:    #ffffff;
      --bg-muted:   #f1f5f9;
      --bg-header:  #f8fafc;
      --border:     #e2e8f0;
      --text-1:     #0f172a;
      --text-2:     #475569;
      --text-3:     #94a3b8;
      --accent:     #6366f1;
      --accent-bg:  #eef2ff;
      --pass-text:  #15803d;
      --pass-bg:    #f0fdf4;
      --warn-text:  #b45309;
      --warn-bg:    #fffbeb;
      --fail-text:  #b91c1c;
      --fail-bg:    #fef2f2;
      --shadow:     0 1px 3px 0 rgb(0 0 0 / 0.07);
    }}
    /* ── Design Tokens: Dark ────────────────────────────────────────────── */
    [data-theme="dark"] {{
      --bg-page:    #0f172a;
      --bg-card:    #1e293b;
      --bg-muted:   #1e293b;
      --bg-header:  #1e293b;
      --border:     #334155;
      --text-1:     #f1f5f9;
      --text-2:     #94a3b8;
      --text-3:     #64748b;
      --accent:     #818cf8;
      --accent-bg:  #1e1b4b;
      --pass-text:  #4ade80;
      --pass-bg:    #052e16;
      --warn-text:  #fbbf24;
      --warn-bg:    #1c1400;
      --fail-text:  #f87171;
      --fail-bg:    #1c0505;
      --shadow:     0 1px 3px 0 rgb(0 0 0 / 0.3);
    }}
    /* ── Density Scale ──────────────────────────────────────────────────── */
    /* Default (comfortable) spacing: these vars are overridden per density. */
    :root {{
      --d-py:   0.75rem;   /* table cell vertical padding  */
      --d-px:   1rem;      /* table cell horizontal padding */
      --d-gap:  1rem;      /* grid/flex gap                 */
      --d-card: 1.5rem;    /* card padding                  */
    }}
    [data-density="compact"]  {{ --d-py: 0.35rem;  --d-px: 0.625rem; --d-gap: 0.5rem;  --d-card: 1rem;  font-size: 0.875rem; }}
    [data-density="spacious"] {{ --d-py: 1.125rem; --d-px: 1.375rem; --d-gap: 1.5rem;  --d-card: 2rem; }}
    /* ── Audience Gating ────────────────────────────────────────────────── */
    /* Sections marked .aud-manager are hidden for the executive audience.
       Sections marked .aud-engineer are hidden for executive and manager.   */
    [data-audience="executive"] .aud-manager,
    [data-audience="executive"] .aud-engineer {{ display: none; }}
    [data-audience="manager"]   .aud-engineer {{ display: none; }}
    /* ── Base Styles ────────────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      background: var(--bg-page);
      color: var(--text-1);
      font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;
      margin: 0; padding: 0;
      transition: background 0.2s ease, color 0.2s ease;
    }}
    main {{ max-width: 64rem; margin: 0 auto; padding: 2.5rem 1.5rem; }}
    /* ── Controls Bar ───────────────────────────────────────────────────── */
    .ctrl-bar {{
      position: sticky; top: 0; z-index: 20;
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      padding: 0.5rem 1.5rem;
      display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
      box-shadow: var(--shadow);
    }}
    .ctrl-brand {{ font-size: 0.7rem; font-weight: 700; letter-spacing: 0.15em; color: var(--accent); margin-right: auto; text-transform: uppercase; }}
    .ctrl-group {{ display: flex; align-items: center; gap: 0.35rem; }}
    .ctrl-label {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); }}
    .ctrl-select, .ctrl-btn {{
      font-size: 0.78rem; padding: 0.2rem 0.5rem;
      border: 1px solid var(--border); border-radius: 0.375rem;
      background: var(--bg-muted); color: var(--text-1); cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }}
    .ctrl-select:hover, .ctrl-btn:hover {{ background: var(--accent-bg); border-color: var(--accent); color: var(--accent); }}
    /* ── Cards ──────────────────────────────────────────────────────────── */
    .card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: var(--d-card);
      margin-bottom: 2rem;
      box-shadow: var(--shadow);
    }}
    .card-title {{ font-size: 1.125rem; font-weight: 600; color: var(--text-1); margin: 0 0 1rem; }}
    .card-subtitle {{ font-size: 0.95rem; font-weight: 600; color: var(--text-1); margin: 1.25rem 0 0.625rem; }}
    /* ── KPI Grid ───────────────────────────────────────────────────────── */
    .kpi-grid {{ display: grid; gap: var(--d-gap); grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr)); margin-top: 1.25rem; }}
    .kpi-cell {{ background: var(--bg-muted); border-radius: 0.75rem; padding: var(--d-py) var(--d-px); }}
    .kpi-label {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin: 0; }}
    .kpi-value {{ font-size: 1.1rem; font-weight: 600; color: var(--text-1); margin: 0.2rem 0 0; }}
    /* ── Tables ─────────────────────────────────────────────────────────── */
    .tbl-wrap {{ border-radius: 0.75rem; overflow: hidden; border: 1px solid var(--border); margin-top: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--bg-card); }}
    thead tr {{ background: var(--bg-header); }}
    thead th {{
      padding: var(--d-py) var(--d-px);
      text-align: left; font-size: 0.7rem; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-2);
    }}
    tbody td {{ padding: var(--d-py) var(--d-px); color: var(--text-2); border-top: 1px solid var(--border); font-size: 0.875rem; }}
    /* Row-level status tints driven by tr.pass / tr.warn / tr.fail classes.
       These interact with the CSS token system so they invert correctly
       in dark mode without any extra JavaScript. */
    tbody tr.pass td {{ background: var(--pass-bg); color: var(--pass-text); }}
    tbody tr.warn td {{ background: var(--warn-bg); color: var(--warn-text); }}
    tbody tr.fail td {{ background: var(--fail-bg); color: var(--fail-text); }}
    /* ── Status Labels ──────────────────────────────────────────────────── */
    .status-pass {{ color: var(--pass-text); font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .status-warn {{ color: var(--warn-text); font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    .status-fail {{ color: var(--fail-text); font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; }}
    /* ── Badge ──────────────────────────────────────────────────────────── */
    .badge {{ display: inline-block; border-radius: 999px; padding: 0.15rem 0.625rem; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.06em; }}
    .badge-accent {{ background: var(--accent-bg); color: var(--accent); }}
    /* ── Inline code ─────────────────────────────────────────────────────── */
    code {{ background: var(--bg-muted); border-radius: 0.25rem; padding: 0.1em 0.35em; font-size: 0.85em; color: var(--accent); }}
  </style>
</head>
<body>

  <!-- ── Controls Bar: Theme / Density / Audience toggles ─────────────────
       Preferences are persisted to localStorage under the "blsn_" namespace
       so they survive page reloads. Selecting "auto" theme follows the OS
       light/dark preference via the prefers-color-scheme media query.       -->
  <nav class="ctrl-bar" role="toolbar" aria-label="Display controls">
    <span class="ctrl-brand">BLSN</span>

    <div class="ctrl-group">
      <span class="ctrl-label" id="lbl-theme">Theme</span>
      <select id="ctrl-theme" class="ctrl-select" onchange="setTheme(this.value)" aria-labelledby="lbl-theme">
        <option value="light">☀ Light</option>
        <option value="dark">🌙 Dark</option>
        <option value="auto">⚙ Auto</option>
      </select>
    </div>

    <div class="ctrl-group">
      <span class="ctrl-label" id="lbl-density">Density</span>
      <select id="ctrl-density" class="ctrl-select" onchange="setDensity(this.value)" aria-labelledby="lbl-density">
        <option value="compact">Compact</option>
        <option value="comfortable">Comfortable</option>
        <option value="spacious">Spacious</option>
      </select>
    </div>

    <div class="ctrl-group">
      <span class="ctrl-label" id="lbl-audience">Audience</span>
      <select id="ctrl-audience" class="ctrl-select" onchange="setAudience(this.value)" aria-labelledby="lbl-audience">
        <option value="executive">Executive</option>
        <option value="manager">Manager</option>
        <option value="engineer">Engineer</option>
      </select>
    </div>
  </nav>

  <main>

    <!-- ── Header / Overview  (visible to ALL audiences) ──────────────── -->
    <header class="card">
      <p style="font-size:0.68rem;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:var(--text-3);margin:0">BLSN</p>
      <h1 style="margin:0.4rem 0 0;font-size:1.875rem;font-weight:700;letter-spacing:-0.02em;color:var(--text-1)">Synthetic Validation Report</h1>
      <p style="margin:0.4rem 0 0;font-size:0.8rem;color:var(--text-3)">
        Theme&nbsp;<strong style="color:var(--text-2)">{theme}</strong>
        &nbsp;·&nbsp;Density&nbsp;<strong style="color:var(--text-2)">{density}</strong>
        &nbsp;·&nbsp;Audience&nbsp;<strong style="color:var(--text-2)">{audience}</strong>
      </p>
      <div class="kpi-grid">
        <div class="kpi-cell"><p class="kpi-label">Vehicle</p><p class="kpi-value">{escape(str(params.get('vehicle_name', 'N/A')))}</p></div>
        <div class="kpi-cell"><p class="kpi-label">Cooling Mode</p><p class="kpi-value">{escape(str(params.get('cooling_mode', 'N/A')))}</p></div>
        <div class="kpi-cell"><p class="kpi-label">Nominal Flow</p><p class="kpi-value">{escape(str(params.get('nominal_mass_flow_g_s', 'N/A')))} g/s</p></div>
        <div class="kpi-cell"><p class="kpi-label">Limits</p><p class="kpi-value">{escape(str(params.get('min_limit_g_s', 'N/A')))}–{escape(str(params.get('max_limit_g_s', 'N/A')))} g/s</p></div>
      </div>
    </header>

    <!-- ── Sanity Check Telemetry  (visible to ALL audiences) ─────────── -->
    <section class="card">
      <h2 class="card-title">Sanity Check Telemetry</h2>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Status</th><th>Message</th></tr></thead>
          <tbody>{sanity_rows}</tbody>
        </table>
      </div>
    </section>

    <!-- ── System Verification KPI  (visible to ALL audiences) ──────────
         Executive audience sees the high-level pass/fail verdict; manager
         and engineer audiences see the full ratio breakdown too.            -->
    <section class="card">
      <h2 class="card-title">System Verification: Claimed vs. Actual</h2>
      <p style="margin:0 0 1rem;padding:0.75rem 1rem;background:var(--pass-bg);border-radius:0.5rem;font-size:0.875rem;color:var(--pass-text)">
        Claimed Limits: <strong>{claimed_limits}</strong>
        &nbsp;|&nbsp; Actually Tested: <strong>{tested_limits}</strong>
        &nbsp;→ STATUS: <strong>{verification_status}</strong>
      </p>
      <div class="kpi-grid">
        <div class="kpi-cell"><p class="kpi-label">Total Runtime</p><p class="kpi-value">{total_runtime:.2f}s</p></div>
        <div class="kpi-cell"><p class="kpi-label">Pass Ratio</p><p class="kpi-value" style="color:var(--pass-text)">{pass_ratio:.1%}</p></div>
        <div class="kpi-cell"><p class="kpi-label">Fail Ratio</p><p class="kpi-value" style="color:var(--fail-text)">{fail_ratio:.1%}</p></div>
        <div class="kpi-cell"><p class="kpi-label">Skip Ratio</p><p class="kpi-value" style="color:var(--warn-text)">{skip_ratio:.1%}</p></div>
      </div>
    </section>

    <!-- ── Tuple Execution Telemetry Targets  (manager + engineer) ──────
         Executive summary omits detailed threshold tables; managers and
         engineers see the full target / warn / fail breakdown.              -->
    <section class="card aud-manager">
      <h2 class="card-title">Tuple Execution Telemetry Targets (seconds)</h2>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Metric</th><th>Target</th><th>Warn</th><th>Fail</th></tr></thead>
          <tbody>{telemetry_rows}</tbody>
        </table>
      </div>
    </section>

    <!-- ── Interactive Plotly Visualizations  (manager + engineer) ──────
         Charts are rendered with a theme-aware Plotly template; re-rendered
         automatically when the theme toggle changes via Plotly.react().     -->
    <section class="card aud-manager">
      <h2 class="card-title">Interactive Visualizations</h2>
      <p style="font-size:0.8rem;color:var(--text-3);margin:0 0 1rem">Telemetry trend and PCA bottleneck analysis — theme-aware rendering.</p>
      <div id="plotly-telemetry-chart" style="width:100%;min-height:400px;border-radius:0.5rem;overflow:hidden;"></div>
      <div id="plotly-pca-chart" style="width:100%;min-height:400px;border-radius:0.5rem;overflow:hidden;margin-top:1.5rem;"></div>
    </section>

    <!-- ── Bradley-Terry Ranking  (manager + engineer) ──────────────────
         Pairwise comparison ranking for global repo, inter-category,
         and QPLANT requirements.                                            -->
    <section class="card aud-manager">
      <h2 class="card-title">System Priority &amp; Bottleneck Ranking (Bradley-Terry)</h2>
      <p style="font-size:0.85rem;color:var(--text-2);margin:0 0 0.75rem">Pairwise probability model: <code>P(i &gt; j) = p_i / (p_i + p_j)</code></p>
      <h3 class="card-subtitle">Global Repo Ranking</h3>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Rank</th><th>Artifact</th><th>BT Strength</th><th>Win Prob vs Top</th></tr></thead>
          <tbody>{global_bt_rows}</tbody>
        </table>
      </div>
      <h3 class="card-subtitle">Inter-Category Ranking</h3>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Rank</th><th>Category</th><th>Win Prob vs Top</th></tr></thead>
          <tbody>{inter_bt_rows}</tbody>
        </table>
      </div>
      <h3 class="card-subtitle">QPLANT Requirements Ranking Bridge</h3>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Rank</th><th>Requirement</th><th>Win Prob vs Top</th></tr></thead>
          <tbody>{requirement_rows}</tbody>
        </table>
      </div>
    </section>

    <!-- ── SPC, DoE & PCA Proof  (engineer only) ────────────────────────
         Full statistical detail: runtime drift, historical success rate,
         DoE factor map and principal-component analysis eigenvalues.        -->
    <section class="card aud-engineer">
      <h2 class="card-title">Wave 12: SPC &amp; Telemetry Stats</h2>
      <div class="kpi-grid">
        <div class="kpi-cell"><p class="kpi-label">Runtime Drift</p><p class="kpi-value">{total_runtime:.4f}s</p></div>
        <div class="kpi-cell"><p class="kpi-label">Prev Moving Avg</p><p class="kpi-value">{previous_runtime:.4f}s</p></div>
        <div class="kpi-cell"><p class="kpi-label">Total Runs</p><p class="kpi-value">{total_runs}</p></div>
        <div class="kpi-cell"><p class="kpi-label">Success Rate</p><p class="kpi-value" style="color:var(--pass-text)">{success_rate:.1%}</p></div>
      </div>
      <p style="font-size:0.875rem;color:var(--text-2);margin-top:1rem">
        DoE Factors — A: <strong>{factor_a}</strong> · B: <strong>{factor_b}</strong> · C: <strong>{factor_c}</strong>
      </p>
      <h3 class="card-subtitle">Principal Component Analysis (PCA Proof)</h3>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>Principal Component</th><th>Eigenvalue</th><th>Explained Variance</th><th>Highest Weight Variable</th></tr></thead>
          <tbody>{pca_rows_html}</tbody>
        </table>
      </div>
    </section>

    <!-- ── Metric Markdown Slugs  (engineer only) ───────────────────────
         Quick-links to generated per-metric markdown pages plus inline
         previews of the threshold bullet points.                            -->
    <section class="card aud-engineer">
      <h2 class="card-title">Metric Markdown Slugs</h2>
      <ul style="margin:0 0 1rem;padding-left:1.25rem;font-size:0.875rem;line-height:2">{metric_links}</ul>
      <div style="display:grid;gap:var(--d-gap)">{previews}</div>
    </section>

    <!-- ── Mermaid Architecture Diagram  (engineer only) ────────────────
         Shows the data-flow from SSOT config through the pipeline to all
         output artefacts.  Requires mermaid.js loaded externally.          -->
    <section class="card aud-engineer" style="background:linear-gradient(135deg,var(--bg-card) 0%,var(--accent-bg) 100%)">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;margin-bottom:1rem">
        <h2 class="card-title" style="margin:0">Mermaid System Flow</h2>
        <span class="badge badge-accent">Diagram</span>
      </div>
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:0.75rem;padding:1rem">
        <div class="mermaid">
          graph LR;
            SSOT[SSOT Config] --> PIPELINE[Pipeline Execution];
            PIPELINE --> MARKDOWN[Markdown Slug Pages];
            PIPELINE --> INDEX[Index HTML];
            PIPELINE --> SLIDES[Slides HTML];
            INDEX --> PDF[PDF Export];
        </div>
      </div>
    </section>

  </main>

  <script>
    /* ── BLSN Report UI Controls ─────────────────────────────────────────
       All user preferences are persisted to localStorage under the "blsn_"
       namespace so they survive hard reloads without server round-trips.

       Theme:    light | dark | auto
         "auto" resolves to light or dark via prefers-color-scheme and keeps
         the <html data-theme> attribute updated when the OS preference
         changes (e.g. switching between light and dark system themes).

       Density:  compact | comfortable | spacious
         Controls the --d-py / --d-px / --d-gap / --d-card CSS tokens that
         scale table cell padding and card gutters without reflowing the page.

       Audience: executive | manager | engineer
         CSS [data-audience] selectors hide .aud-manager and .aud-engineer
         sections for less technical readers.  Changing this value simply
         updates the data attribute; no DOM nodes are added or removed.

       Plotly charts are re-rendered via Plotly.react() rather than
       Plotly.newPlot() when the theme changes so the existing DOM element
       is reused and transitions feel instant.
    ── */
    (function () {{
      'use strict';

      const PREF_NS = 'blsn_';
      const getPref = (k, def) => localStorage.getItem(PREF_NS + k) || def;
      const setPref = (k, v)   => localStorage.setItem(PREF_NS + k, v);

      const root = document.documentElement;

      /* Resolve the "auto" theme sentinel using the OS preference. */
      function resolveTheme(raw) {{
        if (raw !== 'auto') return raw;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }}

      /* Apply a data-attribute and keep its matching <select> in sync. */
      function applyAttr(attr, selectId, value) {{
        root.setAttribute('data-' + attr, value);
        const el = document.getElementById(selectId);
        if (el) el.value = value;
        setPref(attr, value);
      }}

      /* ── Plotly theme-aware rendering ──────────────────────────────── */
      let _payload = null;  /* cached payload to allow re-render on theme change */

      /* Map report theme to the matching built-in Plotly template name. */
      const plotlyTpl = (themeRaw) =>
        resolveTheme(themeRaw) === 'dark' ? 'plotly_dark' : 'plotly_white';

      /* Patch a Plotly chart layout to inherit the current theme colours. */
      function patchLayout(chart, themeRaw) {{
        const isDark = resolveTheme(themeRaw) === 'dark';
        return Object.assign({{}}, chart.layout || {{}}, {{
          template:      plotlyTpl(themeRaw),
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor:  'rgba(0,0,0,0)',
          font:          {{ color: isDark ? '#94a3b8' : '#475569' }},
          xaxis: Object.assign({{}}, (chart.layout || {{}}).xaxis, {{ gridcolor: isDark ? '#334155' : '#e2e8f0' }}),
          yaxis: Object.assign({{}}, (chart.layout || {{}}).yaxis, {{ gridcolor: isDark ? '#334155' : '#e2e8f0' }}),
        }});
      }}

      /* Re-render both Plotly charts with the resolved theme. */
      function rerenderPlotly(themeRaw) {{
        if (!window.Plotly || !_payload) return;
        const charts = _payload.charts || {{}};
        const tel = charts.telemetry_combo  || {{}};
        const pca = charts.pca_bottlenecks  || {{}};
        Plotly.react('plotly-telemetry-chart', tel.data || [], patchLayout(tel, themeRaw));
        Plotly.react('plotly-pca-chart',        pca.data || [], patchLayout(pca, themeRaw));
      }}

      /* ── Public setters wired to onchange handlers ─────────────────── */
      window.setTheme = function (v) {{
        /* Apply the resolved value to data-theme but store the raw choice
           (including "auto") so the select always reflects user intent.   */
        root.setAttribute('data-theme', resolveTheme(v));
        const el = document.getElementById('ctrl-theme');
        if (el) el.value = v;
        setPref('theme', v);
        rerenderPlotly(v);
      }};
      window.setDensity  = (v) => applyAttr('density',  'ctrl-density',  v);
      window.setAudience = (v) => applyAttr('audience', 'ctrl-audience', v);

      /* ── Initialise from saved preferences (fall back to SSOT defaults) */
      const initTheme    = getPref('theme',    '{theme}');
      const initDensity  = getPref('density',  '{density}');
      const initAudience = getPref('audience', '{audience}');

      /* Apply theme without going through the setter so the select shows
         "auto" rather than the resolved value when stored as "auto".      */
      root.setAttribute('data-theme', resolveTheme(initTheme));
      const themeEl = document.getElementById('ctrl-theme');
      if (themeEl) themeEl.value = initTheme;

      applyAttr('density',  'ctrl-density',  initDensity);
      applyAttr('audience', 'ctrl-audience', initAudience);

      /* ── Plotly payload fetch ──────────────────────────────────────── */
      const emptyLayout = (themeRaw) => ({{
        template:      plotlyTpl(themeRaw),
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor:  'rgba(0,0,0,0)',
        xaxis: {{ visible: false }},
        yaxis: {{ visible: false }},
        annotations: [{{
          text: 'No Plotly payload available',
          showarrow: false, xref: 'paper', yref: 'paper', x: 0.5, y: 0.5,
        }}],
      }});

      fetch('visuals/plotly_payloads.json')
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
        .then((payload) => {{
          _payload = payload;
          rerenderPlotly(getPref('theme', '{theme}'));
        }})
        .catch(() => {{
          const el = emptyLayout(getPref('theme', '{theme}'));
          Plotly.newPlot('plotly-telemetry-chart', [], el);
          Plotly.newPlot('plotly-pca-chart',        [], el);
        }});

      /* Keep "auto" theme in sync when the OS preference changes at runtime
         (e.g. user switches system dark mode while the tab is open).       */
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {{
        const stored = getPref('theme', '{theme}');
        if (stored === 'auto') {{
          root.setAttribute('data-theme', resolveTheme('auto'));
          rerenderPlotly('auto');
        }}
      }});
    }})();
  </script>
</body>
</html>""".strip()


def _generate_slides(
    params: dict,
    telemetry_tuples: list[tuple[str, tuple[float, float, float]]],
    output_path: Path,
    base_url: str,
) -> None:
    slides = "\n".join(
        (
            "<section>"
            f"<h2>{escape(_metric_title(metric))}</h2>"
            f"<p><code>{escape(metric)}</code></p>"
            f"<p>Target: {target:.1f}s | Warn: {warn:.1f}s | Fail: {fail:.1f}s</p>"
            f"<p><a href=\"{escape(_join_base(base_url, f'{slugify(metric)}.md'))}\">Open Markdown slug</a></p>"
            "</section>"
        )
        for metric, (target, warn, fail) in telemetry_tuples
    )

    html = f"""
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>BLSN Presentation</title>
    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.css\">
    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/theme/white.css\">
  </head>
  <body>
    <div class=\"reveal\">
      <div class=\"slides\">
        <section>
          <h1>BLSN Telemetry Deck</h1>
          <p>{escape(str(params.get('vehicle_name', 'N/A')))} | {escape(str(params.get('cooling_mode', 'N/A')))}</p>
        </section>
        {slides}
      </div>
    </div>
    <script src=\"https://cdn.jsdelivr.net/npm/reveal.js@5.1.0/dist/reveal.js\"></script>
    <script>Reveal.initialize();</script>
  </body>
</html>
""".strip()
    output_path.write_text(html, encoding="utf-8")


def _write_metric_markdown_files(
    telemetry_tuples: list[tuple[str, tuple[float, float, float]]],
    output_dir: Path,
) -> list[tuple[str, str, str]]:
    pages: list[tuple[str, str, str]] = []

    for metric, thresholds in telemetry_tuples:
        slug = slugify(metric)
        title = _metric_title(metric)
        markdown = _render_metric_markdown(metric, thresholds)
        (output_dir / f"{slug}.md").write_text(markdown, encoding="utf-8")
        pages.append((slug, title, markdown))

    return pages


def _generate_pdf(html_content: str, output_path: Path) -> None:
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("PDF generation requested but fpdf2 is not installed") from exc

    text_content = re.sub(r"<[^>]+>", " ", html_content)
    text_content = re.sub(r"\s+", " ", text_content).strip()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    for chunk_start in range(0, len(text_content), 2000):
        chunk = text_content[chunk_start : chunk_start + 2000]
        wrapped_lines = textwrap.wrap(chunk, width=80, break_long_words=True, break_on_hyphens=True)
        for line in wrapped_lines or [" "]:
            sanitized = line.encode("latin-1", errors="replace").decode("latin-1")
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(190, 8, sanitized)

    pdf.output(str(output_path))


def main() -> None:
    ssot = _load_ssot(CONFIG_PATH)
    params = ssot.get("simulation_parameters", {})
    if not isinstance(params, dict):
        msg = "Missing or invalid simulation_parameters in SSOT"
        raise ValueError(msg)

    sanity_results = collect_sanity_results(params)
    telemetry_tuples = _extract_tuple_telemetry(ssot)
    presentation_layer = _extract_presentation_layer(ssot)
    publishing = _extract_publishing(ssot)

    _export(params)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metric_pages = _write_metric_markdown_files(telemetry_tuples, OUTPUT_DIR)
    kpi_dashboard = _load_kpi_dashboard()
    historical_ledger = _load_json_data(OUTPUT_DIR / "historical_telemetry_ledger.json")
    doe_matrix = _load_json_data(OUTPUT_DIR / "experimental_design_matrix.json")
    bt_ranking = _load_json_data(OUTPUT_DIR / "bt_ranking.json")

    report_html = generate_html_report(
        params,
        sanity_results,
        telemetry_tuples,
        presentation_layer,
        publishing,
        metric_pages,
        kpi_dashboard,
        historical_ledger,
        doe_matrix,
        bt_ranking,
    )
    (OUTPUT_DIR / "index.html").write_text(report_html, encoding="utf-8")

    if bool(publishing.get("generate_slides", False)):
        _generate_slides(
            params,
            telemetry_tuples,
            OUTPUT_DIR / "presentation.html",
            str(publishing.get("base_url", "")),
        )

    if bool(publishing.get("generate_pdf", False)):
        _generate_pdf(report_html, OUTPUT_DIR / "blsn_report.pdf")

    if any("[FAIL]" in result for result in sanity_results):
        raise RuntimeError("Sanity Check FAIL: review generated report and configuration limits")


if __name__ == "__main__":
    main()
