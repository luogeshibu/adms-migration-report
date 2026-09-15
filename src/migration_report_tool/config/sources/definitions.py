"""Built-in source column contracts.

Aliases are explicit business decisions, not fuzzy matching.  Add a new alias
here only after confirming that the external column has the same meaning.
"""
from __future__ import annotations

from ...domain.schema import FieldSpec, SourceSchema


def F(key, label, *aliases, required=False, warn_if_missing=True, description=""):
    return FieldSpec(
        key=key,
        label=label,
        aliases=tuple(aliases),
        required=required,
        warn_if_missing=warn_if_missing,
        description=description,
    )


SOURCE_SCHEMAS: dict[str, SourceSchema] = {
    "se_list": SourceSchema("se_list", "SE Equipment List", (
        F("station", "Station", "SS", "STATION", "Station",
          description="SE station/substation identifier. Used for display and traceability."),
        F("feeder", "Feeder", "FEEDER", "FEEDR", required=True,
          description="Logical feeder identifier used by FEEDER Analysis."),
        F("rmu", "Equipment Name", "EQUIPMENT", "RMU", "RMU_NO", required=True,
          description="Equipment identifier/name used as the record identity for cross-source matching. RMU remains a supported legacy physical-header alias."),
        F("device_type", "Device Type", "DeviceType", "DEVICE TYPE", "DEVICE_TYPE", "EQUIPMENT CLASS", "EQUIPMENT_CLASS", "设备类型", "设备类别",
          warn_if_missing=False,
          description="Generic equipment family/class such as RMU/TRANSFORMER/LBS/FUSE/REC/SFI. This is intentionally separate from TYPE, which is the equipment subtype/cabinet type such as 2L1T/3L1T."),
        F("smart", "SMART / NORMAL", "SMART", "智能标识", "是否智能", "EQUIP. TYPE", "EQUIP TYPE",
          description="SE EQUIP. TYPE contains SMART/NORMAL in the current source format and participates in SMART Analysis."),
        F("oh_ug", "OH / UG", "OH / UG", "OH/UG", "OH_UG",
          description="Overhead/underground classification. Display/reference field."),
        F("rmu_type", "Equipment Type / Subtype", "RMU TYPE", "RMU_TYPE", "CABINET TYPE", "CabinetType", "TYPE",
          description="Physical cabinet type such as 2L1T/3L1T. Optional for SE and participates in TYPE Analysis when available."),
        F("ip", "IP", "IP", "IP_ADDRESS", "PRIMARY_IP", warn_if_missing=False,
          description="Optional communication IP. If present it automatically participates in RMU Analysis IP consistency."),
    )),
    "zenon_db": SourceSchema("zenon_db", "ZENON DB", (
        F("rmu", "Equipment Name", "RMU", "RMU_NO", "RMU_NAME", "EQUIPMENT", "EQUIPMENT_NAME", required=True),
        F("feeder", "Feeder", "FEEDER", "FEEDER_NAME"),
        F("brand", "Brand", "BRAND"),
        F("device_type", "Device Type", "DeviceType", "DEVICE TYPE", "DEVICE_TYPE", "EQUIPMENT CLASS", "EQUIPMENT_CLASS", "设备类型", "设备类别",
          warn_if_missing=False,
          description="Generic equipment family/class when the ZENON DB export provides it. Do not map DEVICE here: current DEVICE is the subtype/cabinet TYPE field."),
        # Confirmed current ADF export: DEVICE contains the cabinet/RMU type.
        F("rmu_type", "Equipment Type / Subtype", "DEVICE", "TYPE", "RMU_TYPE", "RMU TYPE", "CABINET TYPE", "CabinetType"),
        F("nop", "NOP", "NOP"),
        F("smart", "SMART", "SMART", "智能标识", "是否智能"),
        F("vip", "VIP", "VIP"),
        F("function_location", "Function Location", "Function Location", "FUNCTION_LOCATION"),
        F("ip", "Driver IP", "PRIMARY_IP", "IP", "IP_ADDRESS"),
        F("port", "Driver Port", "PRIMARY_PORT", "PORT"),
        F("link_address", "LINK_ADDRESS", "LINK_ADDRESS"),
        F("link_address_size", "LINK_ADDRESS_SIZE", "LINK_ADDRESS_SIZE"),
        F("cot_size", "COT_SIZE", "COT_SIZE"),
        F("coa_size", "COA_SIZE", "COA_SIZE"),
        F("ioa_size", "IOA_SIZE", "IOA_SIZE"),
        F("t1", "T1", "T1"), F("t2", "T2", "T2"), F("t3", "T3", "T3"),
        F("k_value", "K", "K_VALUE", "K"), F("w_value", "W", "W_VALUE", "W"),
        F("net_address", "NET_ADDRESS", "NET_ADDRESS"),
    )),
    "zenon_sld": SourceSchema("zenon_sld", "ZENON SLD Equipment Inventory", (
        # v0.8.150: the authoritative ZENON-SLD contract is the all-equipment
        # device_inventory.csv produced by the XML extractor.  The current
        # Equipment Data Review profile still validates RMUs only, but every
        # source field is canonicalized now so CB/SFI/other profiles can reuse
        # the same file and global mapping later without another schema redesign.
        # Legacy ZENON-SLD.csv headers remain aliases for backward compatibility.
        F("device_type", "Device Type", "DeviceType", "DEVICE TYPE", "DEVICE_TYPE",
          warn_if_missing=False,
          description="Equipment class from the graphical inventory (RMU/CB/SFI/...). When present, the current RMU review profile filters DeviceType=RMU while retaining every other device row in the source inventory for future profiles."),
        F("rmu", "Equipment Name", "DeviceName", "RMU", "RMU_NO", required=True,
          description="Stable equipment/device identifier used as the record identity for cross-source matching. RMU remains a legacy alias when the physical file uses that header."),
        # DeviceScope is deliberately preferred over Picture.  In Jeddah, for
        # example, Picture may be one station-level screen such as ADF110 while
        # DeviceScope carries the feeder identity (JED-CTL-ADF-16).  Picture is
        # mapped separately as screen_name.
        F("feeder", "Feeder / Device Scope", "DeviceScope", "Feeder", "FEEDER", required=True,
          description="Logical feeder/device scope used by FEEDER Analysis. DeviceScope is the preferred inventory field; legacy Feeder remains supported."),
        F("cabinet_type", "Subtype / RMU Type", "SubType", "CabinetType", "TYPE", "RMU_TYPE",
          description="Graphical equipment subtype. For RMUs this is the cabinet type such as 2L1T/3L1T/3L."),
        F("screen_name", "Screen / Picture", "Picture", "Screen name", "Screen Name", "Picture ShortName",
          description="Physical zenOn picture/screen containing this equipment instance."),
        F("smart", "SMART", "SMART", "智能标识", "是否智能"),
        F("duplicate_count", "Graphic Instances", "GraphicInstances", "DuplicateCount", "DUPLICATE_COUNT", "Duplicate Count",
          warn_if_missing=False,
          description="Source-declared graphical occurrence count. The App also counts duplicate canonical rows independently."),
        F("warning", "Warning", "Warning", "WARNING", warn_if_missing=False),
        F("ip", "IP", "IP", "IP_ADDRESS", "PRIMARY_IP", warn_if_missing=False,
          description="Optional communication IP. If present it automatically participates in RMU Analysis IP consistency."),

        # Full device-inventory traceability. These are built-in optional fields:
        # they are mapped and preserved globally but do not create RMU Analysis
        # issues by themselves.  Future Equipment Review profiles can promote
        # the appropriate fields into their own Analysis contracts.
        F("script_version", "Script Version", "ScriptVersion", warn_if_missing=False),
        F("xml_file", "XML File", "XMLFile", warn_if_missing=False),
        F("destination_name", "Destination Name", "DestinationName", warn_if_missing=False),
        F("display_name", "Display Name", "DisplayName", warn_if_missing=False),
        F("resolved_full_name", "Resolved Full Name", "ResolvedFullName", warn_if_missing=False),
        F("full_destination", "Full Destination", "FullDestination", warn_if_missing=False),
        F("raw_substitute_destination", "Raw Substitute Destination", "RawSubstituteDestination", warn_if_missing=False),
        F("link_name", "Link Name", "LinkName", warn_if_missing=False),
        F("substitute_source", "Substitute Source", "SubstituteSource", warn_if_missing=False),
        F("vendor", "Vendor", "Vendor", warn_if_missing=False),
        F("name_source", "Name Source", "NameSource", warn_if_missing=False),
        F("name_status", "Name Status", "NameStatus", warn_if_missing=False),
        F("confidence", "Confidence", "Confidence", warn_if_missing=False),
        F("variable_root_match", "Variable Root Match", "VariableRootMatch", warn_if_missing=False),
        F("classification_reason", "Classification Reason", "ClassificationReason", warn_if_missing=False),
        F("element", "Element", "Element", warn_if_missing=False),
        F("element_name", "Element Name", "ElementName", warn_if_missing=False),
        F("start_x", "Start X", "StartX", warn_if_missing=False),
        F("start_y", "Start Y", "StartY", warn_if_missing=False),
    )),
    "adms_db": SourceSchema("adms_db", "ADMS DB", (
        F("rmu", "Equipment Name", "RMU_NAME", "RMU", "RMU_NO", "NAME", "EQUIPMENT", "EQUIPMENT_NAME", required=True),
        F("gss_fid", "ADMS_GSS-FID", "ADMS_GSS-FID", "ADMS_GSS_FID", "FEEDER"),
        F("device_type", "Device Type", "DeviceType", "DEVICE TYPE", "DEVICE_TYPE", "EQUIPMENT CLASS", "EQUIPMENT_CLASS", "设备类型", "设备类别", warn_if_missing=False,
          description="Generic equipment family/class when the ADMS DB export provides it. TYPE remains the subtype/cabinet type."),
        F("rmu_type", "Equipment Type / Subtype", "TYPE", "RMU TYPE", "RMU_TYPE", "CABINET TYPE"),
        F(
            "smart", "SMART", "SMART", "智能标识", "是否智能",
            warn_if_missing=False,
            description=(
                "Optional ADMS DB SMART/NORMAL field. If the source CSV does not contain "
                "a SMART column, the RMU Data Review column remains blank and SMART "
                "analysis ignores ADMS DB. If a SMART column is added later, it maps automatically."
            ),
        ),
        F(
            "channel_ip", "ADMS Channel IP", "IP", "IP_ADDRESS", "NET_DESCRIPTION1",
            description=(
                "ADMS channel IP is bound by physical header identity, never by column position. "
                "The explicit IP/IP_ADDRESS headers take precedence when present; "
                "NET_DESCRIPTION1 is retained only as a backward-compatible legacy fallback."
            ),
        ),
        F("channel_port", "ADMS Channel Port", "port", "PORT", "PRIMARY_PORT"),
        F("y1", "Y1", "Y1"), F("y2", "Y2", "Y2"), F("y3", "Y3", "Y3"), F("y4", "Y4", "Y4"),
        F("q1", "Q1", "Q1"), F("q2", "Q2", "Q2"),
    )),
    "adms_sld": SourceSchema("adms_sld", "ADMS SLD", (
        # v0.8.165: G File Studio's ADMS-SLD workbook uses the all-equipment
        # ``ADMS-SLD主设备`` sheet as the migration comparison source.  Keep the
        # stable App/business keys used by Analysis, but map them to the real
        # extractor headers and expose every remaining physical column as an
        # optional built-in App field for review/traceability.
        F("rmu", "Equipment Name", "DeviceName", "环网柜名称", "设备名称", "RMU", "RMU_NO", "RMU_NAME", "NAME", "EQUIPMENT", "EQUIPMENT_NAME", required=True,
          description="Universal equipment identifier used as the record identity. ADMS-SLD主设备 DeviceName is the preferred header; legacy RMU/EQUIPMENT aliases remain supported."),
        F("device_type", "Device Type", "DeviceType", "DEVICE TYPE", "DEVICE_TYPE", "设备类型", "设备类别", warn_if_missing=False,
          description="Generic equipment family/class such as RMU/TRANSFORMER/LBS/FUSE/CB."),
        F("rmu_type", "Type", "RMUType", "DeviceSubtype", "环网柜类型", "TYPE", "RMU_TYPE", "RMU TYPE", "柜型", "Subtype", "SUBTYPE",
          description="Equipment subtype. For RMU rows ADMS-SLD主设备 RMUType is preferred (for example 2L1T/3L1T). DeviceSubtype is a fallback."),
        F("smart", "SMART", "SmartType", "SMART", "是否智能", "智能标识",
          description="Normalized SMART/NORMAL classification. ADMS-SLD主设备 SmartType is preferred; IsSmart is retained separately as source traceability."),
        F("feeder", "Feeder", "facName", "FEEDER", "Feeder", "馈线", "馈线名称", "馈线名",
          description="Feeder/scope identifier. ADMS-SLD主设备 facName is the preferred extractor field."),
        F("link", "LINK", "LINK", "RMU可关联", "关联", "环网柜ID", warn_if_missing=False),
        F("ip", "IP", "IP", "IP_ADDRESS", "PRIMARY_IP", warn_if_missing=False,
          description="Optional communication IP. If present it participates in IP consistency Analysis."),

        # Full ADMS-SLD主设备 traceability. These fields are presentation/reference
        # inputs only unless promoted into SYSTEM_LOGIC_FIELD_KEYS later. They are
        # therefore visible in Equipment Data Review and can be hidden by users.
        F("g_file", "G File", "GFile", warn_if_missing=False),
        F("fac_id", "Facility ID", "facID", warn_if_missing=False),
        F("is_smart", "Is Smart", "IsSmart", warn_if_missing=False),
        F("smart_source", "Smart Source", "SmartSource", warn_if_missing=False),
        F("device_form", "Device Form", "DeviceForm", warn_if_missing=False),
        F("parent_rmu", "Parent RMU", "ParentRMU", warn_if_missing=False),
        F("device_subtype", "Device Subtype", "DeviceSubtype", warn_if_missing=False),
        F("profile_device_type", "Profile Device Type", "ProfileDeviceType", warn_if_missing=False),
        F("xml_element", "XML Element", "XML Element", "XMLElement", warn_if_missing=False),
        F("element_id", "Element ID", "ElementID", warn_if_missing=False),
        F("key_id", "Key ID", "keyid", "KeyID", warn_if_missing=False),
        F("key_name", "Key Name", "key_name", "KeyName", warn_if_missing=False),
        F("p_name_string", "p_NameString", "p_NameString", "PNameString", warn_if_missing=False),
        F("standard_file", "Standard File", "StandardFile", warn_if_missing=False),
        F("standard_devref", "Standard Devref", "StandardDevref", warn_if_missing=False),
        F("actual_devref", "Actual Devref", "ActualDevref", warn_if_missing=False),
        F("symbol_validation", "Symbol Validation", "SymbolValidation", warn_if_missing=False),
        F("validation_issue", "Validation Issue", "ValidationIssue", warn_if_missing=False),
        F("name_source", "Name Source", "NameSource", warn_if_missing=False),
        F("name_confidence", "Name Confidence", "NameConfidence", warn_if_missing=False),
        F("display_label", "Display Label", "DisplayLabel", warn_if_missing=False),
        F("display_label_distance", "Display Label Distance", "DisplayLabelDistance", warn_if_missing=False),
        F("quality_status", "Quality Status", "QualityStatus", warn_if_missing=False),
        F("x", "X", "x", "X", warn_if_missing=False),
        F("y", "Y", "y", "Y", warn_if_missing=False),
        F("w", "Width", "w", "W", warn_if_missing=False),
        F("h", "Height", "h", "H", warn_if_missing=False),
    ), sheet_name="ADMS-SLD主设备"),
    "ioa": SourceSchema("ioa", "ZENON-ADMS IOA", (
        F("rmu", "RMU", "RMU_NO", "RMU", required=True),
        F("zenon_gss_fid", "ZENON_GSS-FID", "ZENON_GSS-FID", "ZENON_GSS_FID"),
        F("zenon_signal_name", "ZENON signal name", "ZENON_signal_name", "ZENON_SIGNAL_NAME"),
        F("zenon_dot_no", "ZENON DOT NO", "ZENON_DOT_NO", "ZENON IOA", "ZENON_IOA"),
        F("adms_gss_fid", "ADMS_GSS-FID", "ADMS_GSS-FID", "ADMS_GSS_FID"),
        F("adms_signal_name", "ADMS signal name", "ADMS_signal_name", "ADMS_SIGNAL_NAME", required=True),
        F("adms_dot_no", "ADMS DOT NO", "ADMS_DOT_NO", "ADMS IOA", "ADMS_IOA", required=True),
    )),
    "standard_reference": SourceSchema("standard_reference", "IOA STANDARD Reference", (
        F("type", "Type", "Type", required=True),
        F("ioa", "IOA", "IOA", required=True),
        F("name", "name", "name", required=True),
    ), sheet_name="STANDARD", header_scan_rows=25),
}


def schema_for(source_type: str) -> SourceSchema | None:
    return SOURCE_SCHEMAS.get(source_type)
