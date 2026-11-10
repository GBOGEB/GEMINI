# F03 visual review and Google Drive readback receipt

**Date:** 2026-11-10. **Authority:** generated view and source-integrity evidence only.
**Repository source:** GEMINI main cf72ec33ff85017c997d51bc563e5708453212a1.
**Existing Drive worktree:** [F03 review folder](https://drive.google.com/drive/folders/1F6tq6QeM4EMfHrCtd1NbkoS_2lV27YTA).

## Five source identities

| Mermaid source | Exact Git blob object ID | Rendered graph census |
|---|---|---|
| topology.mmd | 0d32e106da6c370da230a1da745e97e77e2e8b4f | 11 nodes / 12 edges |
| sipoc.mmd | 4a8a032870cb5930cf8ef366d331d7a3aa7361b2 | 5 nodes / 4 edges |
| kahn-lanes.mmd | 002cbc0e90b7f073c46073bbf653c749b29db0f4 | 11 nodes / 13 edges |
| roundtrip-sequence.mmd | 84182ff2e291fbf35ef55fc213aa1ae1b45ae4db | 12 event nodes / 11 ladder edges |
| admission-state.mmd | 15d22501e4796b4a071bea920309508e8de01d13 | 16 nodes / 15 edges |

All five local source files reproduced these Git object IDs with git hash-object. Sources are [editable .mmd files](README.md); [GitHub Mermaid preview](rendered.md) is derived from the same exact source content.

## Generated assets and readback

- [Six-page A3 landscape vector PDF](https://drive.google.com/file/d/1iEf_bKerKzXgsBw1kXtx9JQltH_VzN3c/view?usp=drivesdk).
- [Offline HTML with five inline SVGs and collapsible Mermaid source](https://drive.google.com/file/d/1SJm1UH72SIBMdTd5yx-vHPFy3KvgVJJO/view?usp=drivesdk).
- [Complete source/renderer/receipt ZIP](https://drive.google.com/file/d/1uOQl6ev5vrJT5Ib3h28RpFdQCts8n6W2/view?usp=drivesdk).
- [Local QA receipt](https://drive.google.com/file/d/1tNCJiIOAK5xD3R2FcI_TaTmeat-0ExIg/view?usp=drivesdk).
- ZIP SHA-256: 223e9e0821e53ee32bbe69ff5de291789f74f5558893136bf69fc39408f70d6a.
- A new Drive folder was created **inside** the existing ARGON generic BridgeFlow artifacts subtree; no duplicate portable worktree.
- Uploaded ZIP was read back from Google Drive and compared against the original: **exact byte equality**, same SHA-256 and size (233,515 bytes), 21 ZIP entries, CRC test successful.

## K-series execution and limits

| Check | Outcome |
|---|---|
| K01 source Git blob identity | PASS 5/5 |
| K02 Graphviz semantic fallback graph node/edge parser | PASS 5/5 structural |
| K03 SVG XML parsing | PASS 5/5 |
| K04 PDF page and vector checks | PASS 6 pages, no raster images |
| K05 PDF visual review (rendered PNG montage) | PASS after correcting overly wide layouts |
| K06 HTML static rendering via Playwright | PASS, 5 SVGs and 5 sections, zero page errors |
| K07 Offline file:// browser navigation | BLOCKED by administrator; Playwright set_content fallback used |
| K08 Native pinned Mermaid CLI parity | NOT RUN, CLI unavailable in generation environment |
| K09 Drive ZIP bytes readback | PASS exact SHA-256 |
| K10 Hosted Google WIF, GitHub App and PR admission | INDEPENDENT OWNER HOLD |

**Renderer notice:** SVG/PDF uses a disclosed Graphviz **semantic adapter** of the pinned Mermaid sources, not official Mermaid CLI layout. In particular the round-trip sequence appears as an event ladder rather than UML lifelines. A future pinned native Mermaid render remains a distinct DOV requirement; do not mark it satisfied from static fidelity checks.

**Policy:** The artifact is a human-readable view, not a second SSOT, approval, runtime CI, authenticated Drive publisher, branch protection or engineering acceptance. Retain source and QA snapshots unmodified across future recursive pulses.
