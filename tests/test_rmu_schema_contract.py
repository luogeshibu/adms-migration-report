import unittest


class RMUReviewSchemaContractTests(unittest.TestCase):
    def test_adms_db_owns_channel_ip_and_port(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "ADMS DB")
        keys = [key for key, _label, _width in group]
        self.assertIn("adms_channel_ip", keys)
        self.assertIn("adms_channel_port", keys)
        self.assertNotIn("channel_analysis", keys)
        self.assertFalse(any(name == "ADMS Channel" for name, _color, _cols in DATA_GROUPS))

    def test_channel_analysis_is_not_a_report_column(self):
        from migration_report_tool.config.column_schema import COLUMNS
        self.assertNotIn("channel_analysis", [key for key, _label, _width in COLUMNS])

    def test_se_uses_smart_not_ambiguous_device_column(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "SE")
        keys = [key for key, _label, _width in group]
        self.assertIn("se_smart", keys)
        self.assertNotIn("se_device", keys)


    def test_adms_db_smart_is_after_type(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "ADMS DB")
        keys = [key for key, _label, _width in group]
        self.assertIn("adb_smart", keys)
        self.assertEqual(keys.index("adb_smart"), keys.index("adb_type") + 1)

    def test_adms_sld_display_does_not_include_link(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        group = next(cols for name, _color, cols in DATA_GROUPS if name == "ADMS SLD")
        keys = [key for key, _label, _width in group]
        self.assertEqual(keys, ["asld_rmu", "asld_type", "asld_smart"])
        self.assertNotIn("asld_link", keys)

    def test_source_group_titles_use_clean_display_names(self):
        from migration_report_tool.config.column_schema import DATA_GROUPS
        names = [name for name, _color, _cols in DATA_GROUPS]
        self.assertIn("SE", names)
        self.assertIn("ADMS DB", names)
        self.assertIn("ADMS SLD", names)
        self.assertIn("ZENON DB", names)
        self.assertIn("ZENON SLD", names)
        self.assertNotIn("Driver Info", names)
        self.assertNotIn("ADMS Channel", names)
        self.assertNotIn("ZENON SLD XML", names)
        self.assertFalse(any(name.startswith("From ") for name in names))



if __name__ == "__main__":
    unittest.main()
