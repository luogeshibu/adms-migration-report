# NARI Saudi ADMS Migration Report - User Guide (v0.8.19)

## 1. Configure the Site Repository

Open **Site Data Sources** and choose the root folder that contains one subfolder per site, for example `D:\Workspace\SS`.

Recommended site folder:

```text
ADF\
├─ SE.xlsx
├─ ZENON.XML
├─ ZENON-DB.csv
├─ ZENON-SLD.csv
├─ ADMS-DB.csv
├─ ADMS-SLD.csv
├─ ZENON-ADMS-IOA.csv
```

Legacy names such as `ADF-SE.xlsx` and `ADF.XML` are recognized while sites are migrated to the standard names. `REPORT.xlsx` is not a Site Repository input. Signal Mapping uses the active application STANDARD reference. Use Settings -> Signal Mapping STANDARD reference (or Update STANDARD on the review page) to install a validated replacement; Restore Built-in returns to the release default.

Normal validation/sync operations treat source files as read-only. The explicit **Regenerate ZENON SLD** action is the only repository write and safely replaces the derived `ZENON-SLD.csv`. No Project is created manually. Selecting a site automatically binds it to a private application workspace for SQLite audit state, source snapshots, generated files and reports.


### Regenerate ZENON-SLD.csv from XML

Select a site and click **Regenerate ZENON SLD** when the derived CSV must be refreshed. The App parses the live site XML, applies the same exact feeder isolation used by validation, and atomically replaces `<site>/ZENON-SLD.csv`. If no RMUs are generated, the existing CSV is preserved.

### Rename visible review columns

Open **Source Mapping** for a tabular source and edit **Display Name**. This changes the **global App/Excel review header for every site**; **Internal Key** and each site's **Actual Column** mapping are unchanged. Use **Reset Names** to restore built-in labels. Global Display Names are stored in the application settings database.

## 2. Run site validation

1. Click **Refresh Sources** after copying/replacing site files.
2. Select the site (ADF, ABH, ABN, ABN2, ...).
3. Review the source inventory. `READY` means all current mandatory sources are available.
4. Click **Run Validation**.

Run Validation performs a fresh disk scan at the moment it is clicked. For combined zenOn XML files, the parser extracts the feeder from SubstituteDestination and keeps only records matching the selected site as an exact feeder token; e.g. ABN2 does not match ABN. Changed files are detected by SHA-256, a timestamped source snapshot is created, changed files are archived to the app workspace, and only then is the comparison rebuilt. This prevents a newly replaced SE/Zenon/ADMS file from being ignored accidentally.

## 3. Validation and human Review workflow

Project Overview shows the formal delivery path: **Data Sources -> Validation -> Human Review -> Migration Report**. The top-right project state is calculated automatically; it is not a button.

### RMU Data Review

1. `Analysis` is automatic: `Pass`, `1 Issue`, `2 Issues`, or `Critical`. It is calculated from NAME / FEEDER / SMART / TYPE / IP / LINK.
2. `Review` is human workflow: `Unreviewed`, `Reviewed`, or `Needs Action`.
3. Select one or more RMU rows and click **Set Review**. Use **Reviewed** only after verification/acceptance; use **Needs Action** when a correction is required.
4. Double-click a reviewable value only when an audited correction is needed. Use `Comments` for SE/NARI review notes.
5. If a later source refresh changes that RMU's automatic Analysis fingerprint, the Review state automatically returns to `Unreviewed`. Comments and Audit history remain.

### Signal Mapping Review

1. Automatic validation is `Matched`, `Mismatched`, or `Unchecked`.
2. Project Overview explicitly reconciles `Total = Checked + Unchecked` and `Checked = Matched + Mismatched`. Match Rate is `Matched / Checked`.
3. Select signal rows and click **Set Review**. `Reviewed` means verified/accepted; `Needs Action` means mapping correction is required.
4. If a reviewed signal row's validation content changes, only that row returns to `Unreviewed`. Unchanged reviewed rows remain reviewed even if another source row changed.

A `Needs Action` row counts as processed Review work, but it blocks the project from reaching **Ready for Export** until resolved.

Open **Change Audit** to trace review-state changes, automatic review resets, corrections, old/new values, user and timestamp. Save **Review Versions** before formal handover and use **Report Export** for the Migration Report workbook.

## 4. Advanced Manual Import

Use **Advanced Manual Import** only when a delivery cannot follow the Site Repository naming convention. Manual inputs are still copied into the selected site workspace before use.

## 5. SE equipment columns

The current SE equipment-list columns are `SS`, `FEEDR/FEEDER`, `EQUIPMENT`, `EQUIP. TYPE`, and `OH / UG`. Source Mapping resolves these to fixed internal keys: station / feeder / rmu / smart / oh_ug. `EQUIP. TYPE` is SMART/NORMAL in this source format; it is no longer duplicated as an ambiguous Device field.
