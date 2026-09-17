from __future__ import annotations

import json

from src.drive_ingress import DriveItem, build_receipt, canonical_census, census_digest


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


def test_census_digest_is_deterministic() -> None:
    items = [
        _item("2", "B.md", "text/markdown", "GMI-001/B.md", sha256="abc"),
        _item("1", "A", "application/vnd.google-apps.folder", "GMI-001"),
    ]

    digest_a = census_digest(items)
    digest_b = census_digest(list(items))

    assert digest_a == digest_b
    assert len(digest_a) == 64


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

    receipt = build_receipt("root", items)

    assert receipt["summary"] == {
        "total_items": 3,
        "folder_count": 1,
        "file_count": 2,
        "native_google_file_count": 1,
        "binary_file_count": 1,
    }
    assert receipt["source"]["access_mode"] == "read_only"
    json.dumps(receipt)
