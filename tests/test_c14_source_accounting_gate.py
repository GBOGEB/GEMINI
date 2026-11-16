"""Fail-closed public metadata contract; no private source data are included."""
import json
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parents[1] / "config" / "federation" / "c14_source_accounting_gate.v1.json"

class C14SourceAccountingGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(DOC.read_text(encoding="utf-8"))

    def test_declared_partition_not_identity_proof(self):
        c = self.data["counts"]
        self.assertEqual(c["sidebar_rows_declared"] - c["boundary_overlaps_declared"], c["unique_chats_declared"])
        self.assertEqual(c["safe_candidates_declared"] + c["verify_local_declared"] + c["keep_or_hold_declared"], c["unique_chats_declared"])
        self.assertEqual(c["independently_verified_chat_ids"], 0)
        self.assertEqual(c["deletion_eligible"], 0)

    def test_actual_byte_boundary(self):
        f = self.data["file_fidelity"]
        self.assertEqual(f["raw_source_bytes_locally_hashed"], 3)
        self.assertEqual(f["google_doc_text_exports_hashed"], 2)
        self.assertFalse(f["original_html_and_txt_byte_equivalence_proven"])

    def test_authority_locks(self):
        self.assertTrue(all(v is False for v in self.data["governance"].values()))
        self.assertIn("HOLD", self.data["disposition"])

    def test_public_safe_metadata_only(self):
        raw = DOC.read_text(encoding="utf-8")
        for bad in ("drive.google.com/file/d/", "docs.google.com/document/d/", "ALX/", "MIN-", "chat_id_original"):
            self.assertNotIn(bad, raw)
        self.assertNotIn("source_contents", self.data)

if __name__ == "__main__":
    unittest.main()
