from __future__ import annotations

import json

import pytest

from src import drive_ingress
from src.drive_ingress import (
    DriveIngressError,
    DriveItem,
    build_receipt,
    canonical_census,
    census_digest,
    census_tree,
    get_root_folder,
)


def _item(
    item_id: str,
    name: str,
    mime_type: str,
    relative_path: str,
    *,
    version: str | None = None,
    sha256: str | None = None,
) -> DriveItem:
    return DriveItem(
        id=item_id,
        name=name,
        mime_type=mime_type,
        modified_time="2026-09-17T05:00:00Z",
        created_time="2026-09-17T04:00:00Z",
        size=123 if mime_type != "application/vnd.google-apps.folder" else None,
        md5=None,
        sha1=None,
        sha256=sha256,
        version=version,
        parents=("root",),
        web_view_link=f"https://drive.google.com/open?id={item_id}",
        relative_path=relative_path,
    )


def _root(**overrides):
    value = {
        "id": "root",
        "name": "GEMINI_QPS_HANDOVER",
        "version": "4",
        "mimeType": drive_ingress.FOLDER_MIME,
        "trashed": False,
    }
    value.update(overrides)
    return value


def test_census_digest_is_deterministic() -> None:
    items = [
        _item("2", "B.md", "text/markdown", "GMI-001/B.md", sha256="abc"),
        _item("1", "A", "application/vnd.google-apps.folder", "GMI-001"),
    ]
    assert census_digest(items) == census_digest(list(items))
    assert len(census_digest(items)) == 64


def test_digest_changes_when_drive_version_changes() -> None:
    before = [_item("doc", "handover", "application/vnd.google-apps.document", "GMI-001/handover", version="7")]
    after = [_item("doc", "handover", "application/vnd.google-apps.document", "GMI-001/handover", version="8")]
    assert census_digest(before) != census_digest(after)


def test_canonical_census_excludes_non_identity_display_fields() -> None:
    item = _item("doc", "handover", "application/vnd.google-apps.document", "GMI-001/handover", version="8")
    payload = canonical_census([item])[0]
    assert "web_view_link" not in payload
    assert "created_time" not in payload
    assert payload["version"] == "8"


def test_receipt_separates_native_and_binary_files() -> None:
    items = [
        _item("folder", "GMI-001", "application/vnd.google-apps.folder", "GMI-001"),
        _item("doc", "handover", "application/vnd.google-apps.document", "GMI-001/handover", version="8"),
        _item("md", "raw.md", "text/markdown", "GMI-001/raw.md", sha256="abc"),
    ]
    receipt = build_receipt("root", items, root=_root())
    assert receipt["summary"] == {
        "total_items": 3,
        "folder_count": 1,
        "file_count": 2,
        "native_google_file_count": 1,
        "binary_file_count": 1,
    }
    assert receipt["source"]["access_mode"] == "read_only"
    assert receipt["source"]["root_verified"] is True
    assert receipt["result"] == "PASS_IC3_DRIVE_ROOT_AND_CENSUS"
    json.dumps(receipt)


def test_get_root_folder_rejects_non_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drive_ingress, "_request_json", lambda url, token: _root(mimeType="text/plain"))
    with pytest.raises(DriveIngressError, match="not a folder") as exc:
        get_root_folder("root", "token")
    assert exc.value.code == "ROOT_NOT_FOLDER"


def test_get_root_folder_rejects_trashed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(drive_ingress, "_request_json", lambda url, token: _root(trashed=True))
    with pytest.raises(DriveIngressError, match="trashed") as exc:
        get_root_folder("root", "token")
    assert exc.value.code == "ROOT_TRASHED"


def test_get_root_folder_rejects_missing_trashed_state(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _root()
    del raw["trashed"]
    monkeypatch.setattr(drive_ingress, "_request_json", lambda url, token: raw)
    with pytest.raises(DriveIngressError) as exc:
        get_root_folder("root", "token")
    assert exc.value.code == "ROOT_TRASHED_STATE_UNPROVEN"


def test_root_forbidden_preserves_api_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    def deny(url: str, token: str):
        raise DriveIngressError("DRIVE_API_FORBIDDEN", "forbidden")

    monkeypatch.setattr(drive_ingress, "_request_json", deny)
    with pytest.raises(DriveIngressError) as exc:
        get_root_folder("root", "token")
    assert exc.value.code == "DRIVE_API_FORBIDDEN"


def test_root_not_found_maps_to_root_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(url: str, token: str):
        raise DriveIngressError("DRIVE_RESOURCE_NOT_FOUND", "not found")

    monkeypatch.setattr(drive_ingress, "_request_json", missing)
    with pytest.raises(DriveIngressError) as exc:
        get_root_folder("root", "token")
    assert exc.value.code == "ROOT_INACCESSIBLE_OR_MISSING"


def test_census_verifies_root_before_children(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_request(url: str, token: str):
        calls.append(url)
        return _root(version="1")

    monkeypatch.setattr(drive_ingress, "_request_json", fake_request)
    monkeypatch.setattr(drive_ingress, "list_children", lambda folder_id, token: [])
    root, items = census_tree("root", "token")
    assert root["id"] == "root"
    assert items == []
    assert calls and "/files/root?" in calls[0]


def test_main_rejects_zero_item_census(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(drive_ingress, "census_tree", lambda folder_id, token: (_root(), []))
    status = tmp_path / "status.json"
    output = tmp_path / "census.json"
    rc = drive_ingress.main([
        "--folder-id", "root",
        "--token", "token",
        "--output", str(output),
        "--status-output", str(status),
    ])
    assert rc == 3
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["classification"] == "CENSUS_ZERO_ITEMS"
    assert not output.exists()
