"""Structural Kahn oracle for a declared public architecture fixture.

No job dispatch, credentials, GitHub writes or simulated PASS. Production DAG
scheduling remains owned by pipeline-automation-hub and scoped BridgeFlow assets.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

FILE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "bridge"
    / "federation"
    / "precedence_contract_v1.json"
)


def kahn_layers(nodes):
    """A test-only independent Kahn checker; returns stable ready layers."""
    identities = [node["id"] for node in nodes]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate node ID")
    outgoing = {node_id: [] for node_id in identities}
    degree = {}
    for node in nodes:
        parent_ids = node["predecessors"]
        if len(parent_ids) != len(set(parent_ids)):
            raise ValueError("duplicate predecessor")
        if node["id"] in parent_ids:
            raise ValueError("self dependency")
        for parent_id in parent_ids:
            if parent_id not in outgoing:
                raise ValueError("unknown predecessor")
            outgoing[parent_id].append(node["id"])
        degree[node["id"]] = len(parent_ids)

    layers = []
    ready = sorted(x for x in identities if degree[x] == 0)
    processed = 0
    while ready:
        layers.append(ready)
        processed += len(ready)
        upcoming = []
        for predecessor in ready:
            for successor in outgoing[predecessor]:
                degree[successor] -= 1
                if degree[successor] == 0:
                    upcoming.append(successor)
        ready = sorted(upcoming)
    if processed != len(identities):
        raise ValueError("cycle in declared precedence graph")
    return layers


class FederationPrecedenceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(FILE.read_text(encoding="utf-8"))
        cls.nodes = cls.contract["nodes"]
        cls.by_id = {n["id"]: n for n in cls.nodes}

    def test_structure_matches_documented_kahn_layers(self):
        self.assertEqual(
            kahn_layers(self.nodes),
            self.contract["expected_kahn_layers"],
        )

    def test_disjoint_lanes_are_one_parallel_front_after_validation(self):
        groups = kahn_layers(self.nodes)
        worker_set = {"L_CODEX", "L_ABACUS", "L_MATH", "L_DOCX"}
        self.assertTrue(any(worker_set.issubset(set(layer)) for layer in groups))
        self.assertTrue(
            worker_set.issubset(
                set(self.by_id["J0_JOIN"]["predecessors"])
            )
        )

    def test_auth_review_and_ci_are_distinct_noncompensating_gates(self):
        self.assertEqual(
            set(self.by_id["A0_OWNER_ADMISSION"]["predecessors"]),
            {"Q0_NATIVE_CI", "Q1_INDEPENDENT_REVIEW"},
        )
        self.assertEqual(
            set(self.by_id["Z0_VERSIONED_PUBLICATION"]["predecessors"]),
            {"M0_MERGED_READBACK", "X2_HOSTED_READ", "X3_WRITE_AUTH"},
        )
        self.assertEqual(
            self.by_id["X0_WIF_CONFIG"]["kind"], "external_gate"
        )
        self.assertFalse(self.contract["execution_permission"])
        self.assertFalse(self.contract["authority_transfer"])

    def test_unknown_predecessor_fails_closed(self):
        bad = [dict(n) for n in self.nodes]
        bad[0]["predecessors"] = ["NOT_A_NODE"]
        with self.assertRaisesRegex(ValueError, "unknown predecessor"):
            kahn_layers(bad)

    def test_cycle_fails_closed(self):
        bad = [dict(n) for n in self.nodes]
        bad[0]["predecessors"] = ["Z1_DOWNSTREAM"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            kahn_layers(bad)

    def test_duplicate_or_self_dependency_fails_closed(self):
        bad = [dict(n) for n in self.nodes]
        bad[0]["id"] = bad[1]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate node"):
            kahn_layers(bad)
        bad = [dict(n) for n in self.nodes]
        bad[0]["predecessors"] = ["S0_INTAKE"]
        with self.assertRaisesRegex(ValueError, "self dependency"):
            kahn_layers(bad)


if __name__ == "__main__":
    unittest.main()
