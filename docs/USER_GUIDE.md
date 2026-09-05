# User Guide

## Site source files

Place the current site inputs in one site folder:

```text
SE.xlsx
ZENON-SLD.csv
ZENON-DB.csv
ADMS-DB.csv
ADMS-SLD.csv
ZENON-ADMS-IOA.csv
```

`ZENON-SLD.csv` is supplied directly from the external SLD/device-inventory
extraction workflow. Migration Report no longer accepts ZENON XML and contains
no XML-to-SLD generation action.

Use **Site Data Sources** to select AUTO/latest versions, pin a published
version, choose a manual file, and map its columns. **Refresh Sources** rescans
the site. **Run Validation** force-reads the active tabular sources and rebuilds
the review data.

## Equipment Data Review

The current active review profile is RMU. ZENON-SLD may contain all equipment
types; only DeviceType=RMU participates in today's RMU comparison when
DeviceType is available. Other equipment rows remain available for future
review profiles.
