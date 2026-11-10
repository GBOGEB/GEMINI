"""Adversarial proof that source snapshots never issue merge permission."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from src.federation_admission_probe import ProbeError, audit

S = "a" * 40
B = "b" * 40
SAMPLE = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "federation"
    / "admission_observation_20261110.json"
)


def complete_example():
    return {
        "schema": "gmi.federation_admission_observation.v1",
        "classification": "READ_ONLY_UNATTESTED",
        "source": {
            "repository": "GBOGEB/GEMINI",
            "pr_number": 48,
            "default_branch": "main",
            "pr_head_sha": S,
            "default_sha": B,
            "author": "candidate-author",
            "last_push_at": "2026-11-10T17:00:00Z",
        },
        "observed": {
            "head_sha": S,
            "default_sha": B,
            "check_runs": [
                {
                    "name": "always-run-gate",
                    "head_sha": S,
                    "status": "completed",
                    "conclusion": "success",
                    "steps_count": 5,
                    "integration_id": 1234,
                }
            ],
            "reviews": [
                {
                    "author": "distinct-reviewer",
                    "state": "APPROVED",
                    "commit_id": S,
                    "submitted_at": "2026-11-10T18:00:00Z",
                }
            ],
            "unresolved_review_threads": 0,
            "negative_canaries": {
                "red_required_check_blocked": True,
                "stale_approval_blocked": True,
            },
        },
        "ruleset": {
            "enforcement": "active",
            "target": "branch",
            "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            "bypass_actors": [],
            "rules": [
                {
                    "type": "pull_request",
                    "parameters": {
                        "required_approving_review_count": 1,
                        "dismiss_stale_reviews_on_push": True,
                        "require_last_push_approval": True,
                        "required_review_thread_resolution": True,
                    },
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": True,
                        "required_status_checks": [
                            {"context": "always-run-gate", "integration_id": 1234}
                        ],
                    },
                },
            ],
        },
    }


class FederationAdmissionProbeTests(unittest.TestCase):
    def hold(self, alter, reason):
        candidate = complete_example()
        alter(candidate)
        result = audit(candidate)
        self.assertEqual(result["verdict"], "HOLD")
        self.assertIn(reason, result["reason_codes"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["execution_authorized"])

    def test_structural_complete_still_cannot_merge(self):
        result = audit(complete_example())
        self.assertEqual(result["verdict"], "STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED")
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["authority_transfer"])
        self.assertEqual(result["independent_current_head_approvals"], 1)

    def test_actual_ruleset_snapshot_holds(self):
        result = audit(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(result["verdict"], "HOLD")
        self.assertIn("EFFECTIVE_PR_REVIEW_RULE_MISSING", result["reason_codes"])
        self.assertIn("EFFECTIVE_REQUIRED_CI_RULE_MISSING", result["reason_codes"])

    def test_exact_head_mismatch(self):
        self.hold(lambda p: p["observed"].update(head_sha=B), "EXACT_PR_HEAD_MISMATCH")

    def test_base_ref_drift(self):
        self.hold(lambda p: p["observed"].update(default_sha=S), "DEFAULT_REF_DRIFT")

    def test_red_required_check(self):
        self.hold(
            lambda p: p["observed"]["check_runs"][0].update(conclusion="failure"),
            "REQUIRED_CONTEXT_NOT_GREEN_AT_HEAD:always-run-gate",
        )

    def test_skipped_required_check(self):
        self.hold(
            lambda p: p["observed"]["check_runs"][0].update(conclusion="skipped"),
            "REQUIRED_CONTEXT_NOT_GREEN_AT_HEAD:always-run-gate",
        )

    def test_old_head_check(self):
        self.hold(
            lambda p: p["observed"]["check_runs"][0].update(head_sha=B),
            "REQUIRED_CONTEXT_NOT_GREEN_AT_HEAD:always-run-gate",
        )

    def test_zero_executed_steps(self):
        self.hold(
            lambda p: p["observed"]["check_runs"][0].update(steps_count=0),
            "REQUIRED_CONTEXT_NONZERO_STEPS_UNPROVEN:always-run-gate",
        )

    def test_wrong_check_provider(self):
        self.hold(
            lambda p: p["observed"]["check_runs"][0].update(integration_id=9999),
            "REQUIRED_CONTEXT_PROVIDER_MISMATCH:always-run-gate",
        )

    def test_duplicate_context_evidence(self):
        def duplicate(p):
            p["observed"]["check_runs"].append(copy.deepcopy(p["observed"]["check_runs"][0]))

        self.hold(duplicate, "REQUIRED_CONTEXT_ABSENT_OR_AMBIGUOUS:always-run-gate")

    def test_self_approval_denied(self):
        self.hold(
            lambda p: p["observed"]["reviews"][0].update(author="candidate-author"),
            "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING",
        )

    def test_stale_approval_denied(self):
        self.hold(
            lambda p: p["observed"]["reviews"][0].update(
                submitted_at="2026-11-09T16:00:00Z"
            ),
            "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING",
        )

    def test_other_commit_approval_denied(self):
        self.hold(
            lambda p: p["observed"]["reviews"][0].update(commit_id=B),
            "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING",
        )

    def test_no_approval_rule_denied(self):
        self.hold(
            lambda p: p["ruleset"]["rules"][0]["parameters"].update(
                required_approving_review_count=0
            ),
            "INDEPENDENT_REVIEW_NOT_REQUIRED",
        )

    def test_weakened_review_rule_denied(self):
        self.hold(
            lambda p: p["ruleset"]["rules"][0]["parameters"].update(
                require_last_push_approval=False
            ),
            "REVIEW_FRESHNESS_POLICY_WEAK",
        )

    def test_bypass_actor_denied(self):
        self.hold(
            lambda p: p["ruleset"].update(bypass_actors=[{"actor_id": 123}]),
            "BYPASS_POLICY_UNPROVEN",
        )

    def test_missing_red_canary_denied(self):
        self.hold(
            lambda p: p["observed"]["negative_canaries"].update(
                red_required_check_blocked=False
            ),
            "RED_CANARY_NOT_PROVED",
        )

    def test_missing_stale_review_canary_denied(self):
        self.hold(
            lambda p: p["observed"]["negative_canaries"].update(
                stale_approval_blocked=False
            ),
            "STALE_REVIEW_CANARY_NOT_PROVED",
        )

    def test_unresolved_thread_denied(self):
        self.hold(
            lambda p: p["observed"].update(unresolved_review_threads=1),
            "REVIEW_THREAD_RESOLUTION_UNPROVEN",
        )

    def test_malformed_source_denied(self):
        with self.assertRaisesRegex(ProbeError, "INVALID_OBSERVATION_SCHEMA"):
            audit({"schema": "unsupported"})

    def test_bad_last_push_denied(self):
        self.hold(
            lambda p: p["source"].update(last_push_at="invalid"),
            "LAST_PUSH_TIME_UNPROVEN",
        )


if __name__ == "__main__":
    unittest.main()
