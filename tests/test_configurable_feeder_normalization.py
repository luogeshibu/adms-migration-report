from migration_report_tool.domain.analysis.consistency import compare_strict_consistency
from migration_report_tool.services.configurable_comparison_service import (
    NORMALIZATION_AUTO,
    NORMALIZATION_FEEDER,
    NORMALIZATION_NOP,
    NORMALIZATION_SMART,
    NORMALIZATION_TEXT,
    _comparison_normalizer,
    normalize_config,
)


def test_configurable_feeder_rule_decodes_adms_ah3_value():
    rule = {"title": "FEEDER", "normalization": NORMALIZATION_FEEDER}
    normalizer = _comparison_normalizer(rule, "1-AJWD")

    assert normalizer("JED-CTL-AJWD-AH331") == "AJWD-31"
    assert normalizer("AJWD-31") == "AJWD-31"
    result = compare_strict_consistency(
        {"ADMS DB": "JED-CTL-AJWD-AH331", "ZENON DB": "AJWD-31"},
        normalizer,
    )
    assert result.value is True


def test_existing_config_defaults_to_conservative_text_normalization():
    config = normalize_config({
        "sources": [{"id": "adms", "title": "ADMS DB"}, {"id": "zenon", "title": "ZENON DB"}],
        "comparisons": [{
            "id": "feeder",
            "title": "FEEDER",
            "bindings": {"adms": "feeder", "zenon": "feeder"},
        }],
    })

    assert config["comparisons"][0]["normalization"] == NORMALIZATION_TEXT
    assert _comparison_normalizer(config["comparisons"][0], "1-AJWD")("JED-CTL-AJWD-AH331") == "JED-CTL-AJWD-AH331"


def test_smart_alias_normalization_is_explicit_and_site_local():
    feeder = {"title": "FEEDER", "normalization": NORMALIZATION_AUTO}
    smart = {"title": "SMART", "normalization": NORMALIZATION_SMART}

    assert _comparison_normalizer(feeder, "1-AJWD")("JED-CTL-AJWD-AH331") == "AJWD-31"
    assert _comparison_normalizer(smart)("NORMAL") == "NORMAL"
    assert _comparison_normalizer(smart)("NONSMART") == "NORMAL"


def test_nop_contains_normalization_treats_any_nop_value_as_nop():
    nop = {"title": "NOP", "normalization": NORMALIZATION_NOP}
    normalizer = _comparison_normalizer(nop)

    assert normalizer("NOP") == "NOP"
    assert normalizer("SMART NOP") == "NOP"
    assert normalizer("NORMAL N.O.P.") == "NOP"
    assert normalizer("NON-NOP DEVICE") == "NOP"
    assert normalizer("SMART") == "SMART"
    assert compare_strict_consistency(
        {"SE": "SMART NOP", "ADMS DB": "NOP"}, normalizer
    ).value is True


def test_nop_auto_mode_uses_nop_contains_normalization():
    normalizer = _comparison_normalizer({"title": "NOP", "normalization": NORMALIZATION_AUTO})
    assert normalizer("SMART NOP HT") == "NOP"
