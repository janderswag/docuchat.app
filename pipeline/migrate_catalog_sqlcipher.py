"""One-time catalog migration: plain SQLite -> SQLCipher keyed by the Keychain
master key (encryption cycle, D-73, design §3).

Mirrors reingest_kb.py's rename-aside pattern: the encrypted copy is built and
VERIFIED row-for-row next to the original; only then is the original renamed aside
(``.kb_catalog.pre-enc-<ts>.db`` — matches the existing gitignore, never deleted)
and the encrypted file moved into place. Any failure before the swap leaves the
original byte-identical. ``--rehearse`` runs the whole thing against a scratch COPY
and touches nothing (the handoff requires a rehearsal before the real store).

Usage:
    pipeline/.venv/bin/python pipeline/migrate_catalog_sqlcipher.py --rehearse
    pipeline/.venv/bin/python pipeline/migrate_catalog_sqlcipher.py
"""

import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog  # noqa: E402


class MigrationVerificationError(RuntimeError):
    """The encrypted copy did not match the original — migration aborted pre-swap."""


def _dump_plain(path):
    conn = sqlite3.connect(str(path))
    try:
        return _dump(conn)
    finally:
        conn.close()


def _dump_encrypted(path, master):
    conn = sqlcipher.connect(str(path))
    try:
        conn.execute(f"PRAGMA key = \"x'{master.hex()}'\"")
        return _dump(conn)
    finally:
        conn.close()


def _dump(conn):
    tables = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"))
    return {t: sorted(map(tuple, conn.execute(f"SELECT * FROM {t}").fetchall()))
            for t in tables}


def _export_encrypted(src, dst, master):
    """SQLCipher's own export: open the PLAIN db, attach dst with a key, copy all."""
    conn = sqlcipher.connect(str(src))
    try:
        conn.execute("ATTACH DATABASE ? AS encrypted KEY \"x'%s'\"" % master.hex(),
                     (str(dst),))
        conn.execute("SELECT sqlcipher_export('encrypted')")
        conn.execute("DETACH DATABASE encrypted")
    finally:
        conn.close()


def migrate(db_path=None, master=None, rehearse=False):
    """Migrate one catalog file. Returns a report dict; raises before any swap on
    verification failure. ``rehearse=True`` = run on a scratch copy, touch nothing."""
    src = Path(db_path) if db_path else catalog.DEFAULT_DB
    if not src.exists():
        raise FileNotFoundError(f"catalog not found: {src}")
    if catalog.is_encrypted(src):
        return {"already_encrypted": True, "path": str(src)}
    if master is None:
        import keyvault
        master = keyvault.master_key()

    report = {"already_encrypted": False, "rehearsal": rehearse, "path": str(src)}
    scratch = None
    try:
        if rehearse:
            scratch = Path(tempfile.mkdtemp(prefix="catalog-rehearse-"))
            work_src = scratch / src.name
            shutil.copy2(src, work_src)
        else:
            work_src = src

        tmp = work_src.with_name(work_src.name + ".enc-migrating")
        tmp.unlink(missing_ok=True)
        _export_encrypted(work_src, tmp, master)

        before = _dump_plain(work_src)
        after = _dump_encrypted(tmp, master)
        if before != after or catalog.is_encrypted(tmp) is False:
            tmp.unlink(missing_ok=True)
            raise MigrationVerificationError(
                "encrypted copy does not match the original; nothing was swapped")
        report["verified"] = True
        report["tables"] = {t: len(rows) for t, rows in after.items()}

        if rehearse:
            return report

        aside = src.with_name(
            f".kb_catalog.pre-enc-{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
            if src.name.startswith(".kb_catalog") else src.name + ".pre-enc.db")
        src.rename(aside)
        tmp.rename(src)
        report["aside"] = str(aside)
        return report
    finally:
        if scratch is not None:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    rehearse = "--rehearse" in sys.argv
    r = migrate(rehearse=rehearse)
    if r.get("already_encrypted"):
        print(f"{r['path']} is already encrypted — nothing to do")
    else:
        mode = "REHEARSAL (source untouched)" if rehearse else "MIGRATED"
        print(f"{mode}: {r['path']} verified={r['verified']} tables={r['tables']}")
        if "aside" in r:
            print(f"original kept aside -> {r['aside']} (delete manually once verified)")
