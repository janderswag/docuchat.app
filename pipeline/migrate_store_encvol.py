"""One-time KB store migration onto the encrypted volume (D-73, design §3).

Rename-aside, verified-before-swap, mirroring migrate_catalog_sqlcipher.py:
build the encrypted bundle, copy the store in, VERIFY row-for-row through
LanceDB, and only then rename the plain store aside (``.lancedb_kb.pre-encvol-
<ts>`` — never deleted) and mount the volume at the store path. ``--rehearse``
does everything against a scratch copy and touches nothing.

After the real migration the app's startup hook mounts the volume automatically;
the aside plaintext store should be deleted manually once the owner has verified
a few real queries (same manual-delete contract as reingest_kb.py).

Usage:
    pipeline/.venv/bin/python pipeline/migrate_store_encvol.py --rehearse
    pipeline/.venv/bin/python pipeline/migrate_store_encvol.py
"""

import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import lancedb

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_protection  # noqa: E402
import encvol  # noqa: E402

PIPELINE_DIR = Path(__file__).resolve().parent
KB_DB = PIPELINE_DIR / ".lancedb_kb"


class StoreVerificationError(RuntimeError):
    """The store copy inside the volume did not match — nothing was swapped."""


def _dump_store(db_path):
    """Deterministic content dump of every table: {name: (count, sorted row keys)}."""
    db = lancedb.connect(str(db_path))
    out = {}
    for name in db.table_names():
        t = db.open_table(name)
        rows = t.search().select(["source_filename", "matter", "page_number",
                                  "char_start", "char_end"]).limit(1_000_000).to_arrow().to_pylist()
        key = sorted((r["source_filename"], r["matter"], r["page_number"],
                      r["char_start"], r["char_end"]) for r in rows)
        out[name] = (t.count_rows(), key)
    return out


def migrate(store_dir=None, bundle=None, passphrase=None, rehearse=False):
    """Migrate one store directory into an encrypted volume. Returns a report dict."""
    store = Path(store_dir) if store_dir else KB_DB
    bundle = Path(bundle) if bundle else encvol.KB_BUNDLE
    if not store.is_dir():
        raise FileNotFoundError(f"KB store not found: {store}")
    if encvol.is_mounted(store) or bundle.exists():
        return {"already_migrated": True, "mounted": encvol.is_mounted(store)}
    passphrase = passphrase or encvol.volume_passphrase()

    report = {"already_migrated": False, "rehearsal": rehearse, "store": str(store)}
    before = _dump_store(store)

    scratch = Path(tempfile.mkdtemp(prefix="encvol-migrate-"))
    work_bundle = scratch / "kb.sparsebundle" if rehearse else bundle
    mnt = scratch / "mnt"
    try:
        encvol.create_volume(work_bundle, passphrase)
        encvol.mount(work_bundle, mnt, passphrase)
        for child in store.iterdir():
            if child.is_dir():
                shutil.copytree(child, mnt / child.name)
            else:
                shutil.copy2(child, mnt / child.name)
        after = _dump_store(mnt)
        if before != after:
            raise StoreVerificationError(
                "volume store does not match the original; nothing was swapped")
        report["verified"] = True
        report["tables"] = {n: c for n, (c, _) in after.items()}
        encvol.eject(mnt)

        if rehearse:
            return report  # scratch (bundle + mount dir) removed below

        aside = store.with_name(
            store.name + ".pre-encvol-" + datetime.now().strftime("%Y%m%d%H%M%S"))
        store.rename(aside)
        report["aside"] = str(aside)
        store.mkdir()
        encvol.mount(bundle, store, passphrase)
        final = _dump_store(store)
        if final != before:
            # roll back: eject, remove empty mountpoint, restore the aside
            encvol.eject(store)
            store.rmdir()
            aside.rename(store)
            raise StoreVerificationError("post-swap verification failed; store restored")
        # keep the bundle (and the plaintext aside, until manual delete) out of backups
        report["protection"] = data_protection.protect_paths({"kb volume": bundle})
        return report
    except Exception:
        if not rehearse and bundle.exists() and not encvol.is_mounted(store):
            # a failed real run must not leave a half-built bundle claiming migration
            encvol.eject(mnt)
            shutil.rmtree(bundle, ignore_errors=True)
        raise
    finally:
        encvol.eject(mnt)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    rehearse = "--rehearse" in sys.argv
    r = migrate(rehearse=rehearse)
    if r.get("already_migrated"):
        print(f"store already on the encrypted volume (mounted={r['mounted']})")
    else:
        mode = "REHEARSAL (nothing touched)" if rehearse else "MIGRATED + MOUNTED"
        print(f"{mode}: verified={r['verified']} tables={r['tables']}")
        if "aside" in r:
            print(f"plain store kept aside -> {r['aside']}")
            print("delete it manually once you have verified real queries "
                  "(it is plaintext; until deleted, at-rest encryption is not complete)")
