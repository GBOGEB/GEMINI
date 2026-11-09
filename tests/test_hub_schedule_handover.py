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



def utf8_vector_receipt():
    """Cross-runtime fixed fixture independently hashed in Hub Python and Node."""
    return {
        "schema": "jade.iso-schedule.v1",
        "iso_year": 2026,
        "generation_method": "JADE_ISO_SCHEDULE_PORTABLE_RECEIPT_V1",
        "canonicalization": "JADE_CANONICAL_UTF8_JSON_V1",
        "status": "DECLARED_PLAN_ONLY",
        "authority_transfer": False,
        "tasks": {
            "CAFE": {
                "id": "CAFE", "title": "Caf\u00e9 \U0001f52c/\u2206",
                "start": "2026-11-09", "end": "2026-11-09",
                "start_code": "w46MON", "end_code": "w46MON",
                "kind": "task", "depends_on": [],
            },
        },
        "waves": [["CAFE"]],
        "receipt_sha256": "bb7d5953a763eed0e7b9d0cd7741f7ae2c128d5305677884d44fbd8038b80c17",
    }



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


    def test_explicit_utf8_profile_accepts_hub_node_fixed_vector(self):
        record = utf8_vector_receipt()
        payload = {k: v for k, v in record.items() if k != "receipt_sha256"}
        self.assertEqual(
            canonical_manifest_digest(payload, ensure_ascii=False),
            "bb7d5953a763eed0e7b9d0cd7741f7ae2c128d5305677884d44fbd8038b80c17",
        )
        self.assertNotEqual(
            canonical_manifest_digest(payload), record["receipt_sha256"],
            "legacy escaped-ASCII encoding must not be silently accepted",
        )
        result = candidate(receipt=record)
        self.assertEqual(result["status"], "DECLARED")
        self.assertEqual(result["source_refs"][0]["receipt_sha256"], record["receipt_sha256"])
        self.assertEqual(result["source_refs"][0]["owner_disposition"], "NOT_APPROVED")

    def test_legacy_manifest_digest_mode_is_unchanged(self):
        legacy = receipt()
        self.assertEqual(candidate(receipt=legacy)["status"], "DECLARED")
        payload = {k: v for k, v in legacy.items() if k != "receipt_sha256"}
        self.assertEqual(
            canonical_manifest_digest(payload),
            canonical_manifest_digest(payload, ensure_ascii=True),
        )
        self.assertNotEqual(
            canonical_manifest_digest(payload),
            canonical_manifest_digest(payload, ensure_ascii=False),
        ) if any(ord(ch) > 127 for ch in str(payload)) else None
        with self.assertRaisesRegex(ValueError, "ensure_ascii"):
            canonical_manifest_digest(payload, ensure_ascii="False")

    def test_unsupported_profile_and_unicode_tamper_fail_closed(self):
        bad = utf8_vector_receipt()
        bad["canonicalization"] = "UNKNOWN_PROFILE"
        with self.assertRaisesRegex(ValueError, "canonicalization"):
            candidate(receipt=bad)

        bad = utf8_vector_receipt()
        bad["tasks"]["CAFE"]["title"] = "MUTATED"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            candidate(receipt=bad)

        bad = utf8_vector_receipt()
        bad["tasks"]["CAFE"]["title"] = "Caf\u00e9 \U0001f52c/\u2206 altered"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            candidate(receipt=bad)

    def test_utf8_contract_rejects_ambiguous_keys_types_and_unicode(self):
        cases = [
            ("non-ASCII key", "ASCII", lambda r: r.update({"\u00e9": 1})),
            ("float", "unsupported", lambda r: r.update({"unsupported_ratio": 0.5})),
            ("lone surrogate", "lone surrogate",
             lambda r: r["tasks"]["CAFE"].update({"title": "\ud800"})),
        ]
        for label, error, mutate in cases:
            r = utf8_vector_receipt()
            mutate(r)
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, error):
                candidate(receipt=r)



if __name__ == "__main__":
    unittest.main()
