from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = (ROOT / "src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_release_version_contract():
    assert '__version__ = "0.8.164"' in VERSION


def test_review_versions_and_site_history_have_chinese_meta_ui():
    pairs = {
        "Save Version": "保存版本",
        "No saved versions yet": "暂无已保存版本",
        "Revision History": "版本历史",
        "Issue / Action Register": "问题 / 处理登记",
        "Need Action Lifecycle": "需处理生命周期",
        "RMU Needs Action Tracking": "RMU 需处理跟踪",
        "Change Audit History": "变更审计历史",
        "PDF Sign-off History": "PDF 签字历史",
        "Attach Signed PDF": "关联已签字 PDF",
        "Open Selected PDF": "打开所选 PDF",
        "Generated PDF": "生成的 PDF",
        "Signed PDF": "已签字 PDF",
    }
    for english, chinese in pairs.items():
        assert f'"{english}": "{chinese}"' in I18N


def test_report_export_copy_is_localized():
    for token in (
        '"Migration Report Export": "迁移报告导出"',
        '"Open Site Workspace": "打开站点工作区"',
        '"Station modification & issue-closure sign-off PDF": "站点修改与问题关闭签字 PDF"',
        '"Open Site History": "打开站点历史"',
        '"Delivery status: Ready for formal Migration Report export": "交付状态：可正式导出迁移报告"',
    ):
        assert token in I18N


def test_runtime_refreshed_pages_retranslate_after_assignment():
    assert "translate_widget_tree(self.site_history_page, self.ui_language)" in UI
    assert "translate_widget_tree(self.export_page, self.ui_language)" in UI
    assert "translate_widget_tree(self.db_smart_page, self.ui_language)" in UI
    assert 'ui_tr(f"Migration Report · User: {self.user_name} · Site DB: project.db", self.ui_language)' in UI
    assert "class I18nStatusBar(QStatusBar):" in UI
    assert "self.setStatusBar(I18nStatusBar(self))" in UI


def test_dynamic_history_and_header_patterns_are_supported():
    for source_fragment in (
        "Migration Report · User:",
        "RMU Follow-up: Open",
        "Lifecycle: Open",
        "Sign-off PDFs:",
        "Sign-off history:",
        "Delivery status:",
        "Site selected:",
        '("Status · ", "状态 · ")',
    ):
        assert source_fragment in I18N


def test_signal_mapping_workflow_presentation_is_localized():
    pairs = {
        "Open IOA File": "打开 IOA 文件",
        "Signal Mapping Review is not available": "信号映射审核当前不可用",
        "Analog": "模拟量",
        "Status/Cmd": "状态/命令",
        "Need Action Summary": "需处理汇总",
        "ADMS Implementation Summary": "ADMS 实现汇总",
        "Signal Mapping Review unavailable": "信号映射审核不可用",
    }
    for english, chinese in pairs.items():
        assert f'"{english}": "{chinese}"' in I18N


def test_engineering_source_contract_is_still_language_neutral():
    # Source role and physical source names are intentionally not localized.
    assert '"SE Equipment": "SE Equipment"' in I18N
    assert '"SE Equipment List": "SE Equipment List"' in I18N
    for name in ("SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"):
        assert f'"{name}": "' not in I18N or f'"{name}": "{name}"' in I18N


def test_static_visible_english_literals_are_covered_by_zh_dictionary():
    """Guard against adding a literal English UI caption without zh-CN text.

    This intentionally scans presentation constructors, widget text/tooltips,
    headers and common dialogs. Runtime-composed f-strings are covered by the
    dedicated dynamic-pattern tests above. Physical engineering/source tokens
    remain an explicit allow-list.
    """
    import ast
    import re

    i18n_tree = ast.parse(I18N)
    translations: dict[str, str] = {}

    def add_dict(node):
        if not isinstance(node, ast.Dict):
            return
        for key, value in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                translations[key.value] = value.value

    for node in ast.walk(i18n_tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "ZH_CN":
            add_dict(node.value)
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "ZH_CN" for target in node.targets):
            add_dict(node.value)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "ZH_CN"
            and node.func.attr == "update"
            and node.args
        ):
            add_dict(node.args[0])

    ui_tree = ast.parse(UI)
    constructors = {"QLabel", "QPushButton", "PageHeader", "EmptyState", "QGroupBox", "QCheckBox", "QRadioButton", "QAction"}
    methods = {
        "setText", "setWindowTitle", "setPlaceholderText", "setToolTip", "setStatusTip",
        "addTab", "setHorizontalHeaderLabels", "setVerticalHeaderLabels", "showMessage",
    }
    dialog_methods = {
        "information", "warning", "critical", "question", "getText", "getMultiLineText",
        "getItem", "getOpenFileName", "getExistingDirectory", "getSaveFileName",
    }

    def literal_strings(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, (ast.List, ast.Tuple)):
            result = []
            for child in node.elts:
                result.extend(literal_strings(child))
            return result
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return literal_strings(node.left) + literal_strings(node.right)
        return []

    visible = []
    for node in ast.walk(ui_tree):
        if not isinstance(node, ast.Call):
            continue
        args = []
        if isinstance(node.func, ast.Name) and node.func.id in constructors:
            args = node.args[:1]
        elif isinstance(node.func, ast.Attribute) and node.func.attr in methods:
            if node.func.attr == "addTab" and len(node.args) >= 2:
                args = [node.args[1]]
            elif node.func.attr in {"setHorizontalHeaderLabels", "setVerticalHeaderLabels"}:
                args = node.args[:1]
            elif node.func.attr == "showMessage":
                args = node.args[-1:]
            else:
                args = node.args[:1]
        elif isinstance(node.func, ast.Attribute) and node.func.attr in dialog_methods:
            args = node.args[1:3]
        for arg in args:
            for text in literal_strings(arg):
                text = text.strip()
                if text and re.search(r"[A-Za-z]", text):
                    visible.append((node.lineno, text))

    allowed_exact = {
        "i", "e.g. RMU_FINAL", "CSV (*.csv)", "Excel Workbook (*.xlsx)", "PDF Files (*.pdf)",
        "SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD", "STANDARD", "RMU", "IOA",
        "CSV", "XLSX", "PDF", "project.db", "MIGRATION REPORT  ·  v",
        "NARI · SAUDI ADMS PROJECT · DATA MIGRATION", "RMU —", "Inputs:",
    }
    allowed_prefixes = ("Expressions: ", "e.g. ", "SE / ZENON", "ZENON-", "ADMS-")
    missing = []
    for line, text in visible:
        if text in translations or text in allowed_exact or text.startswith(allowed_prefixes):
            continue
        if re.fullmatch(r"[A-Z0-9_ ./\\*()\-]+", text) and len(text) < 60:
            continue
        missing.append((line, text))

    assert not missing, f"Untranslated literal UI strings: {missing}"


def test_embedded_runtime_tooltip_fragments_are_localized_safely():
    for english, chinese in {
        "Checked means the reviewer inspected this equipment and accepted it as passed.": "勾选表示审核人员已检查该设备，并确认其审核通过。",
        "Checked means the reviewer inspected this signal and accepted it as passed.": "勾选表示审核人员已检查该信号，并确认其审核通过。",
        "Double-click this row or click Map Fields to change mapping.": "双击此行或点击“字段映射”可修改映射。",
        "Right-click any cell to set Unreviewed / Closed / Needs Action for this equipment row.": "右键任意单元格可将该设备行设置为未审核 / 已关闭 / 需处理。",
    }.items():
        assert f'("{english}", "{chinese}")' in I18N


def test_dynamic_zh_en_roundtrip_for_history_export_and_embedded_help(monkeypatch):
    """Exercise tr() without requiring the Qt runtime in the CI container."""
    import importlib.util
    import sys
    import types

    core = types.ModuleType("PySide6.QtCore")
    gui = types.ModuleType("PySide6.QtGui")
    widgets = types.ModuleType("PySide6.QtWidgets")
    package = types.ModuleType("PySide6")

    class FakeQSettings:
        def value(self, *_args, **_kwargs):
            return "en"

    core.QSettings = FakeQSettings
    gui.QAction = type("QAction", (), {})
    for class_name in (
        "QAbstractButton", "QComboBox", "QGroupBox", "QLabel", "QLineEdit",
        "QTabWidget", "QTableWidget", "QWidget",
    ):
        setattr(widgets, class_name, type(class_name, (), {}))

    monkeypatch.setitem(sys.modules, "PySide6", package)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", core)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", gui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", widgets)

    spec = importlib.util.spec_from_file_location("v08164_i18n_runtime", ROOT / "src/migration_report_tool/ui/i18n.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    samples = (
        "RMU Follow-up: Open 1 · Closed 2",
        "Lifecycle: Open 3 · Closed 4",
        "Sign-off PDFs: 5 · Signed: 2",
        "Sign-off history: 5 generated · 2 signed · latest revision R01",
        "Delivery status: VALIDATION REQUIRED · Export is available as a review draft; complete Human Review before formal handover.",
        "foo\nChecked means the reviewer inspected this equipment and accepted it as passed.",
        "bar\nDouble-click this row or click Map Fields to change mapping.",
        "Showing RMUs containing 7 mismatched signal row(s)",
        "Signal Review updated for 4 row(s): CLOSED",
        "Source change detected · SE, ADMS DB · refreshing in background",
        "Signal Mapping Review ready · 248 row(s)",
        "ADMS DB: field mapping saved and affected data refreshed · global mapping active",
        "Added 2 source file(s) · Run Validation when ready",
        "Equipment Review updated: 5 row(s) → CLOSED",
        "Source loaded · SE, ADMS DB · Map Fields required before Validation",
    )
    for english in samples:
        chinese = module.tr(english, module.LANG_ZH_CN)
        assert chinese != english
        assert module.tr(chinese, module.LANG_EN) == english
