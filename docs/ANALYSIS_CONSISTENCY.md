# RMU Analysis Consistency Standard — v0.8.143

The RMU Data Review `Analysis` group uses one shared rule for **NAME / FEEDER / SMART / TYPE / IP**.

## Decision rule

For each field, the App collects the value from every applicable RMU source: **SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD**.

1. Blank / missing values do not participate in comparison.
2. If every source is blank, Analysis is blank (`N/A`).
3. If exactly one source has a value, Analysis is `TRUE`.
4. If two or more sources have values, Analysis is `TRUE` only when all normalized values agree.
5. Any conflicting non-blank value produces `FALSE` and becomes a customer Resolution decision.
6. A missing source row is informational only; it does not by itself create an Analysis mismatch.

This means Analysis is availability-driven, not majority-driven. Three equal values and one conflicting value are still `FALSE`; the App never lets a majority vote hide a disagreement.

## Field normalization

- **NAME**: RMU/cabinet identifier, case-normalized.
- **FEEDER**: station-aware feeder identity. Region/routing prefixes such as `JED-NTH` are ignored, but station identity is retained. `ABH-03`, `JED-NTH-ABH-03` and `JED-NTH-ABH-AH303` normalize to the same logical feeder `ABH-3`; `ABN-3` is different.
- **SMART**: common SMART/SMR/YES/TRUE/1 representations normalize to `SMART`; NORMAL/NO/FALSE/0 representations normalize to `NORMAL`.
- **TYPE**: cabinet type such as `2L1T` / `3L1T` is normalized without insignificant spacing/case differences.
- **IP**: IPv4/IPv6/CIDR values are normalized to the host IP before comparison.

## Source-aware IP

IP is no longer a special two-source `ZENON DB ↔ ADMS DB` comparison. It uses the same common five-source engine as the other fields.

Current files normally provide IP in **ZENON DB** and **ADMS DB**, so those are the only two values that participate today. Optional IP mappings are also defined for **SE / ZENON SLD / ADMS SLD**. If one of those source files later adds an `IP`, `IP_ADDRESS` or `PRIMARY_IP` field and it is mapped, that value automatically joins the same comparison.

Examples:

- ZENON DB only has `172.20.13.10` → `TRUE`.
- ZENON DB + ADMS DB both have `172.20.13.10` → `TRUE`.
- ZENON DB = `172.20.13.10`, ADMS DB = `172.20.13.11` → `FALSE`.
- SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD all have the same IP → `TRUE`.
- Four sources agree and one source differs → `FALSE`.

The Resolution candidates preserve the contributing source name and raw value so the customer can select the approved value when Analysis is `FALSE`.
