#!/usr/bin/env python3
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REQ = {
    "PyYAML": "6.0.1",
    "openpyxl": "3.1.5",
    "python-docx": "1.2.0",
    "python-pptx": "1.0.2",
    "reportlab": "5.0.1",
    "pypdf": "6.0.0",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def fail(msg: str) -> None:
    raise SystemExit(f"R3_EXACT_ENV_CAPSULE_FAIL: {msg}")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--archive")
    args = ap.parse_args()

    root = Path(args.runtime_root)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    py = root / "run-python"
    if not py.is_file():
        fail("runtime relocation-safe run-python launcher missing")

    probe = subprocess.run(
        [str(py), "-c",
         "import json,platform,sys,importlib.metadata as m;"
         "req={'PyYAML':'6.0.1','openpyxl':'3.1.5','python-docx':'1.2.0','python-pptx':'1.0.2','reportlab':'5.0.1','pypdf':'6.0.0'};"
         "print(json.dumps({'python':platform.python_version(),'major_minor':f'{sys.version_info.major}.{sys.version_info.minor}','versions':{k:m.version(k) for k in req}},sort_keys=True))"],
        text=True, capture_output=True
    )
    if probe.returncode:
        fail(probe.stderr.strip() or "runtime probe failed")
    observed = json.loads(probe.stdout)
    if observed["major_minor"] != "3.12":
        fail(f"python family mismatch: {observed['python']}")
    if observed["versions"] != REQ:
        fail(f"dependency lock mismatch: {observed['versions']}")

    if manifest.get("schema") != "gmi.r3_successor.exact_env_capsule.v2":
        fail("manifest schema mismatch")
    if manifest.get("python_family") != "3.12":
        fail("manifest python family mismatch")
    if manifest.get("exact_dependencies") != REQ:
        fail("manifest dependency contract mismatch")
    if manifest.get("relocated_self_test") != "PASS_CLEAN_LD_LIBRARY_PATH":
        fail("manifest does not bind relocated self-test PASS")

    if args.archive:
        archive = Path(args.archive)
        if sha256(archive) != manifest.get("archive_sha256"):
            fail("archive sha256 mismatch")

    print(json.dumps({
        "status": "PASS_EXACT_ENV_CAPSULE",
        "python": observed["python"],
        "exact_dependencies": observed["versions"],
        "archive_sha256_verified": bool(args.archive),
        "authority_transfer": False,
        "formal_credit_delta": 0,
    }, sort_keys=True))

if __name__ == "__main__":
    main()
