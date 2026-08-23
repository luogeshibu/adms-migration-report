# Site Data Sources Standard — v0.8.19

## Identity model

The Site Repository is the user-managed source tree. Normal validation/sync operations are read-only; the explicit **Regenerate ZENON SLD** action is the only repository write and replaces the derived `ZENON-SLD.csv` after a successful XML parse. **One direct child folder equals one site identity. There is no separate Project creation step in the UI.** Selecting `ADF`, `ABH`, `ABN2`, etc. automatically binds that site to a private application workspace used for SQLite audit state, snapshots, generated files and reports.

```text
D:\Workspace\SS\
├─ ADF\
├─ ABH\
├─ ABN\
└─ ABN2\
```

Recommended site contents:

```text
<Site>\
├─ SE.xlsx
├─ ZENON.XML
├─ ZENON-DB.csv
├─ ZENON-SLD.csv
├─ ADMS-DB.csv
├─ ADMS-SLD.csv
├─ ZENON-ADMS-IOA.csv
```

Legacy names such as `ADF-SE.xlsx` and `ADF.XML` remain supported. Site REPORT workbooks are deliberately ignored; STANDARD reference data is application-owned. If exactly one XML exists it is accepted even with a combined name such as `ABN-ABN2.XML`. If multiple XMLs exist, the scanner can select a unique XML whose filename contains the current site as an exact token.


## Regenerate ZENON SLD

`ZENON.XML` is the graphical source of truth. `ZENON-SLD.csv` is a derived/fallback file. With a site selected, **Regenerate ZENON SLD** parses the live XML using the same exact site-feeder isolation used by Run Validation, writes a temporary CSV beside the target, and then replaces `<Site>/ZENON-SLD.csv`. If parsing produces zero RMUs or writing fails, the existing CSV remains unchanged.

## Required inputs

Formal migration validation requires:

- `SE.xlsx`
- `ZENON-DB.csv`
- `ADMS-DB.csv`
- `ADMS-SLD.csv`
- `ZENON-ADMS-IOA.csv`
- one graphical source: `ZENON.XML` or fallback `ZENON-SLD.csv`
- active application `IOA STANDARD.xlsx` for Signal Mapping Review

Site REPORT workbooks are not validation inputs.

## Combined zenOn XML site isolation

A shared XML can contain more than one site. The parser does **not** trust `Picture/@ShortName` for site membership. RMU records are first extracted using the proven rules:

```text
LinkName -> cabinet type
SubstituteDestination -> normalize after final '#'
last '-' token -> RMU
prefix before last '-' -> feeder
```

The selected site is then matched against exact feeder tokens. Example:

```text
Selected site: ABN2
JED-NTH-ABN2-16 -> INCLUDE
JED-JED-ABN2-03 -> INCLUDE
JED-NTH-ABN-16  -> EXCLUDE
JED-STH-ADEL-20 -> EXCLUDE
```

Exact token matching means site `ABN` never matches token `ABN2`. SE `FEEDER` values are also accepted as suffix matches, e.g. `ABN2-16` matches `JED-NTH-ABN2-16`.

## Runtime flow

```text
Select site
→ Rescan selected site folder
→ Validate required sources
→ SHA-256 fingerprint current files
→ Create timestamped snapshot when content changed
→ Archive changed sources into private app workspace
→ Parse current sources
→ Apply selected-site feeder filter to zenOn XML
→ Rebuild RMU validation + Signal Mapping validation
→ Preserve audited overrides / Comments
→ Save project.db
→ Refresh UI
```

## Private application workspace

```text
workspace\ABN2\
├─ project.db
├─ project.json
├─ source_files\
├─ snapshots\
├─ generated\
│  └─ ZENON-SLD.csv   # already filtered to ABN2
└─ reports\
```

`project.db` and `project.json` are retained as internal backward-compatible filenames; users no longer create/open projects manually.
