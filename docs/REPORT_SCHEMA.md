# DATA Report Schema

The desktop Comparison view and exported `DATA` worksheet share one canonical column schema.

The application no longer uses a customer report template. The only bundled workbook is `resources/templates/IOA STANDARD.xlsx`, used as the STANDARD signal reference.

| Columns | Group | Fields |
|---|---|---|
| A:B | index | No., RMU |
| C:G | SE | Station, Feeder, RMU, Device, OH / UG |
| H:O | ZENON DB | Feeder, RMU, BRAND, Device, NOP, SMART, VIP, Function Location |
| P:AB | Driver Info | IP, PORT, LINK_ADDRESS, LINK_ADDRESS_SIZE, COT_SIZE, COA_SIZE, IOA_SIZE, T1, T2, T3, K, W, NET_ADDRESS |
| AC:AF | ZENON SLD XML | Screen Name, Feeder, RMU, TYPE |
| AG:AO | ADMS DB | RMU, ADMS_GSS-FID, Y1, Y2, Y3, Y4, Q1, Q2, TYPE |
| ADMS Channel | ADMS Channel | IP, PORT |
| AS:AV | ADMS SLD | RMU, TYPE, SMART, LINK |
| AW:AZ | Analysis | NAME, FEEDER, SMART, TYPE |
| BA | Remarks | Remarks |
| BB | Comments | SE user review comments |

## Zenon XML Screen Name

`Screen Name` is read from the owning Zenon XML picture node:

```xml
<Picture ShortName="ADF110 (JEDDAH)">
```

The canonical internal field is `zsld_screen_name`. Legacy CSV columns named `Picture`, `Picture ShortName`, or `Screen Name` remain accepted.

## Ownership

Columns A:BA mirror the customer DATA template. BB `Comments` is intentionally appended by Migration Report Tool for SE review feedback and is stored in SQLite, version snapshots, Audit Log changes, and exported reports.
