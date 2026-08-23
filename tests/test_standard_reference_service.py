from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from migration_report_tool.paths import resource_root
from migration_report_tool.services import standard_reference_service as svc


class StandardReferenceServiceTests(unittest.TestCase):
    def test_install_and_restore_validated_standard_override(self):
        bundled = resource_root() / "templates" / "IOA STANDARD.xlsx"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "NEW STANDARD.xlsx"
            source.write_bytes(bundled.read_bytes())
            override = root / "reference" / "IOA STANDARD.xlsx"
            metadata = root / "reference" / "standard_reference.json"

            active = lambda: override if override.exists() else bundled
            origin = lambda: "User Override" if override.exists() else "Built-in"
            with patch.object(svc, "standard_override_path", lambda: override), \
                 patch.object(svc, "standard_reference_metadata_path", lambda: metadata), \
                 patch.object(svc, "standard_reference_path", active), \
                 patch.object(svc, "standard_reference_origin", origin), \
                 patch.object(svc, "bundled_standard_reference_path", lambda: bundled):
                info = svc.install_standard_reference(source, "tester")
                self.assertEqual(info.origin, "User Override")
                self.assertEqual(info.path, override)
                self.assertTrue(override.exists())
                self.assertTrue(metadata.exists())
                self.assertGreater(info.row_count, 0)

                restored = svc.restore_bundled_standard_reference()
                self.assertEqual(restored.origin, "Built-in")
                self.assertEqual(restored.path, bundled)
                self.assertFalse(override.exists())

    def test_invalid_standard_is_rejected_before_install(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "invalid.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "STANDARD"
            ws.append(["Type", "Wrong IOA", "name"])
            ws.append(["2L1T", "1", "Signal"])
            wb.save(path)
            wb.close()
            with self.assertRaises(ValueError):
                svc.validate_standard_reference(path)


if __name__ == "__main__":
    unittest.main()
