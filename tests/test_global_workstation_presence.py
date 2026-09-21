import unittest

from migration_report_tool.infrastructure.database.global_settings_store import (
    claim_global_configuration_admin,
    global_configuration_admin,
    is_global_configuration_admin,
    list_workstation_presence,
    touch_workstation_presence,
)


class WorkstationPresenceTests(unittest.TestCase):
    def test_presence_distinguishes_same_user_on_two_workstations(self):
        previous = __import__("os").environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            __import__("os").environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = tmp

            self.assertTrue(claim_global_configuration_admin("ADMS", "REVIEW-PC", "client-admin", "172.16.21.113"))
            self.assertTrue(touch_workstation_presence(
                "ADMS", "REVIEW-PC", "172.16.21.113", "client-admin", "0.8.207", True
            ))
            self.assertTrue(touch_workstation_presence(
                "ADMS", "CHECK-PC", "172.16.21.114", "client-review", "0.8.207", False
            ))

            admin = global_configuration_admin()
            self.assertEqual(admin["client_id"], "client-admin")
            self.assertEqual(admin["ip_address"], "172.16.21.113")
            self.assertTrue(is_global_configuration_admin("DIFFERENT_LOGIN", "client-admin"))
            self.assertFalse(is_global_configuration_admin("ADMS", "client-review"))

            rows = {row["client_id"]: row for row in list_workstation_presence()}
            self.assertTrue(rows["client-admin"]["online"])
            self.assertTrue(rows["client-admin"]["is_admin"])
            self.assertTrue(rows["client-review"]["online"])
            self.assertFalse(rows["client-review"]["is_admin"])
            self.assertEqual(rows["client-admin"]["user_name"], rows["client-review"]["user_name"])
        if previous is None:
            __import__("os").environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            __import__("os").environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = previous
