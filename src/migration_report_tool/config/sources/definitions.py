"""Built-in source column contracts.

Aliases are explicit business decisions, not fuzzy matching.  Add a new alias
here only after confirming that the external column has the same meaning.
"""
from __future__ import annotations

from ...domain.schema import FieldSpec, SourceSchema


def F(key, label, *aliases, required=False, description=""):
    return FieldSpec(key, label, tuple(aliases), required, description)


SOURCE_SCHEMAS: dict[str, SourceSchema] = {
    "se_list": SourceSchema("se_list", "SE Equipment List", (
        F("station", "Station", "SS", "STATION", "Station",
          description="SE station/substation identifier. Used for display and traceability."),
        F("feeder", "Feeder", "FEEDER", "FEEDR", required=True,
          description="Logical feeder identifier used by FEEDER Analysis."),
        F("rmu", "RMU", "EQUIPMENT", "RMU", "RMU_NO", required=True,
          description="RMU/equipment identifier used to join all source systems."),
        F("smart", "SMART / NORMAL", "SMART", "智能标识", "是否智能", "EQUIP. TYPE", "EQUIP TYPE",
          description="SE EQUIP. TYPE contains SMART/NORMAL in the current source format and participates in SMART Analysis."),
        F("oh_ug", "OH / UG", "OH / UG", "OH/UG", "OH_UG",
          description="Overhead/underground classification. Display/reference field."),
        F("rmu_type", "RMU Type", "RMU TYPE", "RMU_TYPE", "CABINET TYPE", "CabinetType", "TYPE",
          description="Physical cabinet type such as 2L1T/3L1T. Optional for SE and participates in TYPE Analysis when available."),
    )),
    "zenon_db": SourceSchema("zenon_db", "ZENON DB", (
        F("rmu", "RMU", "RMU", "RMU_NO", "RMU_NAME", required=True),
        F("feeder", "Feeder", "FEEDER", "FEEDER_NAME"),
        F("brand", "Brand", "BRAND"),
        # Confirmed current ADF export: DEVICE contains the cabinet/RMU type.
        F("rmu_type", "RMU Type", "DEVICE", "TYPE", "RMU_TYPE", "RMU TYPE", "CABINET TYPE", "CabinetType"),
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
    "zenon_sld": SourceSchema("zenon_sld", "ZENON SLD CSV", (
        F("rmu", "RMU", "RMU", "RMU_NO", required=True),
        F("feeder", "Feeder", "Feeder", "FEEDER", required=True),
        F("cabinet_type", "RMU Type", "CabinetType", "TYPE", "RMU_TYPE"),
        F("screen_name", "Screen name", "Screen name", "Screen Name", "Picture ShortName", "Picture"),
        F("smart", "SMART", "SMART", "智能标识", "是否智能"),
        F("warning", "Warning", "Warning", "WARNING"),
    )),
    "adms_db": SourceSchema("adms_db", "ADMS DB", (
        F("rmu", "RMU", "RMU_NAME", "RMU", "RMU_NO", "NAME", required=True),
        F("gss_fid", "ADMS_GSS-FID", "ADMS_GSS-FID", "ADMS_GSS_FID", "FEEDER"),
        F("rmu_type", "RMU Type", "TYPE", "RMU TYPE", "RMU_TYPE", "CABINET TYPE"),
        F("channel_ip", "ADMS Channel IP", "NET_DESCRIPTION1", "IP", "IP_ADDRESS"),
        F("channel_port", "ADMS Channel Port", "port", "PORT", "PRIMARY_PORT"),
        F("y1", "Y1", "Y1"), F("y2", "Y2", "Y2"), F("y3", "Y3", "Y3"), F("y4", "Y4", "Y4"),
        F("q1", "Q1", "Q1"), F("q2", "Q2", "Q2"),
    )),
    "adms_sld": SourceSchema("adms_sld", "ADMS SLD", (
        F("rmu", "RMU", "环网柜名称", "RMU", "RMU_NO", "RMU_NAME", "NAME", required=True),
        F("rmu_type", "RMU Type", "环网柜类型", "TYPE", "RMU_TYPE", "RMU TYPE", "柜型"),
        F("smart", "SMART", "智能标识", "是否智能", "SMART"),
        F("feeder", "Feeder", "FEEDER", "Feeder", "馈线", "馈线名称", "馈线名"),
        F("link", "LINK", "LINK", "RMU可关联", "关联", "环网柜ID", required=True),
    )),
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
