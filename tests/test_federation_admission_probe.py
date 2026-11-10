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

    def test_excluded_or_unreadable_default_scope_holds(self):
        for exclusion in (["refs/heads/main"], ["~DEFAULT_BRANCH"],
                          ["refs/heads/*"], ["refs/heads/other"], None, "", {}):
            with self.subTest(exclusion=exclusion):
                self.hold(
                    lambda p, exclusion=exclusion: p["ruleset"]["conditions"]["ref_name"].update(exclude=exclusion),
                    "RULESET_SCOPE_UNPROVEN",
                )
        self.hold(
            lambda p: p["ruleset"]["conditions"]["ref_name"].pop("exclude"),
            "RULESET_SCOPE_UNPROVEN",
        )

    def test_required_provider_must_be_explicit_positive_integer(self):
        for provider in (None, 0, -1, True, "1234"):
            with self.subTest(provider=provider):
                self.hold(
                    lambda p, provider=provider: p["ruleset"]["rules"][1]["parameters"]
                    ["required_status_checks"][0].update(integration_id=provider),
                    "REQUIRED_CONTEXT_PROVIDER_UNPROVEN:always-run-gate",
                )
        self.hold(
            lambda p: p["ruleset"]["rules"][1]["parameters"]
            ["required_status_checks"][0].pop("integration_id"),
            "REQUIRED_CONTEXT_PROVIDER_UNPROVEN:always-run-gate",
        )

    def test_observed_provider_must_be_explicit_positive_integer(self):
        for provider in (None, 0, -1, True, "1234"):
            with self.subTest(provider=provider):
                self.hold(
                    lambda p, provider=provider: p["observed"]["check_runs"][0].update(integration_id=provider),
                    "REQUIRED_CONTEXT_PROVIDER_UNPROVEN:always-run-gate",
                )
        self.hold(
            lambda p: p["observed"]["check_runs"][0].pop("integration_id"),
            "REQUIRED_CONTEXT_PROVIDER_UNPROVEN:always-run-gate",
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

    def test_unknown_candidate_author_cannot_prove_independence(self):
        for author in (None, "", " ", "candidate-author ", [], {}):
            with self.subTest(author=author):
                self.hold(
                    lambda p, author=author: p["source"].update(author=author),
                    "PR_AUTHOR_IDENTITY_UNPROVEN",
                )
        self.hold(lambda p: p["source"].pop("author"), "PR_AUTHOR_IDENTITY_UNPROVEN")

    def test_case_variant_author_is_still_self_approval(self):
        self.hold(
            lambda p: p["observed"]["reviews"][0].update(author="CANDIDATE-AUTHOR"),
            "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING",
        )

    def test_case_variant_reviewers_count_once(self):
        def duplicate_identity(p):
            p["ruleset"]["rules"][0]["parameters"]["required_approving_review_count"] = 2
            other = copy.deepcopy(p["observed"]["reviews"][0])
            other["author"] = "DISTINCT-REVIEWER"
            p["observed"]["reviews"].append(other)

        self.hold(duplicate_identity, "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING")

    def test_blank_or_padded_reviewer_cannot_approve(self):
        for author in (" ", "distinct-reviewer "):
            with self.subTest(author=author):
                self.hold(
                    lambda p, author=author: p["observed"]["reviews"][0].update(author=author),
                    "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING",
                )

    def test_later_changes_requested_revokes_approval(self):
        def revoke(p):
            review = dict(p["observed"]["reviews"][0], author="DISTINCT-REVIEWER",
                          state="CHANGES_REQUESTED", submitted_at="2026-11-10T19:00:00Z")
            p["observed"]["reviews"].append(review)

        self.hold(revoke, "REVIEW_CHANGES_REQUESTED")

    def test_latest_approval_is_order_independent(self):
        candidate = complete_example()
        earlier = dict(candidate["observed"]["reviews"][0], state="CHANGES_REQUESTED",
                       submitted_at="2026-11-10T17:30:00Z")
        for history in ([earlier, candidate["observed"]["reviews"][0]],
                        [candidate["observed"]["reviews"][0], earlier]):
            with self.subTest(history=history):
                snapshot = copy.deepcopy(candidate)
                snapshot["observed"]["reviews"] = history
                result = audit(snapshot)
                self.assertEqual(result["verdict"], "STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED")
                self.assertEqual(result["independent_current_head_approvals"], 1)
                self.assertFalse(result["merge_authorized"])

    def test_later_dismissal_revokes_approval(self):
        def dismiss(p):
            review = dict(p["observed"]["reviews"][0], state="DISMISSED",
                          submitted_at="2026-11-10T19:00:00Z")
            p["observed"]["reviews"].append(review)

        self.hold(dismiss, "INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING")

    def test_conflicting_same_time_decisions_hold(self):
        def conflict(p):
            p["observed"]["reviews"].append(
                dict(p["observed"]["reviews"][0], state="CHANGES_REQUESTED")
            )

        self.hold(conflict, "REVIEW_DECISION_AMBIGUOUS")

    def test_unknown_decision_time_cannot_preserve_earlier_approval(self):
        def unknown(p):
            p["observed"]["reviews"].append(
                dict(p["observed"]["reviews"][0], state="CHANGES_REQUESTED", submitted_at=None)
            )

        self.hold(unknown, "REVIEW_DECISION_TIME_UNPROVEN")

    def test_other_reviewers_change_request_is_not_compensated(self):
        def outstanding(p):
            p["observed"]["reviews"].append(
                dict(p["observed"]["reviews"][0], author="another-reviewer", state="CHANGES_REQUESTED")
            )

        self.hold(outstanding, "REVIEW_CHANGES_REQUESTED")

    def test_invalid_later_state_holds_without_type_error(self):
        for state in ([], {}, None, "UNKNOWN", 1):
            with self.subTest(state=state):
                self.hold(
                    lambda p, state=state: p["observed"]["reviews"].append(
                        dict(p["observed"]["reviews"][0], state=state)
                    ),
                    "REVIEW_DECISION_STATE_UNPROVEN",
                )

    def test_unreadable_review_cannot_preserve_complete_verdict(self):
        for review in ([], None, "APPROVED", 1):
            with self.subTest(review=review):
                self.hold(
                    lambda p, review=review: p["observed"]["reviews"].append(review),
                    "REVIEW_DECISION_UNREADABLE",
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
