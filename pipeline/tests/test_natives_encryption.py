"""Encryption cycle (D-73) — natives at rest: uploads land DEK-encrypted, every
read surface (source, thumbnails, ingest, export) sees plaintext, and existing
plain natives migrate in place with verify-before-replace. Encryption is FORCED on
with an injected master key (never the Keychain); the ingest test runs the real
worker + live loopback Ollama end-to-end like the other KB tests. Temp stores only."""

import hashlib
import io
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import fitz
from fastapi.testclient import TestClient

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import catalog  # noqa: E402
import keyvault  # noqa: E402
import migrate_natives_encrypt as mig  # noqa: E402
import retention  # noqa: E402
import routes_kb  # noqa: E402
import api  # noqa: E402

client = TestClient(api.app)

MAGIC = keyvault.MAGIC


def _pdf_bytes(text):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    return doc.tobytes()


class _EncryptedBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._cat, catalog.DEFAULT_DB = catalog.DEFAULT_DB, self.tmp / "cat.db"
        self._db, routes_kb.KB_DB = routes_kb.KB_DB, self.tmp / ".lancedb_kb"
        self._docs, routes_kb.KB_DOCS = routes_kb.KB_DOCS, self.tmp / "kb"
        self._master = keyvault.new_dek()
        catalog.MASTER_KEY_PROVIDER = lambda: self._master
        keyvault.NATIVES_ENCRYPTION = True
        self.m = catalog.create_matter("Sealed Matter")
        self.slug = self.m["slug"]

    def tearDown(self):
        catalog.DEFAULT_DB = self._cat
        routes_kb.KB_DB = self._db
        routes_kb.KB_DOCS = self._docs
        catalog.MASTER_KEY_PROVIDER = None
        keyvault.NATIVES_ENCRYPTION = None

    def _upload(self, name, content):
        return client.post(f"/kb/upload?matter={self.slug}&filename={name}", content=content)

    def _wait_terminal(self, doc_id, timeout=90):
        deadline = time.time() + timeout
        while time.time() < deadline:
            row = catalog.get_document(doc_id)
            if row and row["status"] in ("ready", "needs_review", "failed"):
                return row["status"]
            time.sleep(0.2)
        return None


class TestEncryptedUploadAndViews(_EncryptedBase):
    def test_upload_is_ciphertext_on_disk_with_plaintext_manifest(self):
        body = b"SYNTHETIC. The consulting fee is $5,000."
        r = self._upload("memo.txt", body)
        self.assertEqual(r.status_code, 200, r.text)
        doc = r.json()
        stored = Path(doc["stored_path"])
        self.assertTrue(stored.read_bytes().startswith(MAGIC))       # sealed on disk
        self.assertNotIn(b"consulting fee", stored.read_bytes())
        self.assertEqual(doc["checksum"], hashlib.sha256(body).hexdigest())  # plaintext hash
        self.assertEqual(doc["size_bytes"], len(body))
        # /kb/source serves the decrypted native
        src = client.get(f"/kb/source/{doc['id']}")
        self.assertEqual(src.status_code, 200)
        self.assertEqual(src.content, body)

    def test_reupload_same_content_dedupes_against_plaintext(self):
        body = b"SYNTHETIC dedup probe content."
        p1 = self._upload("dup.txt", body).json()["stored_path"]
        p2 = self._upload("dup.txt", body).json()["stored_path"]
        self.assertEqual(p1, p2)  # same plaintext -> same file, no dup despite fresh nonce

    def test_thumb_and_highlight_render_encrypted_pdf(self):
        body = _pdf_bytes("SYNTHETIC. The escrow amount is $9,999.")
        doc = self._upload("escrow.pdf", body).json()
        self.assertTrue(Path(doc["stored_path"]).read_bytes().startswith(MAGIC))
        thumb = client.get(f"/kb/thumb/{doc['id']}?page=1")
        self.assertEqual(thumb.status_code, 200)
        self.assertEqual(thumb.content[:8], b"\x89PNG\r\n\x1a\n")
        hi = client.get(f"/kb/highlight/{doc['id']}?page=1&span=escrow amount")
        self.assertEqual(hi.status_code, 200)
        self.assertEqual(hi.content[:8], b"\x89PNG\r\n\x1a\n")


class TestEncryptedIngestAnswerExport(_EncryptedBase):
    def test_encrypted_native_ingests_answers_and_exports_plaintext(self):
        body = b"SYNTHETIC - NOT REAL.\nThe indemnity cap is $250,000 per claim."
        doc = self._upload("indemnity_memo.txt", body).json()
        self.assertTrue(Path(doc["stored_path"]).read_bytes().startswith(MAGIC))
        self.assertEqual(self._wait_terminal(doc["id"]), "ready")
        # the decrypt scratch tree is gone once ingest ends
        self.assertFalse((routes_kb.KB_DB / ".ingest_tmp").exists())
        # live answerability from the encrypted native's chunks
        from answering import answer
        res = answer("What is the indemnity cap?", matter=self.slug,
                     db_path=str(routes_kb.KB_DB))
        self.assertEqual(res["rejected_claims"], [])
        self.assertTrue(res["citations"], res["answer_text"])
        self.assertEqual(res["citations"][0]["filename"], "indemnity_memo.txt")
        self.assertIn("250,000", res["answer_text"])
        # export surrenders PLAINTEXT natives that match the manifest checksum
        blob = retention.export_matter(self.slug, routes_kb.KB_DOCS)
        z = zipfile.ZipFile(io.BytesIO(blob))
        self.assertEqual(z.read("documents/indemnity_memo.txt"), body)


class TestNativesMigrationDrill(_EncryptedBase):
    def _plant_plain(self, name, body):
        keyvault.NATIVES_ENCRYPTION = False  # plant a pre-encryption native
        d = (routes_kb.KB_DOCS / self.slug)
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        p.write_bytes(body)
        doc = catalog.add_document(self.slug, p, status="ready")
        keyvault.NATIVES_ENCRYPTION = True
        return p, doc

    def test_drill_rehearse_then_migrate_verify_before_replace(self):
        body = b"SYNTHETIC plain-era native."
        p, _ = self._plant_plain("old.txt", body)
        r = mig.migrate(kb_docs_root=routes_kb.KB_DOCS, rehearse=True)
        self.assertEqual(r["encrypted"], ["old.txt"])
        self.assertEqual(p.read_bytes(), body)                       # rehearsal wrote nothing
        r = mig.migrate(kb_docs_root=routes_kb.KB_DOCS)
        self.assertEqual(r["encrypted"], ["old.txt"])
        self.assertTrue(p.read_bytes().startswith(MAGIC))
        self.assertEqual(keyvault.read_matter_file(p, self.slug), body)
        # second run: nothing left to do
        r = mig.migrate(kb_docs_root=routes_kb.KB_DOCS)
        self.assertEqual(r["already_encrypted"], ["old.txt"])

    def test_drill_checksum_mismatch_refuses_to_seal_corruption(self):
        p, doc = self._plant_plain("bitrot.txt", b"SYNTHETIC original bytes.")
        p.write_bytes(b"SYNTHETIC corrupted bytes!")  # disk no longer matches catalog
        with self.assertRaises(mig.NativeVerificationError):
            mig.migrate(kb_docs_root=routes_kb.KB_DOCS)
        self.assertEqual(p.read_bytes(), b"SYNTHETIC corrupted bytes!")  # untouched


if __name__ == "__main__":
    unittest.main()
