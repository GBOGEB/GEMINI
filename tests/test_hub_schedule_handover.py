"""Synthetic handover bridge negative tests; no tokens, private bids, or Drive IDs."""
import unittest
from pathlib import Path

from src.handover_package import canonical_manifest_digest, validate_manifest
from src.hub_schedule_handover import hub_schedule_manifest

ROOT = Path(__file__).resolve().parents[1]

SHA = "a" * 40


def receipt():
    record = {
        "schema": "jade.iso-schedule.v1",
        "iso_year": 2026,
        "generation_method": "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1",
        "status": "DECLARED_PLAN_ONLY",
        "authority_transfer": False,
        "tasks": {
            "N1": {
                "id": "N1", "title": "Synthetic plan",
                "start": "2026-11-09", "end": "2026-11-09",
                "start_code": "w46MON", "end_code": "w46MON",
                "kind": "milestone", "depends_on": [],
            },
        },
        "waves": [["N1"]],
    }
    record["receipt_sha256"] = canonical_manifest_digest(record)
    return record


def candidate(**over):
    fields = {
        "session_id": "GMI-hub-iso-20261109",
        "generated_at": "2026-11-09T00:00:00Z",
        "source_sha": SHA,
        "source_path": "mission-control/jade_temple/tools/iso_schedule.py",
        "receipt": receipt(),
    }
    fields.update(over)
    return hub_schedule_manifest(**fields)


class HubScheduleHandover(unittest.TestCase):
    def test_native_gemini_schema_accepts_declared_candidate(self):
        m = candidate()
        result = validate_manifest(m, ROOT)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["deferred"], [])
        self.assertEqual(m["status"], "DECLARED")
        self.assertEqual(m["source_refs"][0]["source_sha"], SHA)
        self.assertFalse(m["artifact_refs"])
        self.assertEqual(m["source_refs"][0]["receipt_sha256"], receipt()["receipt_sha256"])

    def test_never_promote_hub_plan_to_verified(self):
        m = candidate()
        self.assertNotEqual(m["status"], "VERIFIED")
        self.assertNotIn("approved", m["current_gate"].lower())

    def test_missing_or_fake_commit_rejected(self):
        for bad in ("", "abc", "g" * 40, "A" * 40):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                candidate(source_sha=bad)

    def test_cross_repo_and_escape_path_rejected(self):
        for path in ("../private.txt", "mission-control/jade_temple/../../private",
                     "mission-control/jade_temple/"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                candidate(source_path=path)

    def test_invalid_or_escalated_receipt_rejected(self):
        for key, value in (("status", "VERIFIED"), ("authority_transfer", True),
                           ("schema", "alternate"), ("tasks", {}), ("iso_year", None)):
            r = receipt()
            r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate(receipt=r)

    def test_portable_digest_rejects_in_place_mutation(self):
        record = receipt()
        record["tasks"]["N1"]["title"] = "Modified after hash"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            candidate(receipt=record)

    def test_portable_digest_rejects_fabricated_or_missing_value(self):
        for value in (None, "0" * 64, "INVALID"):
            record = receipt()
            if value is None:
                del record["receipt_sha256"]
            else:
                record["receipt_sha256"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                candidate(receipt=record)

    def test_wrong_generation_method_cannot_be_relabelled(self):
        record = receipt()
        record["generation_method"] = "UNRECOGNIZED_RUNTIME"
        record["receipt_sha256"] = canonical_manifest_digest(
            {k: v for k, v in record.items() if k != "receipt_sha256"}
        )
        with self.assertRaisesRegex(ValueError, "generation method"):
            candidate(receipt=record)

    def test_valid_id_and_session_identity(self):
        with self.assertRaises(ValueError):
            candidate(session_id="not-GMI")
        self.assertEqual(candidate()["session_id"], "GMI-hub-iso-20261109")


if __name__ == "__main__":
    unittest.main()
