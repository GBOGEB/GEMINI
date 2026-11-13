"""Structure guard for the root landing page (shared skeleton R2).

Checks the fixed part order, the personal "At a glance" slots, a single
snapshot SHA, and that every relative link and in-page anchor resolves.
See docs/landing/LANDING_SKELETON.md. Stdlib only; runs on Python 3.9.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SKELETON = ROOT / "docs" / "landing" / "LANDING_SKELETON.md"

PARTS = ["At a glance"] + [f"{n}. " for n in range(1, 10)]
SLOTS = [
    "Domain",
    "EPICs carried here",
    "Owner and decision authority",
    "Role in the federation",
    "Owns",
    "Does not own",
    "Status snapshot",
]
LINK = re.compile(r"\]\(([^)\s]+)\)")
SNAPSHOT = re.compile(r"main@([0-9a-f]{7,40})")


def _prose(text):
    """Drop fenced code blocks so Mermaid labels are not read as links."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _h2(text):
    return [line[3:].strip() for line in _prose(text).splitlines() if line.startswith("## ")]


def _slug(heading):
    slug = heading.strip().lower()
    slug = re.sub(r"[^\w\- ]", "", slug)
    return slug.replace(" ", "-")


def _anchors(text):
    return {
        _slug(line.lstrip("#"))
        for line in _prose(text).splitlines()
        if re.match(r"#{1,6} ", line)
    }


@pytest.fixture(scope="module")
def readme():
    return README.read_text(encoding="utf-8")


def test_parts_present_once_and_in_order(readme):
    headings = _h2(readme)
    positions = []
    for part in PARTS:
        hits = [i for i, h in enumerate(headings) if h.startswith(part)]
        assert len(hits) == 1, f"landing part {part!r} found {len(hits)} times"
        positions.append(hits[0])
    assert positions == sorted(positions), f"landing parts out of order: {headings!r}"


def test_at_a_glance_slots_filled(readme):
    for slot in SLOTS:
        pattern = r"^\| \*\*" + re.escape(slot) + r"\*\* \| (.+?) \|$"
        row = re.search(pattern, readme, flags=re.MULTILINE)
        assert row, f"At-a-glance slot {slot!r} missing"
        assert row.group(1).strip(), f"At-a-glance slot {slot!r} is empty"


def test_one_snapshot_sha(readme):
    shas = set(SNAPSHOT.findall(readme))
    assert len(shas) == 1, f"landing cites more than one main SHA: {sorted(shas)!r}"


@pytest.mark.parametrize("page", [README, SKELETON], ids=lambda p: p.name)
def test_relative_links_resolve(page):
    text = page.read_text(encoding="utf-8")
    anchors = _anchors(text)
    broken = []
    for target in LINK.findall(_prose(text)):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue
        path, _, fragment = target.partition("#")
        if not path:
            if fragment not in anchors:
                broken.append(target)
            continue
        if not (page.parent / path).exists():
            broken.append(target)
    assert not broken, f"{page.name} has unresolved links: {broken!r}"


def test_slug_matches_github_rule():
    assert _slug("1. Why GEMINI exists — BIOS") == "1-why-gemini-exists--bios"
    assert _slug("5. Process diagrams — flow, SIPOC, Kahn") == "5-process-diagrams--flow-sipoc-kahn"
