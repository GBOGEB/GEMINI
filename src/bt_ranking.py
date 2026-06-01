"""Bradley-Terry ranking engine powered by PCA eigenvector strengths."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
KPI_DASHBOARD_PATH = DOCS_DIR / "kpi_dashboard.json"
INDEX_PATH = DOCS_DIR / "index.json"
SSOT_PATH = ROOT / "config" / "blsn_config.yaml"
OUTPUT_PATH = DOCS_DIR / "bt_ranking.json"
FEDERATION_CHERRY_PICK_PATH = DOCS_DIR / "federation" / "federation_cherry_pick.json"


@dataclass
class RankEntry:
    name: str
    category: str
    strength: float


class BradleyTerryRanker:
    def __init__(self, strengths: dict[str, float]) -> None:
        self.strengths = {name: max(float(value), 1e-9) for name, value in strengths.items()}

    def probability(self, winner: str, loser: str) -> float:
        p_i = self.strengths.get(winner, 1e-9)
        p_j = self.strengths.get(loser, 1e-9)
        return p_i / (p_i + p_j)

    def ordered(self) -> list[tuple[str, float]]:
        return sorted(self.strengths.items(), key=lambda item: item[1], reverse=True)


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _primary_pca_weights(kpi_dashboard: dict) -> dict[str, float]:
    pca = kpi_dashboard.get("pca_mathematical_proof", {}) if isinstance(kpi_dashboard, dict) else {}
    if not isinstance(pca, dict):
        return {}

    variable_names = pca.get("variable_names", [])
    eigenmatrix = pca.get("eigenmatrix", [])
    if not isinstance(variable_names, list) or not isinstance(eigenmatrix, list):
        return {}

    weights: dict[str, float] = {}
    for index, name in enumerate(variable_names):
        if not isinstance(name, str):
            continue
        if index >= len(eigenmatrix):
            continue
        row = eigenmatrix[index]
        if not isinstance(row, list) or not row:
            continue
        weights[name] = abs(float(row[0] or 0.0))

    return weights


def _item_strength(item: dict, pca_weights: dict[str, float]) -> float:
    file_name = str(item.get("file_name", ""))
    file_type = str(item.get("file_type", "none")).lower()
    size_bytes = int(item.get("size_bytes", 0) or 0)

    avg_weight = sum(pca_weights.values()) / len(pca_weights) if pca_weights else 1.0

    type_anchor = {
        "py": pca_weights.get("runtime_seconds", avg_weight),
        "yaml": pca_weights.get("pass_rate", avg_weight),
        "yml": pca_weights.get("pass_rate", avg_weight),
        "json": pca_weights.get("fail_rate", avg_weight),
        "md": pca_weights.get("skip_rate", avg_weight),
        "html": pca_weights.get("total_tests", avg_weight),
    }.get(file_type, avg_weight)

    size_term = 1.0 + (math.log1p(max(size_bytes, 0)) / 10.0)
    path_term = 1.0 + (len(file_name) / 200.0)

    return max((avg_weight + type_anchor) * size_term * path_term, 1e-9)


def _rank_entries(entries: list[RankEntry]) -> list[dict]:
    strengths = {entry.name: entry.strength for entry in entries}
    ranker = BradleyTerryRanker(strengths)
    ordered = ranker.ordered()
    if not ordered:
        return []

    top_name = ordered[0][0]
    result: list[dict] = []
    for rank_index, (name, strength) in enumerate(ordered, start=1):
        result.append(
            {
                "rank": rank_index,
                "name": name,
                "strength": round(strength, 9),
                "win_probability_vs_top": round(ranker.probability(name, top_name) * 100, 4),
            }
        )
    return result


def _global_and_category_rankings(index_items: list[dict], pca_weights: dict[str, float]) -> dict:
    entries: list[RankEntry] = []
    by_category: defaultdict[str, list[RankEntry]] = defaultdict(list)

    for item in index_items:
        file_name = str(item.get("file_name", "unknown"))
        file_type = str(item.get("file_type", "none")).lower()
        strength = _item_strength(item, pca_weights)
        entry = RankEntry(name=file_name, category=file_type, strength=strength)
        entries.append(entry)
        by_category[file_type].append(entry)

    global_ranking = _rank_entries(entries)

    category_entries = [
        RankEntry(name=category, category="category", strength=sum(item.strength for item in category_items))
        for category, category_items in by_category.items()
    ]
    inter_category_ranking = _rank_entries(category_entries)

    intra_category_ranking = {
        category: _rank_entries(category_items)
        for category, category_items in sorted(by_category.items(), key=lambda item: item[0])
    }

    return {
        "global_repo_ranking": global_ranking,
        "inter_category_ranking": inter_category_ranking,
        "intra_category_ranking": intra_category_ranking,
    }


def _metric_category(metric_name: str, index: int) -> str:
    lowered = metric_name.lower()
    if "safety" in lowered or "safe" in lowered:
        return "Safety"
    if "reliab" in lowered:
        return "Reliability"
    if "performance" in lowered or "runtime" in lowered or "latency" in lowered or "speed" in lowered:
        return "Performance"
    if "cost" in lowered or "price" in lowered:
        return "Cost"
    return ["Safety", "Reliability", "Performance", "Cost"][index % 4]


def _extract_monitored_metrics(ssot: dict) -> list[str]:
    telemetry = ssot.get("telemetry", {}) if isinstance(ssot, dict) else {}
    if not isinstance(telemetry, dict):
        return []

    monitored = telemetry.get("monitored_metrics")
    if isinstance(monitored, list):
        return [str(item) for item in monitored[:50]]

    tuple_targets = telemetry.get("tuple_execution_targets", {})
    if isinstance(tuple_targets, dict):
        return [str(key) for key in list(tuple_targets.keys())[:50]]

    return []


def _requirement_rankings(ssot: dict, pca_weights: dict[str, float]) -> dict:
    metrics = _extract_monitored_metrics(ssot)
    if not metrics:
        return {
            "global": [],
            "by_category": {},
            "federation_external_global": [],
            "global_with_federation": [],
        }

    ordered_weights = list(pca_weights.values()) or [1.0]
    entries: list[RankEntry] = []
    by_category: defaultdict[str, list[RankEntry]] = defaultdict(list)

    for index, metric in enumerate(metrics):
        category = _metric_category(metric, index)
        strength = abs(ordered_weights[index % len(ordered_weights)]) + 1e-9
        entry = RankEntry(name=metric, category=category, strength=strength)
        entries.append(entry)
        by_category[category].append(entry)

    return {
        "global": _rank_entries(entries),
        "by_category": {category: _rank_entries(items) for category, items in sorted(by_category.items())},
        "federation_external_global": [],
        "global_with_federation": _rank_entries(entries),
    }


def _federation_entries(federation_snapshot: dict, pca_weights: dict[str, float]) -> list[RankEntry]:
    if not isinstance(federation_snapshot, dict):
        return []

    runtime_weight = abs(float(pca_weights.get("runtime_seconds", 1.0)))
    fail_weight = abs(float(pca_weights.get("fail_rate", 1.0)))

    external_entries: list[RankEntry] = []

    for item in federation_snapshot.get("abacus_top_slowest_tests", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        variance = abs(float(item.get("variance", 0.0)))
        score = abs(float(item.get("score", 0.0)))
        strength = (1.0 + variance) * (1.0 + math.log1p(score)) * max(runtime_weight, 1e-9)
        external_entries.append(
            RankEntry(
                name=f"ABACUS::{name}",
                category="Federation:ABACUS",
                strength=max(strength, 1e-9),
            )
        )

    for item in federation_snapshot.get("codex_top_governance_violations", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        variance = abs(float(item.get("variance", 0.0)))
        score = abs(float(item.get("score", 0.0)))
        strength = (1.0 + variance) * (1.0 + math.log1p(score)) * max(fail_weight, 1e-9)
        external_entries.append(
            RankEntry(
                name=f"CODEX::{name}",
                category="Federation:CODEX",
                strength=max(strength, 1e-9),
            )
        )

    return external_entries


def _merge_requirement_rankings(base_rankings: dict, external_entries: list[RankEntry]) -> dict:
    external_by_category: defaultdict[str, list[RankEntry]] = defaultdict(list)
    for entry in external_entries:
        external_by_category[entry.category].append(entry)

    merged_by_category = {
        category: list(items)
        for category, items in base_rankings.get("by_category_entries", {}).items()
        if isinstance(items, list)
    }
    for category, items in external_by_category.items():
        merged_by_category.setdefault(category, []).extend(items)

    merged_entries = list(base_rankings.get("global_entries", [])) + external_entries

    return {
        "global": _rank_entries(base_rankings.get("global_entries", [])),
        "by_category": {category: _rank_entries(items) for category, items in sorted(merged_by_category.items())},
        "federation_external_global": _rank_entries(external_entries),
        "global_with_federation": _rank_entries(merged_entries),
    }


def _requirement_rankings_with_federation(
    ssot: dict, pca_weights: dict[str, float], federation_snapshot: dict
) -> dict:
    metrics = _extract_monitored_metrics(ssot)
    if not metrics:
        return {
            "global": [],
            "by_category": {},
            "federation_external_global": _rank_entries(_federation_entries(federation_snapshot, pca_weights)),
            "global_with_federation": _rank_entries(_federation_entries(federation_snapshot, pca_weights)),
        }

    ordered_weights = list(pca_weights.values()) or [1.0]
    entries: list[RankEntry] = []
    by_category: defaultdict[str, list[RankEntry]] = defaultdict(list)

    for index, metric in enumerate(metrics):
        category = _metric_category(metric, index)
        strength = abs(ordered_weights[index % len(ordered_weights)]) + 1e-9
        entry = RankEntry(name=metric, category=category, strength=strength)
        entries.append(entry)
        by_category[category].append(entry)

    base_rankings = {
        "global_entries": entries,
        "by_category_entries": by_category,
    }
    external_entries = _federation_entries(federation_snapshot, pca_weights)
    return _merge_requirement_rankings(base_rankings, external_entries)


def build_bt_output() -> dict:
    kpi_dashboard = _load_json(KPI_DASHBOARD_PATH)
    index_items = _load_json_list(INDEX_PATH)
    ssot = _load_yaml(SSOT_PATH)
    federation_snapshot = _load_json(FEDERATION_CHERRY_PICK_PATH)

    pca_weights = _primary_pca_weights(kpi_dashboard)
    if not pca_weights:
        pca_weights = {
            "runtime_seconds": 1.0,
            "pass_rate": 0.75,
            "fail_rate": 0.5,
            "skip_rate": 0.25,
            "total_tests": 0.6,
        }

    ranking_sets = _global_and_category_rankings(index_items, pca_weights)
    requirements = _requirement_rankings_with_federation(ssot, pca_weights, federation_snapshot)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bt_formula": "P(i>j) = p_i / (p_i + p_j)",
        "pca_strength_vector": pca_weights,
        "global_repo_ranking": ranking_sets["global_repo_ranking"],
        "inter_category_ranking": ranking_sets["inter_category_ranking"],
        "intra_category_ranking": ranking_sets["intra_category_ranking"],
        "qplant_requirements_ranking": requirements,
        "federation_sources": federation_snapshot.get("sources", {}) if isinstance(federation_snapshot, dict) else {},
    }


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    output = build_bt_output()
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
