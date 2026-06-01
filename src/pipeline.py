"""Main engine orchestration for generating BLSN synthetic reports from SSOT config."""

from contextlib import redirect_stdout
from html import escape
from io import StringIO
from pathlib import Path

import yaml

from src.reporter import export_outputs
from src.validators import run_sanity_checks


CONFIG_PATH = "config/blsn_config.yaml"


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


def collect_sanity_results(params: dict) -> list[str]:
    output = StringIO()
    failure: str | None = None

    try:
        with redirect_stdout(output):
            run_sanity_checks(params)
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


def generate_html_report(
    params: dict,
    sanity_results: list[str],
    telemetry_tuples: list[tuple[str, tuple[float, float, float]]],
    presentation_layer: dict[str, str | bool],
) -> str:
    lipstick_enabled = bool(presentation_layer.get("enable_lipstick", False))
    css_cdn = escape(str(presentation_layer.get("css_framework_cdn", "")))
    theme = escape(str(presentation_layer.get("theme", "light")))
    cdn_block = f"<script src=\"{css_cdn}\"></script>" if lipstick_enabled and css_cdn else ""

    sanity_rows = "\n".join(
        (
            f"<tr class=\"border-b border-slate-200 last:border-none {_status_from_alert(alert)}\">"
            f"<td class=\"px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-600\">{_status_from_alert(alert).upper()}</td>"
            f"<td class=\"px-4 py-3 text-sm text-slate-700\">{escape(alert)}</td>"
            "</tr>"
        )
        for alert in sanity_results
    )

    telemetry_rows = "\n".join(
        (
           "<tr class=\"border-b border-slate-200 last:border-none\">"
           f"<td class=\"px-4 py-3 font-medium text-slate-800\">{escape(metric)}</td>"
           f"<td class=\"px-4 py-3 text-slate-700\">{target:.1f}</td>"
           f"<td class=\"px-4 py-3 text-amber-700\">{warn:.1f}</td>"
           f"<td class=\"px-4 py-3 text-rose-700\">{fail:.1f}</td>"
            "</tr>"
        )
        for metric, (target, warn, fail) in telemetry_tuples
    )
   telemetry_rows = (
       telemetry_rows
       or "<tr><td colspan=\"4\" class=\"px-4 py-3 text-slate-500\">No tuple telemetry configured.</td></tr>"
   )

   return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
 <meta charset=\"utf-8\">
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

   <section class=\"rounded-2xl border border-indigo-200 bg-gradient-to-br from-white to-indigo-50 p-6 shadow-sm\">
     <div class=\"mb-4 flex items-center justify-between gap-4\">
       <h2 class=\"text-xl font-semibold text-slate-900\">Mermaid System Flow</h2>
       <span class=\"rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-indigo-700\">Diagram</span>
     </div>
     <div class=\"rounded-xl border border-indigo-100 bg-white p-4\">
       <div class=\"mermaid\">
         graph LR;
           SSOT[SSOT Config] --> PIPELINE[Pipeline Execution];
           PIPELINE --> SANITY[Sanity Checks];
           PIPELINE --> EXPORT[Output Export];
           SANITY --> REPORT[HTML Report];
           EXPORT --> REPORT;
       </div>
     </div>
   </section>
 </main>
</body>
</html>
""".strip()


def main() -> None:
    ssot = _load_ssot(CONFIG_PATH)
    params = ssot.get("simulation_parameters", {})
    if not isinstance(params, dict):
        msg = "Missing or invalid simulation_parameters in SSOT"
        raise ValueError(msg)

    sanity_results = collect_sanity_results(params)
    telemetry_tuples = _extract_tuple_telemetry(ssot)
    presentation_layer = _extract_presentation_layer(ssot)

    export_outputs(params)

    report_path = Path("output") / "blsn_report.html"
    report_path.write_text(
        generate_html_report(params, sanity_results, telemetry_tuples, presentation_layer),
        encoding="utf-8",
    )

    if any("[FAIL]" in result for result in sanity_results):
        raise RuntimeError("Sanity Check FAIL: review generated report and configuration limits")


if __name__ == "__main__":
    main()
