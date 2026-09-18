# GMI evidence binding contract v1

This lane binds **two independent proof classes** without allowing either to
compensate for the other:

1. **Content/package evidence** from the GMI batch validator.
2. **Transport/authentication evidence** from the hosted GM-I-C/IC3 Drive workflow.

The binding is a control receipt, not a new source of engineering truth.

## Exact hosted IC3 predicate

Transport passes only when the supplied IC3 status receipt contains both:

- `result: PASS`
- `classification: IC3_DRIVE_READONLY_GT0_STEP_PASS`

Any missing, failed, or differently classified transport receipt is
`WITHHELD`. A manual ChatGPT/Drive connector read remains separate evidence and
cannot satisfy this predicate.

## Content predicate

Content accepts only when the batch receipt says `ACCEPT` **and** proves a
positive integer package count. This prevents an empty workspace from being
promoted merely because an empty batch is structurally deterministic.

`REJECT`, `DEFER`, malformed batch evidence, and zero/unproven package counts
all withhold combined readiness.

## Combined readiness

`READY_FOR_REVIEW` requires both:

```text
transport_gate == PASS
AND
content_gate == ACCEPT
```

Every other combination is `WITHHELD` with explicit blockers.

## Non-compensation and authority

The adapter never mutates the supplied batch or IC3 receipts, never promotes
source-agent evidence state, and always emits:

- `non_compensation: true`
- `source_claims_promoted: false`
- `authority_transfer: false`
- `formal_credit_delta: 0`

Therefore a package/batch ACCEPT does not burn IC3, an IC3 PASS does not validate
semantic source claims, and `READY_FOR_REVIEW` is not QPS engineering acceptance,
runtime GOLD, release authority, or formal credit.
