from pathlib import Path
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import resolve_schema


class V08128AdmsSldSmartHeaderPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_version(self):
        version = (self.root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.215"', version)

    def test_adms_sld_smart_prefers_is_smart_header(self):
        result = resolve_schema(
            schema_for("adms_sld"),
            ["环网柜名称", "环网柜类型", "智能标识", "是否智能"],
        )
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("smart"), "是否智能")

    def test_legacy_header_remains_supported(self):
        result = resolve_schema(
            schema_for("adms_sld"),
            ["环网柜名称", "环网柜类型", "智能标识"],
        )
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("smart"), "智能标识")

    def test_old_saved_mapping_cannot_override_explicit_is_smart_header(self):
        result = resolve_schema(
            schema_for("adms_sld"),
            ["环网柜名称", "环网柜类型", "智能标识", "是否智能"],
            {"smart": "智能标识"},
        )
        self.assertEqual(result.mapped_column("smart"), "是否智能")
        self.assertIn("ignored", result.mapping_by_key["smart"].message.lower())

    def test_project_schema_unchanged(self):
        migrations = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "migrations.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_SCHEMA_VERSION = 12", migrations)


if __name__ == "__main__":
    unittest.main()
