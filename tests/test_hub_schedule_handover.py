"""Synthetic handover bridge negative tests; no tokens, private bids, or Drive IDs."""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from hub_schedule_handover import hub_schedule_manifest
from handover_package import validate_manifest

SHA = "a" * 40


def receipt():
    return {"schema": "jade.iso-schedule.v1", "iso_year": 2026,
            "status": "DECLARED_PLAN_ONLY", "authority_transfer": False,
            "tasks": {"N1": {"id": "N1"}}, "waves": [["N1"]]}


def candidate(**over):
    fields = dict(session_id="GMI-hub-iso-20261109", generated_at="2026-11-09T00:00:00Z",
                  source_sha=SHA,
                  source_path="mission-control/jade_temple/tools/iso_schedule.py",
                  receipt=receipt())
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

    def test_valid_id_and_session_identity(self):
        with self.assertRaises(ValueError):
            candidate(session_id="not-GMI")
        self.assertEqual(candidate()["session_id"], "GMI-hub-iso-20261109")


if __name__ == "__main__":
    unittest.main()
