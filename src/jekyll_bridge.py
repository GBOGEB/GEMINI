"""Bridge generated Python artifacts into Jekyll data and metric collections."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
DATA_DIR = DOCS_DIR / "_data"
METRICS_DIR = DOCS_DIR / "_metrics"

SSOT_SOURCE = ROOT / "config" / "blsn_config.yaml"
INDEX_SOURCE = DOCS_DIR / "index.json"
PLOTLY_SOURCE = DOCS_DIR / "visuals" / "plotly_payloads.json"
BT_SOURCE = DOCS_DIR / "bt_ranking.json"


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "metric"


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_yaml_data(name: str, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / name
    target.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _write_json_data(name: str, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / name
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _requirement_metrics(ssot: dict, bt_ranking: dict) -> list[dict[str, object]]:
    ranking = bt_ranking.get("qplant_requirements_ranking", {}) if isinstance(bt_ranking, dict) else {}
    global_reqs = ranking.get("global", []) if isinstance(ranking, dict) else []

    metrics: list[dict[str, object]] = []
    if isinstance(global_reqs, list):
        for req in global_reqs:
            if not isinstance(req, dict):
                continue
            metric_id = req.get("name")
            if not isinstance(metric_id, str) or not metric_id.strip():
                continue
            metrics.append(
                {
                    "metric_id": metric_id,
                    "rank": int(req.get("rank", 0) or 0),
                    "strength": float(req.get("strength", 0.0) or 0.0),
                }
            )

    if metrics:
        return metrics

    telemetry = ssot.get("telemetry", {}) if isinstance(ssot, dict) else {}
    tuple_targets = telemetry.get("tuple_execution_targets", {}) if isinstance(telemetry, dict) else {}
    if not isinstance(tuple_targets, dict):
        return []

    return [
        {
            "metric_id": key,
            "rank": 0,
            "strength": 0.0,
        }
        for key in tuple_targets
        if isinstance(key, str) and key.strip()
    ]


def _render_metric_markdown(metric: dict[str, object]) -> str:
    metric_id = str(metric["metric_id"])
    title = metric_id.replace("_", " ").strip().title()
    frontmatter = {
        "layout": "default",
        "title": title,
        "metric_id": metric_id,
        "chart_id": "telemetry_combo",
    }

    if int(metric.get("rank", 0) or 0) > 0:
        frontmatter["qplant_rank"] = int(metric["rank"])
    if float(metric.get("strength", 0.0) or 0.0) > 0:
        frontmatter["qplant_strength"] = round(float(metric["strength"]), 9)

    frontmatter_yaml = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    body = (
        f"# {title}\n\n"
        f"{{% include metric_card.html metric_id=\"{metric_id}\" %}}\n\n"
        "{% include plotly_render.html chart_id=page.chart_id %}\n"
    )
    return f"---\n{frontmatter_yaml}\n---\n\n{body}"


def _sync_metric_pages(metrics: list[dict[str, object]]) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    expected_paths: set[Path] = set()

    for metric in metrics:
        slug = _slugify(str(metric["metric_id"]))
        target = METRICS_DIR / f"{slug}.md"
        target.write_text(_render_metric_markdown(metric), encoding="utf-8")
        expected_paths.add(target)

    for existing in METRICS_DIR.glob("*.md"):
        if existing not in expected_paths:
            existing.unlink()


def main() -> None:
    ssot = _load_yaml(SSOT_SOURCE)
    index_data = _load_json(INDEX_SOURCE)
    plotly_data = _load_json(PLOTLY_SOURCE)
    bt_data = _load_json(BT_SOURCE)

    _write_yaml_data("blsn_config.yml", ssot)
    _write_json_data("index.json", index_data)
    _write_json_data("plotly_payloads.json", plotly_data)
    _write_json_data("bt_ranking.json", bt_data)

    _sync_metric_pages(_requirement_metrics(ssot, bt_data))


if __name__ == "__main__":
    main()
