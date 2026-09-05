from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from migration_report_tool.paths import resource_root, standard_reference_path
from migration_report_tool.services import standard_reference_service as svc


class StandardReferenceServiceTests(unittest.TestCase):
    def test_multiple_versions_are_preserved_and_activation_is_explicit(self):
        bundled = resource_root() / "templates" / "IOA STANDARD.xlsx"
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MIGRATION_REPORT_TOOL_USER_DATA_ROOT": td}, clear=False
        ):
            root = Path(td)
            a = root / "IOA STANDARD-V1.xlsx"
            b = root / "IOA STANDARD-V2.xlsx"
            a.write_bytes(bundled.read_bytes())
            b.write_bytes(bundled.read_bytes())

            self.assertEqual(svc.current_standard_reference_info().origin, "Built-in")
            info_a = svc.add_standard_reference(a, "tester")
            info_b = svc.add_standard_reference(b, "tester")
            self.assertFalse(info_a.active)
            self.assertFalse(info_b.active)
            self.assertEqual(svc.current_standard_reference_info().origin, "Built-in")

            active_a = svc.activate_standard_reference(info_a.key, "tester")
            self.assertEqual(active_a.path.name, a.name)
            self.assertEqual(active_a.origin, "User Library")
            self.assertEqual(standard_reference_path().name, a.name)

            refs = svc.list_standard_references()
            self.assertEqual({r.path.name for r in refs if r.origin == "User Library"}, {a.name, b.name})
            self.assertEqual(sum(1 for r in refs if r.active), 1)

            restored = svc.restore_bundled_standard_reference()
            self.assertEqual(restored.origin, "Built-in")
            self.assertTrue((root / "reference" / "standards" / a.name).exists())
            self.assertTrue((root / "reference" / "standards" / b.name).exists())

    def test_same_name_never_overwrites_without_explicit_consent(self):
        bundled = resource_root() / "templates" / "IOA STANDARD.xlsx"
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"MIGRATION_REPORT_TOOL_USER_DATA_ROOT": td}, clear=False
        ):
            root = Path(td)
            source = root / "STANDARD-Approved.xlsx"
            source.write_bytes(bundled.read_bytes())
            first = svc.add_standard_reference(source, "tester")
            with self.assertRaises(FileExistsError):
                svc.add_standard_reference(source, "tester", overwrite=False)
            second = svc.add_standard_reference(source, "tester", overwrite=True)
            self.assertEqual(first.path, second.path)
            backups = list((root / "reference" / "standards" / "backups").glob("STANDARD-Approved-*.xlsx"))
            self.assertEqual(len(backups), 1)

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
