"""Read-only Google Drive ingress for cross-agent handover packages.

The module intentionally uses the Drive v3 REST API directly so the runtime
credential can be a short-lived OAuth access token minted by GitHub OIDC ->
Google Workload Identity Federation. It never accepts or persists refresh
credentials and never writes to Drive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DRIVE_API = "https://www.googleapis.com/drive/v3"
FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME_PREFIX = "application/vnd.google-apps."
DEFAULT_FIELDS = (
    "nextPageToken,files(id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,"
    "sha1Checksum,sha256Checksum,version,parents,webViewLink)"
)


@dataclass(frozen=True)
class DriveItem:
    """Normalized Drive metadata used by the deterministic census."""

    id: str
    name: str
    mime_type: str
    modified_time: str | None
    created_time: str | None
    size: int | None
    md5: str | None
    sha1: str | None
    sha256: str | None
    version: str | None
    parents: tuple[str, ...]
    web_view_link: str | None
    relative_path: str

    @classmethod
    def from_api(cls, raw: dict[str, Any], relative_path: str) -> "DriveItem":
        size_raw = raw.get("size")
        return cls(
            id=str(raw["id"]),
            name=str(raw.get("name", "")),
            mime_type=str(raw.get("mimeType", "")),
            modified_time=raw.get("modifiedTime"),
            created_time=raw.get("createdTime"),
            size=int(size_raw) if size_raw is not None else None,
            md5=raw.get("md5Checksum"),
            sha1=raw.get("sha1Checksum"),
            sha256=raw.get("sha256Checksum"),
            version=str(raw["version"]) if raw.get("version") is not None else None,
            parents=tuple(str(parent) for parent in raw.get("parents", [])),
            web_view_link=raw.get("webViewLink"),
            relative_path=relative_path,
        )

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME

    @property
    def is_native_google_file(self) -> bool:
        return self.mime_type.startswith(GOOGLE_DOC_MIME_PREFIX) and not self.is_folder

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "relative_path": self.relative_path,
            "mime_type": self.mime_type,
            "is_folder": self.is_folder,
            "is_native_google_file": self.is_native_google_file,
            "modified_time": self.modified_time,
            "created_time": self.created_time,
            "size": self.size,
            "checksums": {
                "md5": self.md5,
                "sha1": self.sha1,
                "sha256": self.sha256,
            },
            "version": self.version,
            "parents": list(self.parents),
            "web_view_link": self.web_view_link,
        }


def _request_json(url: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Drive API HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Drive API unavailable: {exc.reason}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Drive API returned a non-object JSON payload")
    return payload


def list_children(folder_id: str, token: str) -> list[dict[str, Any]]:
    """List every non-trashed direct child of *folder_id*, with pagination."""

    page_token: str | None = None
    children: list[dict[str, Any]] = []
    while True:
        query = f"'{folder_id}' in parents and trashed = false"
        params = {
            "q": query,
            "fields": DEFAULT_FIELDS,
            "pageSize": "1000",
            "orderBy": "name",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}"
        payload = _request_json(url, token)
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise RuntimeError("Drive API 'files' field is not a list")
        children.extend(item for item in files if isinstance(item, dict))
        next_token = payload.get("nextPageToken")
        if not next_token:
            break
        page_token = str(next_token)
    return children


def census_tree(root_folder_id: str, token: str) -> list[DriveItem]:
    """Recursively enumerate a Drive folder into a deterministic flat census."""

    pending: list[tuple[str, str]] = [(root_folder_id, "")]
    seen_folders: set[str] = set()
    items: list[DriveItem] = []

    while pending:
        folder_id, prefix = pending.pop(0)
        if folder_id in seen_folders:
            continue
        seen_folders.add(folder_id)

        children = list_children(folder_id, token)
        normalized: list[DriveItem] = []
        for raw in children:
            name = str(raw.get("name", ""))
            relative_path = f"{prefix}/{name}".lstrip("/")
            normalized.append(DriveItem.from_api(raw, relative_path))

        normalized.sort(key=lambda item: (item.relative_path.casefold(), item.id))
        items.extend(normalized)
        for item in normalized:
            if item.is_folder:
                pending.append((item.id, item.relative_path))

    return sorted(items, key=lambda item: (item.relative_path.casefold(), item.id))


def canonical_census(items: list[DriveItem]) -> list[dict[str, Any]]:
    """Return only stable source identity fields used for the census digest."""

    return [
        {
            "id": item.id,
            "relative_path": item.relative_path,
            "mime_type": item.mime_type,
            "modified_time": item.modified_time,
            "size": item.size,
            "md5": item.md5,
            "sha1": item.sha1,
            "sha256": item.sha256,
            "version": item.version,
        }
        for item in items
    ]


def census_digest(items: list[DriveItem]) -> str:
    canonical = json.dumps(
        canonical_census(items), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_receipt(root_folder_id: str, items: list[DriveItem]) -> dict[str, Any]:
    files = [item for item in items if not item.is_folder]
    folders = [item for item in items if item.is_folder]
    native = [item for item in files if item.is_native_google_file]
    binary = [item for item in files if not item.is_native_google_file]
    return {
        "schema_version": 1,
        "receipt_type": "drive_folder_census",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "provider": "google_drive",
            "root_folder_id": root_folder_id,
            "access_mode": "read_only",
        },
        "summary": {
            "total_items": len(items),
            "folder_count": len(folders),
            "file_count": len(files),
            "native_google_file_count": len(native),
            "binary_file_count": len(binary),
        },
        "census_sha256": census_digest(items),
        "items": [item.as_dict() for item in items],
        "limitations": [
            "Native Google files expose Drive revision/version identity, not byte SHA-256.",
            "No file content is downloaded by this census.",
            "No Drive mutation is performed.",
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder-id", default=os.getenv("GDRIVE_FOLDER_ID"))
    parser.add_argument("--token", default=os.getenv("GDRIVE_ACCESS_TOKEN"))
    parser.add_argument("--output", default="output/drive_ingress/drive_census.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.folder_id:
        print("GDRIVE_FOLDER_ID or --folder-id is required", file=sys.stderr)
        return 2
    if not args.token:
        print("GDRIVE_ACCESS_TOKEN or --token is required", file=sys.stderr)
        return 2

    items = census_tree(str(args.folder_id), str(args.token))
    receipt = build_receipt(str(args.folder_id), items)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Drive census: {receipt['summary']['file_count']} files, "
        f"{receipt['summary']['folder_count']} folders, "
        f"digest={receipt['census_sha256']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
