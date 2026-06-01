"""Repository indexing engine for docs/config artifacts."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
CONFIG_DIR = ROOT / "config"
MANIFEST_PATH = ROOT / "repo_manifest.yaml"


def _load_manifest_version() -> str:
    if not MANIFEST_PATH.exists():
        return "unknown"

    try:
        data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return "unknown"

    if not isinstance(data, dict):
        return "unknown"

    version_control = data.get("version_control", {})
    if not isinstance(version_control, dict):
        return "unknown"

    return str(version_control.get("manifest_version", "unknown"))


def _safe_relative(path: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except (ValueError, OSError):
        return None


def _lineage_for(path: Path) -> str:
    relative = _safe_relative(path)
    if not relative:
        return "Lineage unknown"

    if relative.startswith("docs/"):
        return "Generated from config/blsn_config.yaml"
    if relative.startswith("config/"):
        return "Source configuration artifact"
    return "Repository artifact"


def _collect_records() -> list[dict[str, str | int]]:
    records: list[dict[str, str | int]] = []

    for base in (DOCS_DIR, CONFIG_DIR):
        if not base.exists() or not base.is_dir():
            continue

        for file_path in sorted(base.rglob("*")):
            if not file_path.is_file():
                continue

            relative = _safe_relative(file_path)
            if not relative:
                continue

            try:
                stat = file_path.stat()
            except OSError:
                continue

            records.append(
                {
                    "file_name": relative,
                    "file_type": file_path.suffix.lstrip(".") or "none",
                    "size_bytes": int(stat.st_size),
                    "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "lineage": _lineage_for(file_path),
                }
            )

    return records


def _write_outputs(records: list[dict[str, str | int]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    (DOCS_DIR / "index.json").write_text(json.dumps(records, indent=2), encoding="utf-8")

    summary = {
        "total_files": len(records),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in records),
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "manifest_version": _load_manifest_version(),
    }

    (DOCS_DIR / "index.yaml").write_text(
        yaml.safe_dump(summary, sort_keys=False),
        encoding="utf-8",
    )


def main() -> None:
    try:
        records = _collect_records()
        _write_outputs(records)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"Indexer fallback activated: {exc}", file=sys.stderr)
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_DIR / "index.json").write_text("[]\n", encoding="utf-8")
        (DOCS_DIR / "index.yaml").write_text(
            yaml.safe_dump(
                {
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                    "manifest_version": "unknown",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
