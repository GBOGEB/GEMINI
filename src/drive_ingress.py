"""Read-only Google Drive ingress for cross-agent handover packages.

The runtime credential is a short-lived OAuth access token minted by GitHub
OIDC -> Google Workload Identity Federation. The module never accepts refresh
credentials, never writes to Drive, and fails closed unless the configured root
folder itself is proved readable before child enumeration begins.
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
ROOT_FIELDS = (
    "id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,sha1Checksum,"
    "sha256Checksum,version,parents,webViewLink,trashed"
)


class DriveIngressError(RuntimeError):
    """A classified, user-actionable Drive ingress failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DriveItem:
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
            "checksums": {"md5": self.md5, "sha1": self.sha1, "sha256": self.sha256},
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
        if exc.code == 401:
            code = "GOOGLE_ACCESS_TOKEN_REJECTED"
        elif exc.code == 403:
            code = "DRIVE_API_FORBIDDEN"
        elif exc.code == 404:
            code = "DRIVE_RESOURCE_NOT_FOUND"
        else:
            code = "DRIVE_API_HTTP_ERROR"
        raise DriveIngressError(code, f"Drive API HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise DriveIngressError("DRIVE_API_UNAVAILABLE", f"Drive API unavailable: {exc.reason}") from exc

    if not isinstance(payload, dict):
        raise DriveIngressError("DRIVE_API_INVALID_RESPONSE", "Drive API returned a non-object JSON payload")
    return payload


def get_root_folder(folder_id: str, token: str) -> dict[str, Any]:
    """Prove that the configured root exists, is readable, non-trashed and a folder."""

    encoded_id = urllib.parse.quote(folder_id, safe="")
    params = {"fields": ROOT_FIELDS, "supportsAllDrives": "true"}
    url = f"{DRIVE_API}/files/{encoded_id}?{urllib.parse.urlencode(params)}"
    try:
        raw = _request_json(url, token)
    except DriveIngressError as exc:
        if exc.code == "DRIVE_RESOURCE_NOT_FOUND":
            raise DriveIngressError(
                "ROOT_INACCESSIBLE_OR_MISSING",
                "Configured Drive root was not found; verify the folder ID and that the Google principal can see it",
            ) from exc
        # Preserve 403 and other API classifications because Drive uses 403 for
        # policy/quota/API conditions as well as permission failures.
        raise

    if str(raw.get("id", "")) != folder_id:
        raise DriveIngressError("ROOT_ID_MISMATCH", "Drive root response did not bind the requested folder ID")
    if raw.get("trashed") is True:
        raise DriveIngressError("ROOT_TRASHED", "Configured Drive root is trashed")
    if raw.get("trashed") is not False:
        raise DriveIngressError(
            "ROOT_TRASHED_STATE_UNPROVEN",
            "Drive root response did not explicitly prove trashed=false",
        )
    if raw.get("mimeType") != FOLDER_MIME:
        raise DriveIngressError("ROOT_NOT_FOLDER", "Configured Drive root is not a folder")
    return raw


def list_children(folder_id: str, token: str) -> list[dict[str, Any]]:
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
        payload = _request_json(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}", token)
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise DriveIngressError("DRIVE_API_INVALID_RESPONSE", "Drive API 'files' field is not a list")
        children.extend(item for item in files if isinstance(item, dict))
        next_token = payload.get("nextPageToken")
        if not next_token:
            break
        page_token = str(next_token)
    return children


def census_tree(root_folder_id: str, token: str) -> tuple[dict[str, Any], list[DriveItem]]:
    """Verify the root then recursively enumerate it into a deterministic census."""

    root = get_root_folder(root_folder_id, token)
    pending: list[tuple[str, str]] = [(root_folder_id, "")]
    seen_folders: set[str] = set()
    items: list[DriveItem] = []

    while pending:
        folder_id, prefix = pending.pop(0)
        if folder_id in seen_folders:
            continue
        seen_folders.add(folder_id)
        normalized: list[DriveItem] = []
        for raw in list_children(folder_id, token):
            name = str(raw.get("name", ""))
            relative_path = f"{prefix}/{name}".lstrip("/")
            normalized.append(DriveItem.from_api(raw, relative_path))
        normalized.sort(key=lambda item: (item.relative_path.casefold(), item.id))
        items.extend(normalized)
        for item in normalized:
            if item.is_folder:
                pending.append((item.id, item.relative_path))

    return root, sorted(items, key=lambda item: (item.relative_path.casefold(), item.id))


def canonical_census(items: list[DriveItem]) -> list[dict[str, Any]]:
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


def build_receipt(root_folder_id: str, items: list[DriveItem], root: dict[str, Any] | None = None) -> dict[str, Any]:
    files = [item for item in items if not item.is_folder]
    folders = [item for item in items if item.is_folder]
    native = [item for item in files if item.is_native_google_file]
    binary = [item for item in files if not item.is_native_google_file]
    return {
        "schema_version": 2,
        "receipt_type": "drive_folder_census",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "result": "PASS_IC3_DRIVE_ROOT_AND_CENSUS",
        "source": {
            "provider": "google_drive",
            "root_folder_id": root_folder_id,
            "root_verified": root is not None,
            "root_name": None if root is None else root.get("name"),
            "root_version": None if root is None else str(root.get("version")) if root.get("version") is not None else None,
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


def write_status(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder-id", default=os.getenv("GDRIVE_FOLDER_ID"))
    parser.add_argument("--token", default=os.getenv("GDRIVE_ACCESS_TOKEN"))
    parser.add_argument("--output", default="output/drive_ingress/drive_census.json")
    parser.add_argument("--status-output", default="output/drive_ingress/ic3_status.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.folder_id:
        write_status(args.status_output, {"result": "FAIL", "classification": "CONFIG_MISSING_FOLDER_ID"})
        print("GDRIVE_FOLDER_ID or --folder-id is required", file=sys.stderr)
        return 2
    if not args.token:
        write_status(args.status_output, {"result": "FAIL", "classification": "CONFIG_MISSING_ACCESS_TOKEN"})
        print("GDRIVE_ACCESS_TOKEN or --token is required", file=sys.stderr)
        return 2

    try:
        root, items = census_tree(str(args.folder_id), str(args.token))
        if not items:
            raise DriveIngressError(
                "CENSUS_ZERO_ITEMS",
                "Drive root was readable but recursive enumeration returned zero items; IC3 requires a positive census",
            )
        receipt = build_receipt(str(args.folder_id), items, root=root)
    except DriveIngressError as exc:
        write_status(
            args.status_output,
            {"result": "FAIL", "classification": exc.code, "message": str(exc), "root_folder_id": str(args.folder_id)},
        )
        print(f"{exc.code}: {exc}", file=sys.stderr)
        return 3

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    write_status(
        args.status_output,
        {
            "result": "PASS",
            "classification": "IC3_DRIVE_READONLY_GT0_STEP_PASS",
            "root_folder_id": str(args.folder_id),
            "root_verified": True,
            "census_sha256": receipt["census_sha256"],
            "total_items": receipt["summary"]["total_items"],
            "file_count": receipt["summary"]["file_count"],
            "folder_count": receipt["summary"]["folder_count"],
        },
    )
    print(
        f"Drive census: {receipt['summary']['file_count']} files, {receipt['summary']['folder_count']} folders, digest={receipt['census_sha256']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
