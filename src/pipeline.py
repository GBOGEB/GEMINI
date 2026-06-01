"""Main engine orchestration for generating BLSN synthetic reports from SSOT config."""

from __future__ import annotations

import json
import re
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
    system_meta = ssot.get("system_meta", {})
    if not isinstance(system_meta, dict):
        return {
            "enable_lipstick": False,
            "css_framework_cdn": "",
            "theme": "light",
        }

    presentation_layer = system_meta.get("presentation_layer", {})
    if not isinstance(presentation_layer, dict):
        return {
            "enable_lipstick": False,
            "css_framework_cdn": "",
            "theme": "light",
        }

    return {
        "enable_lipstick": bool(presentation_layer.get("enable_lipstick", False)),
        "css_framework_cdn": str(presentation_layer.get("css_framework_cdn", "")).strip(),
        "theme": str(presentation_layer.get("theme", "light")).strip().lower() or "light",
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
        '<article class="rounded-xl border border-slate-200 bg-white p-4">'
        f"<h3 class=\"text-lg font-semibold text-slate-900\">{title_html}</h3>"
        f"<ul class=\"mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700\">{bullet_html}</ul>"
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
) -> str:
    presentation = presentation_layer or {"enable_lipstick": False, "css_framework_cdn": "", "theme": "light"}
    publishing_cfg = publishing or {"base_url": "", "generate_pdf": False, "generate_slides": False}

    lipstick_enabled = bool(presentation.get("enable_lipstick", False))
    css_cdn = escape(str(presentation.get("css_framework_cdn", "")))
    theme = escape(str(presentation.get("theme", "light")))
    base_url = str(publishing_cfg.get("base_url", ""))

    cdn_block = f'<script src="{css_cdn}"></script>' if lipstick_enabled and css_cdn else ""

    sanity_rows = "\n".join(
        (
            f'<tr class="{_status_from_alert(alert)} border-b border-slate-200 last:border-none">'
            f'<td class="px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600">{_status_from_alert(alert).upper()}</td>'
            f'<td class="px-4 py-3 text-sm text-slate-700">{escape(alert)}</td>'
            "</tr>"
        )
        for alert in sanity_results
    )

    telemetry_rows = "\n".join(
        (
            '<tr class="border-b border-slate-200 last:border-none">'
            f'<td class="px-4 py-3 font-medium text-slate-800">{escape(metric)}</td>'
            f'<td class="px-4 py-3 text-slate-700">{target:.1f}</td>'
            f'<td class="px-4 py-3 text-amber-700">{warn:.1f}</td>'
            f'<td class="px-4 py-3 text-rose-700">{fail:.1f}</td>'
            "</tr>"
        )
        for metric, (target, warn, fail) in telemetry_tuples
    )
    telemetry_rows = (
        telemetry_rows
        or '<tr><td colspan="4" class="px-4 py-3 text-slate-500">No tuple telemetry configured.</td></tr>'
    )

    metric_links = "\n".join(
        f'<li><a class="text-indigo-600 hover:text-indigo-500" href="{escape(_join_base(base_url, f"{slug}.md"))}">{escape(title)}</a></li>'
        for slug, title, _ in metric_pages or []
    ) or '<li class="text-slate-500">No metric pages generated.</li>'

    previews = "\n".join(_render_markdown_preview(markdown) for _, _, markdown in metric_pages or [])
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
    ledger = historical_ledger if isinstance(historical_ledger, dict) else {}
    ledger_meta = ledger.get("meta", {})
    ledger_meta = ledger_meta if isinstance(ledger_meta, dict) else {}
    total_runs = int(ledger_meta.get("total_attempts", 0) or 0)
    success_rate = float(ledger_meta.get("success_rate", 0.0) or 0.0)
    latest_deltas = ledger_meta.get("latest_deltas", {})
    latest_deltas = latest_deltas if isinstance(latest_deltas, dict) else {}
    previous_runtime = float(latest_deltas.get("previous_runtime_moving_avg", 0.0) or 0.0)

    doe = doe_matrix if isinstance(doe_matrix, dict) else {}
    factor_map = doe.get("factor_map", {})
    factor_map = factor_map if isinstance(factor_map, dict) else {}
    factor_a = escape(str(factor_map.get("A", "python_version")))
    factor_b = escape(str(factor_map.get("B", "os_type")))
    factor_c = escape(str(factor_map.get("C", "load_parameter")))

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
        variance_ratio = float(pca_variance[component_index] or 0.0) if component_index < len(pca_variance) else 0.0
        weights = []
        for variable_index, variable_name in enumerate(pca_variables):
            if variable_index < len(pca_eigenmatrix):
                row_values = pca_eigenmatrix[variable_index]
                if isinstance(row_values, list) and component_index < len(row_values):
                    weights.append((variable_name, abs(float(row_values[component_index] or 0.0))))
        strongest_variable = max(weights, key=lambda item: item[1])[0] if weights else "N/A"
        pca_rows.append(
            "<tr class=\"border-b border-slate-200 last:border-none\">"
            f"<td class=\"px-4 py-3 text-sm text-slate-800\">PC{component_index + 1}</td>"
            f"<td class=\"px-4 py-3 text-sm text-slate-700\">{eigenvalue:.6f}</td>"
            f"<td class=\"px-4 py-3 text-sm text-slate-700\">{variance_ratio:.2%}</td>"
            f"<td class=\"px-4 py-3 text-sm text-slate-700\">{escape(str(strongest_variable))}</td>"
            "</tr>"
        )
    pca_rows_html = (
        "\n".join(pca_rows)
        if pca_rows
        else '<tr><td colspan="4" class="px-4 py-3 text-sm text-slate-500">No PCA proof data available.</td></tr>'
    )

    return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>BLSN Report</title>
  {cdn_block}
</head>
<body class=\"bg-slate-50 text-slate-900\">
  <main class=\"mx-auto max-w-5xl px-6 py-10\">
    <header class=\"mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm\">
      <p class=\"text-xs font-semibold uppercase tracking-[0.2em] text-slate-500\">BLSN</p>
      <h1 class=\"mt-2 text-3xl font-bold tracking-tight text-slate-900\">Synthetic Validation Report</h1>
      <p class=\"mt-3 text-sm text-slate-600\">Theme: <span class=\"font-semibold text-slate-800\">{theme}</span></p>
      <div class=\"mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4\">
        <div class=\"rounded-xl bg-slate-100 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Vehicle</p>
          <p class=\"mt-1 text-lg font-semibold text-slate-900\">{escape(str(params.get('vehicle_name', 'N/A')))}</p>
        </div>
        <div class=\"rounded-xl bg-slate-100 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Cooling Mode</p>
          <p class=\"mt-1 text-lg font-semibold text-slate-900\">{escape(str(params.get('cooling_mode', 'N/A')))}</p>
        </div>
        <div class=\"rounded-xl bg-slate-100 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Nominal Mass Flow</p>
          <p class=\"mt-1 text-lg font-semibold text-slate-900\">{escape(str(params.get('nominal_mass_flow_g_s', 'N/A')))} g/s</p>
        </div>
        <div class=\"rounded-xl bg-slate-100 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Limits</p>
          <p class=\"mt-1 text-lg font-semibold text-slate-900\">{escape(str(params.get('min_limit_g_s', 'N/A')))} - {escape(str(params.get('max_limit_g_s', 'N/A')))} g/s</p>
        </div>
      </div>
    </header>

    <section class=\"mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm\">
      <h2 class=\"text-xl font-semibold text-slate-900\">Sanity Check Telemetry</h2>
      <table class=\"mt-4 w-full overflow-hidden rounded-xl border border-slate-200 bg-white\">
        <thead>
          <tr class=\"bg-slate-100 text-left\">
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Status</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Message</th>
          </tr>
        </thead>
        <tbody>
          {sanity_rows}
        </tbody>
      </table>
    </section>

    <section class=\"mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm\">
      <h2 class=\"text-xl font-semibold text-slate-900\">Tuple Execution Telemetry Targets (seconds)</h2>
      <table class=\"mt-4 w-full overflow-hidden rounded-xl border border-slate-200 bg-white\">
        <thead>
          <tr class=\"bg-slate-100 text-left\">
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Metric</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Target</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Warn Threshold</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Fail Threshold</th>
          </tr>
        </thead>
        <tbody>
          {telemetry_rows}
        </tbody>
      </table>
    </section>

    <section class=\"mb-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm\">
      <h2 class=\"text-xl font-semibold text-slate-900\">Metric Markdown Slugs</h2>
      <ul class=\"mt-4 list-disc space-y-2 pl-5 text-sm\">{metric_links}</ul>
      <div class=\"mt-6 grid gap-4\">{previews}</div>
    </section>

    <section class=\"mb-8 rounded-2xl border border-emerald-200 bg-white p-6 shadow-sm\">
      <h2 class=\"text-xl font-semibold text-slate-900\">System Verification: Claimed vs. Actual</h2>
      <p class=\"mt-3 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-900\">Claimed Limits: {claimed_limits} | Actually Tested Limits: {tested_limits} -&gt; STATUS: <strong>{verification_status}</strong></p>
      <div class=\"mt-4 grid gap-4 md:grid-cols-2\">
        <div class=\"rounded-xl border border-slate-200 bg-slate-50 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Execution Velocity</p>
          <p class=\"mt-1 text-sm text-slate-800\">Total Runtime (engine + tests): <strong>{total_runtime:.4f}s</strong></p>
        </div>
        <div class=\"rounded-xl border border-slate-200 bg-slate-50 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Validation Strictness</p>
          <p class=\"mt-1 text-sm text-slate-800\">Pass: <strong>{pass_ratio:.2%}</strong> | Fail: <strong>{fail_ratio:.2%}</strong> | Skip: <strong>{skip_ratio:.2%}</strong></p>
        </div>
      </div>
    </section>

    <section class=\"mb-8 rounded-2xl border border-violet-200 bg-white p-6 shadow-sm\">
      <h2 class=\"text-xl font-semibold text-slate-900\">Wave 12: SPC &amp; Telemetry Stats</h2>
      <div class=\"mt-4 grid gap-4 md:grid-cols-2\">
        <div class=\"rounded-xl border border-slate-200 bg-slate-50 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Runtime Drift</p>
          <p class=\"mt-1 text-sm text-slate-800\">Current Runtime: <strong>{total_runtime:.4f}s</strong></p>
          <p class=\"text-sm text-slate-700\">Previous Moving Average: <strong>{previous_runtime:.4f}s</strong></p>
        </div>
        <div class=\"rounded-xl border border-slate-200 bg-slate-50 p-4\">
          <p class=\"text-xs uppercase tracking-wide text-slate-500\">Historical Control</p>
          <p class=\"mt-1 text-sm text-slate-800\">Total Accumulated Runs: <strong>{total_runs}</strong></p>
          <p class=\"text-sm text-slate-700\">Success Rate: <strong>{success_rate:.2%}</strong></p>
        </div>
      </div>
      <p class=\"mt-4 text-sm text-slate-700\">DoE Factors - A: <strong>{factor_a}</strong>, B: <strong>{factor_b}</strong>, C: <strong>{factor_c}</strong></p>
      <table class=\"mt-4 w-full overflow-hidden rounded-xl border border-slate-200 bg-white\">
        <thead>
          <tr class=\"bg-slate-100 text-left\">
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Principal Component</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Eigenvalue</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Explained Variance</th>
            <th class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">Highest Weight Variable</th>
          </tr>
        </thead>
        <tbody>
          {pca_rows_html}
        </tbody>
      </table>
    </section>

    <section class=\"rounded-2xl border border-indigo-200 bg-gradient-to-br from-white to-indigo-50 p-6 shadow-sm\">
      <div class=\"mb-4 flex items-center justify-between gap-4\">
        <h2 class=\"text-xl font-semibold text-slate-900\">Mermaid System Flow</h2>
        <span class=\"rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-indigo-700\">Diagram</span>
      </div>
      <div class=\"rounded-xl border border-indigo-100 bg-white p-4\">
        <div class=\"mermaid\">
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
</body>
</html>
""".strip()


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
        pdf.multi_cell(0, 8, chunk)

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
