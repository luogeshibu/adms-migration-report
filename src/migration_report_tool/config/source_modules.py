"""Business-module to source-table relationships shown by Site Repository.

The same physical table may intentionally appear in more than one module.  This
is a dependency view, not a de-duplicated file inventory.  Keeping the
relationship explicit makes it obvious which tables feed each review module.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleTableRef:
    source_type: str
    label: str
    role: str
    expected_name: str


@dataclass(frozen=True)
class ModuleSourceGroup:
    key: str
    label: str
    description: str
    tables: tuple[ModuleTableRef, ...]


MODULE_SOURCE_GROUPS: tuple[ModuleSourceGroup, ...] = (
    ModuleSourceGroup(
        "rmu_review",
        "RMU Data Review",
        "Cross-system RMU review assembled from SE, ZENON and ADMS tables. ZENON XML is the graphical source of truth and can regenerate the derived ZENON SLD table.",
        (
            ModuleTableRef("se_list", "SE Equipment", "RMU / feeder / SMART reference", "SE.xlsx"),
            ModuleTableRef("zenon_xml", "ZENON XML", "Graphical source → generates ZENON SLD", "ZENON.XML"),
            ModuleTableRef("zenon_sld", "ZENON SLD", "Derived XML table / fallback input", "ZENON-SLD.csv"),
            ModuleTableRef("zenon_db", "ZENON DB", "Device / driver / communication data", "ZENON-DB.csv"),
            ModuleTableRef("adms_db", "ADMS DB", "ADMS migration / channel data", "ADMS-DB.csv"),
            ModuleTableRef("adms_sld", "ADMS SLD", "ADMS RMU type / SMART / LINK result", "ADMS-SLD.csv"),
        ),
    ),
    ModuleSourceGroup(
        "signal_mapping",
        "Signal Mapping Review",
        "Signal review assembled from the site IOA table, ADMS SLD cabinet type and the active application STANDARD reference.",
        (
            ModuleTableRef("ioa", "ZENON-ADMS IOA", "ZENON ↔ ADMS signal mapping", "ZENON-ADMS-IOA.csv"),
            ModuleTableRef("adms_sld", "ADMS SLD", "Shared RMU type reference", "ADMS-SLD.csv"),
            ModuleTableRef("standard_reference", "IOA STANDARD", "Application reference table", "IOA STANDARD.xlsx"),
        ),
    ),
)

MODULE_BY_KEY = {module.key: module for module in MODULE_SOURCE_GROUPS}
