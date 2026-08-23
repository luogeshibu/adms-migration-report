# Windows Excel File Handle Safety

## Why v0.7.3 exists

`openpyxl.load_workbook(..., read_only=True)` streams an XLSX file from its ZIP archive. On Windows the archive remains locked until `Workbook.close()` is called. If a regression test or temporary project tries to delete the imported workbook first, Python raises:

`PermissionError: [WinError 32] another process is using the file`

The lock was produced by the application process itself, not by the comparison data.

## Required lifecycle

Every `load_workbook()` call must use deterministic cleanup:

```python
wb = load_workbook(path, read_only=True, data_only=True)
try:
    # read workbook
    ...
finally:
    wb.close()
```

This rule applies to normal reads, empty worksheets and exceptions while streaming rows.

## Release validation

The regression suite contains explicit workbook-close contract tests. The production `read_excel_rows()` helper, formal report export path and packaged self-test all use deterministic workbook cleanup.

Do not replace this with `gc.collect()` or arbitrary sleep calls. Garbage collection timing is not a valid file-lifecycle contract on Windows.
