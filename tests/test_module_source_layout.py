from migration_report_tool.config.source_modules import MODULE_SOURCE_GROUPS


def test_module_source_layout_exposes_all_review_dependencies():
    modules = {m.key: m for m in MODULE_SOURCE_GROUPS}
    assert set(modules) == {"rmu_review", "signal_mapping"}

    rmu = [t.source_type for t in modules["rmu_review"].tables]
    assert rmu == ["se_list", "zenon_xml", "zenon_sld", "zenon_db", "adms_db", "adms_sld"]

    signal = [t.source_type for t in modules["signal_mapping"].tables]
    assert signal == ["ioa", "adms_sld", "standard_reference"]


def test_adms_sld_is_explicitly_shared_and_standard_is_application_table():
    modules = {m.key: m for m in MODULE_SOURCE_GROUPS}
    assert "adms_sld" in {t.source_type for t in modules["rmu_review"].tables}
    assert "adms_sld" in {t.source_type for t in modules["signal_mapping"].tables}
    standard = next(t for t in modules["signal_mapping"].tables if t.source_type == "standard_reference")
    assert standard.expected_name == "IOA STANDARD.xlsx"
    assert "Application" in standard.role


def test_zenon_xml_and_derived_sld_relationship_is_visible():
    rmu = next(m for m in MODULE_SOURCE_GROUPS if m.key == "rmu_review")
    xml = next(t for t in rmu.tables if t.source_type == "zenon_xml")
    sld = next(t for t in rmu.tables if t.source_type == "zenon_sld")
    assert "generates ZENON SLD" in xml.role
    assert "Derived" in sld.role
