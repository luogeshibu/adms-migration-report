# Site Repository

The Site Repository is the user-managed source tree. One direct child folder is
one site. Normal validation/sync operations are read-only.

## Unified site storage

A migrated or newly created site may keep its source tables and persistent
Project Data together:

```text
1-AJWD/
  project.db
  project.json
  PORTABLE_SITE.json       # created by the one-time migration action
  source_files/
    ADMS-DB.xlsx
    ZENON-DB.xlsx
    ZENON-SLD.xlsx
    ...
  reports/
```

The application detects this layout and opens `project.db` directly in the site
folder. This preserves Comments and Checked records when the folder is copied
to another machine. New imports use `source_files/` automatically. Existing
split-layout sites remain supported for backward compatibility.

## Recommended site inputs

```text
<Site>/
├─ SE.xlsx
├─ ZENON-SLD.csv
├─ ZENON-DB.csv
├─ ADMS-DB.csv
├─ ADMS-SLD.csv
└─ ZENON-ADMS-IOA.csv
```

Published `-V1`, `-V2`, `-V2.1.0` variants remain supported by the existing
version-selection rules.

## ZENON SLD

`ZENON-SLD.csv` is the authoritative graphical equipment inventory. It is
produced outside Migration Report and supplied directly to the site folder.
Migration Report does not parse ZENON XML and does not generate, regenerate or
overwrite ZENON-SLD.csv.

The standard v0.8.150+ all-equipment inventory contract is retained, including
DeviceType, DeviceName, DeviceScope, Picture, SubType, SMART and traceability
fields. Equipment Data Review currently activates the RMU profile and retains
other equipment types for future profiles.
