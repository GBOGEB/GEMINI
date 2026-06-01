"""Federation bridge for CODEX and ABACUS artifact assimilation."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FEDERATION_ROOT = ROOT / "docs" / "federation"
CHERRY_PICK_PATH = FEDERATION_ROOT / "federation_cherry_pick.json"

REPO_DEFINITIONS = {
    "codex": {"owner": "GBOGEB", "repo": "CODEX"},
    "abacus": {"owner": "GBOGEB", "repo": "ABACUS"},
}

ARTIFACT_CANDIDATES = {
    "index.json": ("docs/index.json", "index.json"),
    "kpi_dashboard.json": ("docs/kpi_dashboard.json", "kpi_dashboard.json"),
    "sarif": ("docs/ruff.sarif", "ruff.sarif", "docs/results.sarif", "results.sarif"),
}

SLOWNESS_SCORE_KEYS = (
    "duration",
    "duration_seconds",
    "runtime_seconds",
    "elapsed",
    "elapsed_seconds",
    "time_seconds",
    "avg_duration",
    "mean_duration",
)
ENTITY_NAME_KEYS = ("component", "name", "test", "nodeid", "id", "file", "path", "ruleId", "metric")
SEVERITY_WEIGHTS = {"error": 4.0, "high": 4.0, "warning": 3.0, "medium": 3.0, "low": 2.0, "note": 1.0}


def _json_load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data


def _headers(github_token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "gemini-federation-bridge",
    }
    if github_token:
        headers["Authorization"] = "Bearer " + github_token
    return headers


def _fetch_bytes(url: str, github_token: str | None) -> bytes | None:
    request = Request(url=url, headers=_headers(github_token))
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            return response.read()
    except (HTTPError, URLError, TimeoutError):
        return None


def _fetch_artifact(owner: str, repo: str, candidate_path: str, github_token: str | None) -> bytes | None:
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{candidate_path}"
    payload = _fetch_bytes(raw_url, github_token)
    if payload:
        return payload

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{candidate_path}?ref=main"
    api_payload = _fetch_bytes(api_url, github_token)
    if not api_payload:
        return None

    try:
        metadata = json.loads(api_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(metadata, dict):
        return None

    encoded = metadata.get("content")
    if not isinstance(encoded, str):
        return None

    try:
        return base64.b64decode(encoded)
    except (ValueError, base64.binascii.Error):
        return None


def _download_repo_payloads(repo_key: str, github_token: str | None) -> dict[str, str]:
    repo_info = REPO_DEFINITIONS[repo_key]
    owner = repo_info["owner"]
    repo = repo_info["repo"]
    target_dir = FEDERATION_ROOT / repo_key
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded_paths: dict[str, str] = {}
    for artifact_name, candidates in ARTIFACT_CANDIDATES.items():
        for candidate in candidates:
            payload = _fetch_artifact(owner, repo, candidate, github_token)
            if not payload:
                continue
            filename = artifact_name if artifact_name != "sarif" else Path(candidate).name
            destination = target_dir / filename
            destination.write_bytes(payload)
            downloaded_paths[artifact_name] = str(destination.relative_to(ROOT))
            break

    return downloaded_paths


def _iter_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        nested = [payload]
        for value in payload.values():
            nested.extend(_iter_dicts(value))
        return nested
    if isinstance(payload, list):
        nested: list[dict[str, Any]] = []
        for item in payload:
            nested.extend(_iter_dicts(item))
        return nested
    return []


def _score_from_candidate(item: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        if key not in item:
            continue
        try:
            value = float(item.get(key, 0.0))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return 0.0


def _first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_top_slowest(abacus_payloads: list[Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for payload in abacus_payloads:
        for item in _iter_dicts(payload):
            name = _first_text(item, ENTITY_NAME_KEYS)
            score = _score_from_candidate(item, SLOWNESS_SCORE_KEYS)
            if not name or score <= 0:
                continue
            candidates.append({"name": name, "score": score, "source": "ABACUS"})

    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        current = deduped.get(candidate["name"])
        if current is None or float(candidate["score"]) > float(current["score"]):
            deduped[candidate["name"]] = candidate

    selected = sorted(deduped.values(), key=lambda item: float(item["score"]), reverse=True)[:3]
    if not selected:
        return []

    mean_score = sum(float(item["score"]) for item in selected) / len(selected)
    for item in selected:
        score = float(item["score"])
        item["variance"] = round((score - mean_score) ** 2, 6)
        item["score"] = round(score, 6)
    return selected


def _extract_top_governance(codex_payloads: list[Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for payload in codex_payloads:
        if isinstance(payload, dict) and isinstance(payload.get("runs"), list):
            for run in payload["runs"]:
                if not isinstance(run, dict):
                    continue
                results = run.get("results", [])
                if not isinstance(results, list):
                    continue
                for result in results:
                    if not isinstance(result, dict):
                        continue
                    level = str(result.get("level", "warning")).lower()
                    message = result.get("message", {})
                    text = (
                        str(message.get("text", "")).strip()
                        if isinstance(message, dict)
                        else str(message).strip()
                    )
                    name = str(result.get("ruleId", "")).strip() or text
                    if not name:
                        continue
                    candidates.append(
                        {
                            "name": name[:200],
                            "score": SEVERITY_WEIGHTS.get(level, 1.0),
                            "severity": level,
                            "source": "CODEX",
                        }
                    )

        for item in _iter_dicts(payload):
            severity = str(item.get("severity", item.get("level", ""))).lower()
            if severity not in SEVERITY_WEIGHTS:
                continue
            name = _first_text(item, ("rule", "ruleId", "id", "message", "name", "title"))
            if not name:
                continue
            count = _score_from_candidate(item, ("count", "occurrences", "violations", "total"))
            score = SEVERITY_WEIGHTS.get(severity, 1.0) * max(count, 1.0)
            candidates.append(
                {
                    "name": name[:200],
                    "score": score,
                    "severity": severity,
                    "source": "CODEX",
                }
            )

    deduped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        current = deduped.get(candidate["name"])
        if current is None or float(candidate["score"]) > float(current["score"]):
            deduped[candidate["name"]] = candidate

    selected = sorted(deduped.values(), key=lambda item: float(item["score"]), reverse=True)[:3]
    if not selected:
        return []

    mean_score = sum(float(item["score"]) for item in selected) / len(selected)
    for item in selected:
        score = float(item["score"])
        item["variance"] = round((score - mean_score) ** 2, 6)
        item["score"] = round(score, 6)
    return selected


def build_federation_snapshot(github_token: str | None) -> dict[str, Any]:
    codex_downloads = _download_repo_payloads("codex", github_token)
    abacus_downloads = _download_repo_payloads("abacus", github_token)

    codex_dir = FEDERATION_ROOT / "codex"
    abacus_dir = FEDERATION_ROOT / "abacus"

    codex_payloads = [
        _json_load(codex_dir / "index.json", default=[]),
        _json_load(codex_dir / "kpi_dashboard.json", default={}),
        _json_load(codex_dir / "ruff.sarif", default={}),
        _json_load(codex_dir / "results.sarif", default={}),
    ]
    abacus_payloads = [
        _json_load(abacus_dir / "index.json", default=[]),
        _json_load(abacus_dir / "kpi_dashboard.json", default={}),
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "codex": {"repo": "GBOGEB/CODEX", "downloaded_files": codex_downloads},
            "abacus": {"repo": "GBOGEB/ABACUS", "downloaded_files": abacus_downloads},
        },
        "abacus_top_slowest_tests": _extract_top_slowest(abacus_payloads),
        "codex_top_governance_violations": _extract_top_governance(codex_payloads),
    }


def main() -> None:
    github_token = os.getenv("GITHUB_TOKEN")

    FEDERATION_ROOT.mkdir(parents=True, exist_ok=True)
    snapshot = build_federation_snapshot(github_token)
    CHERRY_PICK_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
