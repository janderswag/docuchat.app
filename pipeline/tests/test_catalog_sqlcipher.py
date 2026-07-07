"""Encryption cycle (D-73, design §3) — SQLCipher catalog migration + the data-loss
drill the handoff requires BEFORE the real store is touched.

The drill: populate a catalog -> migrate -> prove (a) row-for-row equality across
every table, (b) the original survives untouched as a rename-aside, (c) the new file
is real ciphertext (plain sqlite3 cannot read it; the header is not SQLite's),
(d) the wrong master key fails loud without damaging anything, (e) a failed/aborted
migration leaves the original in place. Master keys are injected — the real
Keychain is never touched here."""

import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import keyvault  # noqa: E402
import migrate_catalog_sqlcipher as mig  # noqa: E402

SQLITE_HEADER = b"SQLite format 3\x00"


def _populate(db):
    """A catalog with every table exercised (the drill payload)."""
    catalog.create_matter("Acme v. Bolt", db_path=db)
    catalog.create_matter("In re Widget", db_path=db)
    native = db.parent / "brief.pdf"
    native.write_bytes(b"%PDF-1.7 synthetic drill native")
    catalog.add_document("acme-v-bolt", native, db_path=db)
    tid = catalog.create_thread("acme-v-bolt", "First questions", db_path=db)["id"]
    catalog.add_message(tid, "user", "what does the brief say?", db_path=db)
    catalog.add_message(tid, "assistant", "the brief says…",
                        citations_json="[]", db_path=db)
    keyvault.ensure_matter_dek("acme-v-bolt", keyvault.new_dek(), db_path=db)


def _dump(conn):
    """Deterministic full-content dump: {table: sorted rows}."""
    tables = sorted(r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"))
    return {t: sorted(map(tuple, conn.execute(f"SELECT * FROM {t}").fetchall()))
            for t in tables}


class TestSqlcipherMigrationDrill(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.db = self.dir / "cat.db"
        _populate(self.db)
        self.master = keyvault.new_dek()
        self.before = _dump(sqlite3.connect(str(self.db)))
        self.assertTrue(self.before["matters"])  # payload sanity

    def test_drill_migrate_verifies_and_preserves_original_aside(self):
        original_bytes = self.db.read_bytes()
        report = mig.migrate(db_path=self.db, master=self.master)
        self.assertTrue(report["verified"])
        # (b) rename-aside original, byte-identical
        aside = Path(report["aside"])
        self.assertTrue(aside.exists())
        self.assertEqual(aside.read_bytes(), original_bytes)
        # (c) the live file is ciphertext now
        self.assertNotEqual(self.db.read_bytes()[:16], SQLITE_HEADER)
        with self.assertRaises(sqlite3.DatabaseError):
            sqlite3.connect(str(self.db)).execute("SELECT * FROM matters").fetchall()
        # (a) row-for-row equality through the normal catalog path
        catalog.MASTER_KEY_PROVIDER = lambda: self.master
        self.addCleanup(setattr, catalog, "MASTER_KEY_PROVIDER", None)
        self.assertEqual(_dump(catalog._connect(self.db)), self.before)

    def test_drill_wrong_master_fails_loud_and_damages_nothing(self):
        mig.migrate(db_path=self.db, master=self.master)
        catalog.MASTER_KEY_PROVIDER = keyvault.new_dek  # wrong key every call
        self.addCleanup(setattr, catalog, "MASTER_KEY_PROVIDER", None)
        with self.assertRaises(Exception):
            _dump(catalog._connect(self.db))
        # right key still works — nothing was corrupted by the failed attempt
        catalog.MASTER_KEY_PROVIDER = lambda: self.master
        self.assertEqual(_dump(catalog._connect(self.db)), self.before)

    def test_drill_rehearse_leaves_source_untouched(self):
        original_bytes = self.db.read_bytes()
        report = mig.migrate(db_path=self.db, master=self.master, rehearse=True)
        self.assertTrue(report["verified"])
        self.assertTrue(report["rehearsal"])
        self.assertEqual(self.db.read_bytes(), original_bytes)  # source untouched
        self.assertEqual(self.db.read_bytes()[:16], SQLITE_HEADER)  # still plain
        self.assertFalse(list(self.dir.glob("*.pre-enc-*")))  # no aside created

    def test_drill_verification_failure_aborts_before_swap(self):
        # sabotage the exported copy so verification MUST fail -> no swap happens
        original_bytes = self.db.read_bytes()
        real_verify = mig._dump_encrypted
        mig._dump_encrypted = lambda *a, **k: {"matters": [("tampered",)]}
        self.addCleanup(setattr, mig, "_dump_encrypted", real_verify)
        with self.assertRaises(mig.MigrationVerificationError):
            mig.migrate(db_path=self.db, master=self.master)
        self.assertEqual(self.db.read_bytes(), original_bytes)  # original untouched
        self.assertFalse(list(self.dir.glob("*.pre-enc-*")))

    def test_migrate_already_encrypted_is_a_noop(self):
        mig.migrate(db_path=self.db, master=self.master)
        report = mig.migrate(db_path=self.db, master=self.master)
        self.assertTrue(report["already_encrypted"])

    def test_fresh_test_path_catalogs_stay_plain(self):
        # tests and non-production paths must keep creating PLAIN sqlite files
        fresh = self.dir / "fresh.db"
        catalog.create_matter("Plain Co", db_path=fresh)
        self.assertEqual(fresh.read_bytes()[:16], SQLITE_HEADER)


if __name__ == "__main__":
    unittest.main()
