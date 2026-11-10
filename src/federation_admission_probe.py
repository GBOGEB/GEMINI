"""Offline non-authorizing probe for GEMINI federation PR evidence.

No GitHub/Drive network use, tokens, branch writes, review submissions or merge.
Even a structurally complete snapshot is NOT an authenticated admission receipt.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "gmi.federation_admission_observation.v1"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")


class ProbeError(ValueError):
    """A malformed evidence input must fail closed."""


def _map(value):
    return value if isinstance(value, dict) else {}


def _array(value):
    return value if isinstance(value, list) else []


def _sha(value):
    return isinstance(value, str) and bool(SHA40.fullmatch(value))


def _time(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            return None
        return result.astimezone(timezone.utc)
    except ValueError:
        return None


def audit(snapshot):
    """Assess evidence consistency without asserting effective merge authority."""
    if not isinstance(snapshot, dict) or snapshot.get("schema") != SCHEMA:
        raise ProbeError("INVALID_OBSERVATION_SCHEMA")
    if snapshot.get("classification") != "READ_ONLY_UNATTESTED":
        raise ProbeError("UNTRUSTED_CLASSIFICATION")
    source = _map(snapshot.get("source"))
    evidence = _map(snapshot.get("observed"))
    ruleset = _map(snapshot.get("ruleset"))
    reasons = []
    head = source.get("pr_head_sha")
    default = source.get("default_sha")
    source_author = source.get("author")
    author_known = (
        isinstance(source_author, str)
        and bool(source_author)
        and source_author == source_author.strip()
    )
    if not author_known:
        reasons.append("PR_AUTHOR_IDENTITY_UNPROVEN")
    if source.get("repository") != "GBOGEB/GEMINI" or source.get("default_branch") != "main":
        reasons.append("WRONG_SOURCE_OWNER")
    pr_number = source.get("pr_number")
    if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number < 1:
        reasons.append("PR_ID_UNVERIFIED")
    if not _sha(head) or not _sha(default):
        reasons.append("INVALID_SOURCE_SHA")
    if not _sha(evidence.get("head_sha")) or evidence.get("head_sha") != head:
        reasons.append("EXACT_PR_HEAD_MISMATCH")
    if not _sha(evidence.get("default_sha")) or evidence.get("default_sha") != default:
        reasons.append("DEFAULT_REF_DRIFT")

    if ruleset.get("enforcement") != "active" or ruleset.get("target") != "branch":
        reasons.append("RULESET_NOT_ACTIVE")
    conditions = _map(ruleset.get("conditions"))
    ref_names = _map(conditions.get("ref_name"))
    included = _array(ref_names.get("include"))
    # This offline probe does not implement GitHub's ruleset pattern matcher.
    # Any excluded or unreadable scope needs an effective-rule readback first.
    if "~DEFAULT_BRANCH" not in included or ref_names.get("exclude") != []:
        reasons.append("RULESET_SCOPE_UNPROVEN")
    if ruleset.get("bypass_actors") != []:
        reasons.append("BYPASS_POLICY_UNPROVEN")

    rules = [rule for rule in _array(ruleset.get("rules")) if isinstance(rule, dict)]
    pr_rules = [rule for rule in rules if rule.get("type") == "pull_request"]
    ci_rules = [rule for rule in rules if rule.get("type") == "required_status_checks"]
    required_reviews = 0
    if len(pr_rules) != 1:
        reasons.append("EFFECTIVE_PR_REVIEW_RULE_MISSING")
    else:
        params = _map(pr_rules[0].get("parameters"))
        count = params.get("required_approving_review_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 1:
            required_reviews = count
        else:
            reasons.append("INDEPENDENT_REVIEW_NOT_REQUIRED")
        if not all(params.get(key) is True for key in (
            "dismiss_stale_reviews_on_push",
            "require_last_push_approval",
            "required_review_thread_resolution",
        )):
            reasons.append("REVIEW_FRESHNESS_POLICY_WEAK")

    required_contexts = []
    if len(ci_rules) != 1:
        reasons.append("EFFECTIVE_REQUIRED_CI_RULE_MISSING")
    else:
        params = _map(ci_rules[0].get("parameters"))
        entries = _array(params.get("required_status_checks"))
        if params.get("strict_required_status_checks_policy") is not True:
            reasons.append("REQUIRED_CI_SOURCE_FRESHNESS_WEAK")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("context"), str) or not entry["context"]:
                reasons.append("MALFORMED_REQUIRED_CONTEXT")
                continue
            required_contexts.append(entry)
        names = [entry["context"] for entry in required_contexts]
        if not names or len(names) != len(set(names)):
            reasons.append("REQUIRED_CONTEXT_SET_MISSING_OR_DUPLICATE")

    check_runs = [c for c in _array(evidence.get("check_runs")) if isinstance(c, dict)]
    for entry in required_contexts:
        context = entry["context"]
        matches = [c for c in check_runs if c.get("name") == context]
        if len(matches) != 1:
            reasons.append("REQUIRED_CONTEXT_ABSENT_OR_AMBIGUOUS:" + context)
            continue
        check = matches[0]
        if (check.get("head_sha") != head or check.get("status") != "completed"
                or check.get("conclusion") != "success"):
            reasons.append("REQUIRED_CONTEXT_NOT_GREEN_AT_HEAD:" + context)
        steps = check.get("steps_count")
        if not isinstance(steps, int) or isinstance(steps, bool) or steps < 1:
            reasons.append("REQUIRED_CONTEXT_NONZERO_STEPS_UNPROVEN:" + context)
        provider = entry.get("integration_id")
        observed_provider = check.get("integration_id")
        provider_known = isinstance(provider, int) and not isinstance(provider, bool) and provider > 0
        observed_provider_known = (
            isinstance(observed_provider, int)
            and not isinstance(observed_provider, bool)
            and observed_provider > 0
        )
        if not provider_known or not observed_provider_known:
            reasons.append("REQUIRED_CONTEXT_PROVIDER_UNPROVEN:" + context)
        elif provider != observed_provider:
            reasons.append("REQUIRED_CONTEXT_PROVIDER_MISMATCH:" + context)

    last_push = _time(source.get("last_push_at"))
    if last_push is None:
        reasons.append("LAST_PUSH_TIME_UNPROVEN")
    reviewers = set()
    decisions = {}
    for review in _array(evidence.get("reviews")):
        if not isinstance(review, dict):
            reasons.append("REVIEW_DECISION_UNREADABLE")
            continue
        state = review.get("state")
        if not isinstance(state, str) or state not in {
            "APPROVED", "CHANGES_REQUESTED", "DISMISSED", "COMMENTED", "PENDING"
        }:
            reasons.append("REVIEW_DECISION_STATE_UNPROVEN")
            continue
        if state in {"COMMENTED", "PENDING"}:
            continue
        author = review.get("author")
        when = _time(review.get("submitted_at"))
        if not isinstance(author, str) or not author or author != author.strip():
            reasons.append("REVIEWER_IDENTITY_UNPROVEN")
            continue
        if when is None:
            reasons.append("REVIEW_DECISION_TIME_UNPROVEN")
            continue
        decisions.setdefault(author.casefold(), []).append((when, review))
    for author, history in decisions.items():
        latest_time = max(when for when, _ in history)
        latest = [review for when, review in history if when == latest_time]
        signatures = {(review.get("state"), str(review.get("commit_id"))) for review in latest}
        if len(signatures) != 1:
            reasons.append("REVIEW_DECISION_AMBIGUOUS")
            continue
        review = latest[0]
        if review.get("state") == "CHANGES_REQUESTED":
            reasons.append("REVIEW_CHANGES_REQUESTED")
            continue
        if (review.get("state") == "APPROVED" and author_known
                and author != source_author.casefold()
                and review.get("commit_id") == head
                and last_push is not None and latest_time >= last_push):
            reviewers.add(author)
    if required_reviews and len(reviewers) < required_reviews:
        reasons.append("INDEPENDENT_CURRENT_HEAD_APPROVAL_MISSING")
    threads = evidence.get("unresolved_review_threads")
    if not isinstance(threads, int) or isinstance(threads, bool) or threads != 0:
        reasons.append("REVIEW_THREAD_RESOLUTION_UNPROVEN")
    canaries = _map(evidence.get("negative_canaries"))
    if canaries.get("red_required_check_blocked") is not True:
        reasons.append("RED_CANARY_NOT_PROVED")
    if canaries.get("stale_approval_blocked") is not True:
        reasons.append("STALE_REVIEW_CANARY_NOT_PROVED")

    reasons = sorted(set(reasons))
    return {
        "schema": "gmi.federation_admission_probe_receipt.v1",
        "verdict": "HOLD" if reasons else "STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED",
        "reason_codes": reasons,
        "examined_pr_head_sha": head if _sha(head) else None,
        "required_context_count": len(required_contexts),
        "independent_current_head_approvals": len(reviewers),
        "execution_authorized": False,
        "merge_authorized": False,
        "authority_transfer": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline non-authorizing admission probe")
    parser.add_argument("snapshot")
    parser.add_argument("--expect", choices=["hold", "complete"])
    args = parser.parse_args(argv)
    try:
        receipt = audit(json.loads(Path(args.snapshot).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(json.dumps({"verdict": "DENY_INPUT", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if args.expect == "hold":
        return 0 if receipt["verdict"] == "HOLD" else 2
    if args.expect == "complete":
        return 0 if receipt["verdict"] == "STRUCTURAL_EVIDENCE_COMPLETE_UNATTESTED" else 2
    return 0 if receipt["verdict"] != "HOLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
