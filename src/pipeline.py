"""
Main engine orchestration for generating BLSN synthetic reports from SSOT config.
"""

from contextlib import redirect_stdout
from html import escape
from io import StringIO
from pathlib import Path

from src.parameters import load_config
from src.reporter import export_outputs
from src.validators import run_sanity_checks


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


def generate_html_report(params: dict, sanity_results: list[str]) -> str:
    rows = "\n".join(
        (
            f"<tr class=\"{_status_from_alert(alert)}\">"
            f"<td>{_status_from_alert(alert).upper()}</td>"
            f"<td>{escape(alert)}</td>"
            "</tr>"
        )
        for alert in sanity_results
    )

    return f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>BLSN Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; }}
    .sanity-widget {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 1rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 0.75rem; }}
    th, td {{ padding: 0.6rem; border: 1px solid #d0d7de; text-align: left; }}
    tr.pass td:first-child {{ background: #2da44e; color: #fff; font-weight: 700; }}
    tr.warn td:first-child {{ background: #bf8700; color: #fff; font-weight: 700; }}
    tr.fail td:first-child {{ background: #cf222e; color: #fff; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>BLSN Synthetic Validation Report</h1>
  <p><strong>Vehicle:</strong> {escape(str(params.get('vehicle_name', 'N/A')))}</p>
  <p><strong>Cooling Mode:</strong> {escape(str(params.get('cooling_mode', 'N/A')))}</p>
  <ul>
    <li>Nominal Mass Flow: {escape(str(params.get('nominal_mass_flow_g_s', 'N/A')))}</li>
    <li>Max Limit: {escape(str(params.get('max_limit_g_s', 'N/A')))}</li>
    <li>Min Limit: {escape(str(params.get('min_limit_g_s', 'N/A')))}</li>
  </ul>

  <section class=\"sanity-widget\">
    <h2>Sanity Check Telemetry</h2>
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </section>
</body>
</html>
""".strip()


def main() -> None:
    params = load_config("config/blsn_config.yaml")
    sanity_results = collect_sanity_results(params)

    export_outputs(params)

    report_path = Path("output") / "blsn_report.html"
    report_path.write_text(generate_html_report(params, sanity_results), encoding="utf-8")

    if any("[FAIL]" in result for result in sanity_results):
        raise RuntimeError("Sanity Check FAIL: review generated report and configuration limits")


if __name__ == "__main__":
    main()
