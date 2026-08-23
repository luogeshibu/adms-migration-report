# Architecture Baseline — v0.8.0

The application uses layered boundaries:

- **Domain**: review rules, normalizers, severity and signal mapping. No Qt and no file-system decisions.
- **Services**: use-case orchestration such as RMU review, source import and schema mapping.
- **Infrastructure**: CSV/XLSX/XML parsing, SQLite, Site Repository, adapters and Excel export.
- **UI**: display/filter/edit/review interactions only.
- **Config**: stable review column layout and explicit source-schema profiles.

The two major review workflows are application-owned:

1. **RMU Data Review** — SE + ZENON + ADMS canonical data -> NAME/FEEDER/SMART/TYPE/IP/LINK analysis.
2. **Signal Mapping Review** — ZENON-ADMS-IOA + ADMS-SLD Type + REPORT/STANDARD(Type, IOA, name) -> calculated mapping review.

Site REPORT workbooks are not inputs. Signal Mapping uses only the bundled `resources/templates/IOA STANDARD.xlsx` reference workbook.
