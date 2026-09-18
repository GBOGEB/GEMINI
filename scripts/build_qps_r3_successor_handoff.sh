#!/usr/bin/env bash
set -euo pipefail

SOURCE_SHA="${R3_SOURCE_SHA:-1248290ca0a9d55ec83d0efa0235ed1a45a88eeb}"
QPS_CLONE="${1:-}"
OUT_DIR="${2:-./output/r3_successor_handoff}"
BUNDLE_NAME="QPS_R3_1248290c.bundle"
TMP_REF="refs/heads/r3-exact-1248290c"

fail(){ printf 'R3_SUCCESSOR_HANDOFF_FAIL: %s\n' "$*" >&2; exit 2; }

test -n "$QPS_CLONE" || fail "usage: $0 /path/to/genuine/cryoplant-project [out_dir]"
git -C "$QPS_CLONE" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not a genuine git worktree"
git -C "$QPS_CLONE" cat-file -e "$SOURCE_SHA^{commit}" 2>/dev/null || fail "required successor commit is absent"
test -z "$(git -C "$QPS_CLONE" status --porcelain)" || fail "source clone must be clean"

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
BUNDLE="$OUT_DIR/$BUNDLE_NAME"
SIDECAR="$BUNDLE.sha256"
RECEIPT="$OUT_DIR/QPS_R3_1248290c.bundle.receipt.json"

cleanup(){ git -C "$QPS_CLONE" update-ref -d "$TMP_REF" >/dev/null 2>&1 || true; }
trap cleanup EXIT

git -C "$QPS_CLONE" update-ref "$TMP_REF" "$SOURCE_SHA"
git -C "$QPS_CLONE" bundle create "$BUNDLE" "$TMP_REF"
VERIFY="$(git bundle verify "$BUNDLE" 2>&1)"
HEADS="$(git bundle list-heads "$BUNDLE")"
printf '%s\n' "$HEADS" | grep -F "$SOURCE_SHA" >/dev/null || fail "bundle does not advertise required successor commit"

SHA="$(sha256sum "$BUNDLE" | awk '{print $1}')"
BYTES="$(wc -c < "$BUNDLE" | tr -d ' ')"
printf '%s  %s\n' "$SHA" "$BUNDLE_NAME" > "$SIDECAR"

python3 - "$RECEIPT" "$SOURCE_SHA" "$BUNDLE_NAME" "$SHA" "$BYTES" "$HEADS" "$VERIFY" <<'PY'
import json, sys
from pathlib import Path
out, source, name, sha, size, heads, verify = sys.argv[1:]
receipt = {
    "schema": "gmi.r3_successor.git_bundle_receipt.v1",
    "status": "PASS_GENUINE_GIT_BUNDLE_CREATED_AND_VERIFIED",
    "repository": "GBOGEB/cryoplant-project",
    "required_commit": source,
    "bundle_filename": name,
    "bundle_sha256": sha,
    "bundle_bytes": int(size),
    "git_bundle_verify": "PASS",
    "advertised_refs": heads.splitlines(),
    "verify_output": verify.splitlines(),
    "source_clone_required_clean": True,
    "connector_reconstructed_checkout": False,
    "authority_transfer": False,
    "formal_credit_delta": 0,
}
Path(out).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

printf 'R3_SUCCESSOR_GIT_BUNDLE=PASS\n'
printf 'BUNDLE=%s\nSIDECAR=%s\nRECEIPT=%s\n' "$BUNDLE" "$SIDECAR" "$RECEIPT"
