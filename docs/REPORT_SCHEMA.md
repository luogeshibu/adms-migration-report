# DATA Report Schema

The desktop Comparison view and exported `DATA` worksheet share one canonical column schema.

The application no longer uses a customer report template. The only bundled workbook is `resources/templates/IOA STANDARD.xlsx`, used as the STANDARD signal reference.

| Columns | Group | Fields |
|---|---|---|
| A:B | index | No., RMU |
| C:G | SE | Station, Feeder, RMU, SMART, OH / UG |
| H:AB | ZENON DB | Feeder, RMU, BRAND, Device, NOP, SMART, VIP, Function Location, IP, PORT, LINK_ADDRESS, LINK_ADDRESS_SIZE, COT_SIZE, COA_SIZE, IOA_SIZE, T1, T2, T3, K, W, NET_ADDRESS |
| AC:AF | ZENON SLD | Screen Name, Feeder, RMU, TYPE |
| AG:AR | ADMS DB | RMU, ADMS_GSS-FID, Y1, Y2, Y3, Y4, Q1, Q2, TYPE, SMART, IP, PORT |
| AS:AU | ADMS SLD | RMU, TYPE, SMART |
| AV:AZ | Analysis | NAME, FEEDER, SMART, TYPE, IP |
| BA | Remarks | Remarks |
| BB | Resolution | Customer resolution / review comment |

## ZENON SLD Screen / Picture

`Screen / Picture` is read from the mapped `Picture` field in the supplied ZENON-SLD device inventory.


## Ownership

Each visible source group corresponds to one physical source table. Missing physical fields remain blank. Analysis may normalize/compare values, but source-table cells preserve their own source values. BB stores the structured/manual Resolution text used by the review and sign-off workflow.
