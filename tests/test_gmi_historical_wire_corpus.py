"""Cross-format W2 corpus: preserve historical #41 shape, accept only #40 wire.

Source provenance: GBOGEB/GEMINI merged PR #41 (e8481490...) versus
canonical merged PR #40 (d875206a...). These fixtures are *representative*
synthetic inputs, not a copy of a real signed owner package or hosted evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from src.handover_package import canonical_manifest_digest
from src.proposal_broker import PROFILE, BrokerError, parse_profile

CORPUS = Path(__file__).resolve().parent / 'fixtures' / 'gmi_wire'
CONTENTS = b'safe bounded replacement\n'


def _manifest(name: str) -> dict:
    return json.loads((CORPUS / name).read_text(encoding='utf-8'))


def _package(tmp_path: Path, manifest: dict) -> Path:
    p = tmp_path / 'GMI-HISTORICAL-CROSSWALK'
    p.mkdir()
    (p / 'ARTIFACTS').mkdir()
    (p / 'ARTIFACTS' / 'replacement.txt').write_bytes(CONTENTS)
    return p


def test_corpus_provenance_is_explicit_not_owner_attestation():
    meta = _manifest('SOURCE_RECEIPT.json')
    assert meta['authority_transfer'] is False
    assert meta['historical_wire']['pr'] == 41
    assert meta['canonical_wire']['pr'] == 40
    assert meta['synthetic_fixtures'] is True
    assert 'W3' not in meta['claims']


def test_historical_41_wire_is_rejected_prior_to_artifact_read(tmp_path):
    manifest = _manifest('historical_41.json')
    # No artifacts are created; legacy marker must reject first.
    with pytest.raises(BrokerError) as exc:
        parse_profile(manifest, tmp_path / 'absent-package')
    assert exc.value.code == 'AMBIGUOUS_LEGACY_PROFILE'


def test_mixed_dual_marker_is_always_rejected(tmp_path):
    current = _manifest('canonical_40.json')
    old = _manifest('historical_41.json')
    current['proposal_profile'] = old['proposal_profile']
    with pytest.raises(BrokerError) as exc:
        parse_profile(current, tmp_path / 'absent-package')
    assert exc.value.code == 'AMBIGUOUS_LEGACY_PROFILE'


def test_canonical_40_profile_parses_real_local_artifact(tmp_path):
    manifest = _manifest('canonical_40.json')
    assert manifest['profile'] == PROFILE
    folder = _package(tmp_path, manifest)
    parsed = parse_profile(manifest, folder)
    assert parsed['changes'][0]['artifact'] == CONTENTS
    assert parsed['changes'][0]['path'] == 'docs/example.txt'
    assert parsed['repo'] == 'GBOGEB/GEMINI'


def test_manifest_digest_is_order_stable_and_cross_wire_distinct():
    canonical = _manifest('canonical_40.json')
    historical = _manifest('historical_41.json')
    assert canonical_manifest_digest(canonical) != canonical_manifest_digest(historical)
    reordered = dict(reversed(list(canonical.items())))
    assert canonical_manifest_digest(canonical) == canonical_manifest_digest(reordered)


def test_changed_session_digest_is_observable_but_not_owner_permission():
    canonical = _manifest('canonical_40.json')
    changed = copy.deepcopy(canonical)
    changed['proposal']['intent'] = 'A separately edited proposal for the same session'
    assert canonical['session_id'] == changed['session_id']
    assert canonical_manifest_digest(canonical) != canonical_manifest_digest(changed)
    assert _manifest('SOURCE_RECEIPT.json')['changed_replay_owner_decision'] == 'PENDING'


def test_fixture_artifact_sha_is_explicit_not_git_oid():
    canonical = _manifest('canonical_40.json')
    a = canonical['artifact_refs'][0]
    assert a['sha256'] == hashlib.sha256(CONTENTS).hexdigest()
    assert len(a['sha256']) == 64
    assert len(canonical['proposal']['changes'][0]['base_blob']) == 40