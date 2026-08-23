import unittest


class RMUReviewSchemaContractTests(unittest.TestCase):
    def test_adms_channel_contains_only_ip_and_port(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "ADMS Channel")
        keys = [key for key, _label, _width in group]
        self.assertEqual(keys, ["adms_channel_ip", "adms_channel_port"])
        self.assertNotIn("channel_analysis", keys)

    def test_channel_analysis_is_not_a_report_column(self):
        from migration_report_tool.config.column_schema import COLUMNS
        self.assertNotIn("channel_analysis", [key for key, _label, _width in COLUMNS])

    def test_se_uses_smart_not_ambiguous_device_column(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "SE")
        keys = [key for key, _label, _width in group]
        self.assertIn("se_smart", keys)
        self.assertNotIn("se_device", keys)

    def test_source_group_titles_use_clean_display_names(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        names = [name for name, _color, _cols in DATA_GROUPS]
        self.assertIn("SE", names)
        self.assertIn("ADMS DB", names)
        self.assertIn("ADMS SLD", names)
        self.assertIn("Driver Info", names)
        self.assertFalse(any(name.startswith("From ") for name in names))



if __name__ == "__main__":
    unittest.main()
