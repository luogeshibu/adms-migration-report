import unittest
from unittest.mock import patch

from migration_report_tool.parsers import read_excel_rows


class _Sheet:
    def __init__(self, rows):
        self._rows = rows

    def iter_rows(self, values_only=True):
        return iter(self._rows)


class _FailingSheet:
    def iter_rows(self, values_only=True):
        def _rows():
            yield ("A", "B")
            raise RuntimeError("synthetic streaming failure")
        return _rows()


class _Workbook:
    def __init__(self, sheet):
        self.active = sheet
        self.closed = False

    def close(self):
        self.closed = True


class ExcelHandleSafetyTests(unittest.TestCase):
    def test_read_excel_rows_closes_workbook_after_normal_read(self):
        wb = _Workbook(_Sheet([("A", "B"), (1, 2)]))
        with patch("migration_report_tool.infrastructure.parsers.legacy.load_workbook", return_value=wb):
            rows = read_excel_rows("ignored.xlsx")
        self.assertEqual(rows, [{"A": 1, "B": 2}])
        self.assertTrue(wb.closed)

    def test_read_excel_rows_closes_workbook_when_sheet_is_empty(self):
        wb = _Workbook(_Sheet([]))
        with patch("migration_report_tool.infrastructure.parsers.legacy.load_workbook", return_value=wb):
            rows = read_excel_rows("ignored.xlsx")
        self.assertEqual(rows, [])
        self.assertTrue(wb.closed)

    def test_read_excel_rows_closes_workbook_when_streaming_raises(self):
        wb = _Workbook(_FailingSheet())
        with patch("migration_report_tool.infrastructure.parsers.legacy.load_workbook", return_value=wb):
            with self.assertRaises(RuntimeError):
                read_excel_rows("ignored.xlsx")
        self.assertTrue(wb.closed)


if __name__ == "__main__":
    unittest.main()
