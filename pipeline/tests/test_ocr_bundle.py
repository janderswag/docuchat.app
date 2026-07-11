"""Frozen builds must OCR with the VENDORED tesseract (Contents/Resources/
pipeline/vendor/tesseract), never assume a Homebrew install on the user's Mac.
B2 of the adoption-tips plan (council 2026-07-11): pytesseract is only a
wrapper that shells out — without this, every scanned page on a brew-less Mac
silently fails OCR."""

import sys
import unittest
from pathlib import Path
from unittest import mock

PIPELINE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_DIR))
import ingestion  # noqa: E402


class TestConfigureTesseract(unittest.TestCase):
    def test_frozen_uses_vendored_binary_and_tessdata(self):
        fake_root = Path("/tmp/fake-bundle/Resources")
        with mock.patch.object(ingestion.apppaths, "assets_root",
                               return_value=fake_root), \
             mock.patch.object(ingestion.Path, "is_file", return_value=True), \
             mock.patch.dict(ingestion.os.environ, {}, clear=False):
            cmd = ingestion.configure_tesseract()
            self.assertEqual(cmd,
                             str(fake_root / "vendor/tesseract/bin/tesseract"))
            self.assertEqual(ingestion.os.environ.get("TESSDATA_PREFIX"),
                             str(fake_root / "vendor/tesseract/share/tessdata"))
            import pytesseract
            self.assertEqual(pytesseract.pytesseract.tesseract_cmd, cmd)

    def test_dev_without_vendor_leaves_system_default(self):
        with mock.patch.object(ingestion.Path, "is_file", return_value=False):
            self.assertEqual(ingestion.configure_tesseract(), "system default")

    def test_configuration_happens_at_module_import(self):
        """Deleting the module-level configure_tesseract() call must fail THIS
        test: the frozen server only imports ingestion, it never calls the
        function itself."""
        import importlib
        fake_root = Path("/tmp/fake-bundle/Resources")
        with mock.patch.object(ingestion.apppaths, "assets_root",
                               return_value=fake_root), \
             mock.patch.object(ingestion.Path, "is_file", return_value=True), \
             mock.patch.dict(ingestion.os.environ, {}, clear=False):
            importlib.reload(ingestion)
            import pytesseract
            self.assertEqual(
                pytesseract.pytesseract.tesseract_cmd,
                str(fake_root / "vendor/tesseract/bin/tesseract"))
        importlib.reload(ingestion)   # restore un-mocked module state

    @classmethod
    def tearDownClass(cls):
        # undo any pytesseract command the frozen-path test set; the module
        # default is the plain "tesseract" PATH lookup
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = "tesseract"
        ingestion.configure_tesseract()


if __name__ == "__main__":
    unittest.main(verbosity=2)
