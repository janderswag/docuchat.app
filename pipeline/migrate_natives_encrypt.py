"""One-time natives encryption: existing plain files under documents/kb/ become
DEK-encrypted per matter (D-73, design §3).

Verify-before-replace, per file: read the plaintext, check it against the catalog
checksum (integrity gate — a corrupted native must not be silently sealed),
encrypt to a sibling temp name, decrypt-verify byte-for-byte, then atomically
replace. No plaintext aside is kept — unlike the catalog/store migrations, keeping
plaintext copies of client documents would defeat the exercise, and each file is
proven recoverable before its plaintext is replaced. ``--rehearse`` reports what
would change without writing anything.

Usage:
    pipeline/.venv/bin/python pipeline/migrate_natives_encrypt.py --rehearse
    pipeline/.venv/bin/python pipeline/migrate_natives_encrypt.py
"""

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402
import keyvault  # noqa: E402


class NativeVerificationError(RuntimeError):
    """A native failed its integrity or roundtrip check — file left untouched."""


def migrate(kb_docs_root=None, db_path=None, rehearse=False):
    """Encrypt every cataloged plain native under ``kb_docs_root``. Returns a report."""
    import routes_kb
    root = Path(kb_docs_root) if kb_docs_root else routes_kb.KB_DOCS
    report = {"rehearsal": rehearse, "encrypted": [], "already_encrypted": [],
              "missing": [], "skipped_outside_root": []}
    for d in catalog.list_documents(db_path=db_path):
        p = Path(d["stored_path"])
        if not p.is_file():
            report["missing"].append(d["filename"])
            continue
        try:
            p.resolve().relative_to(root.resolve())
        except ValueError:
            report["skipped_outside_root"].append(d["filename"])
            continue
        if keyvault.is_encrypted_file(p):
            report["already_encrypted"].append(d["filename"])
            continue

        plain = p.read_bytes()
        digest = hashlib.sha256(plain).hexdigest()
        if d["checksum"] and digest != d["checksum"]:
            raise NativeVerificationError(
                f"{d['filename']}: on-disk sha256 does not match the catalog — "
                "refusing to encrypt a file that may already be corrupted")
        if rehearse:
            report["encrypted"].append(d["filename"])
            continue

        tmp = p.with_name(p.name + ".enc-migrating")
        keyvault.write_matter_file(tmp, plain, d["matter_slug"], db_path=db_path)
        if not keyvault.is_encrypted_file(tmp) or \
                keyvault.read_matter_file(tmp, d["matter_slug"], db_path=db_path) != plain:
            tmp.unlink(missing_ok=True)
            raise NativeVerificationError(
                f"{d['filename']}: encrypted roundtrip mismatch — original untouched")
        os.replace(tmp, p)  # atomic; plaintext gone only after the proof above
        report["encrypted"].append(d["filename"])

    if not rehearse:  # a rehearsal writes NOTHING, including audit entries
        catalog.audit_append(
            "natives-encrypted",
            detail=f"{len(report['encrypted'])} encrypted, "
                   f"{len(report['already_encrypted'])} already encrypted",
            db_path=db_path)
    return report


if __name__ == "__main__":
    rehearse = "--rehearse" in sys.argv
    r = migrate(rehearse=rehearse)
    mode = "REHEARSAL (nothing written)" if rehearse else "MIGRATED"
    print(f"{mode}: {len(r['encrypted'])} encrypted, "
          f"{len(r['already_encrypted'])} already encrypted, "
          f"{len(r['missing'])} missing, "
          f"{len(r['skipped_outside_root'])} outside documents/kb (untouched)")
