"""Lightweight runtime UI localization for the desktop application.

The migration data contract, field keys, source headers and persisted review
states remain language-neutral/English tokens.  Only presentation strings are
translated.  This deliberately avoids putting localized text into project.db or
using translated combo labels as business keys.
"""
from __future__ import annotations

import re
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTabWidget,
    QTableWidget, QWidget,
)

LANG_EN = "en"
LANG_ZH_CN = "zh_CN"
SUPPORTED_LANGUAGES = ((LANG_EN, "English"), (LANG_ZH_CN, "中文（简体）"))
_RUNTIME_LANGUAGE: str | None = None


def normalize_language(value: object) -> str:
    token = str(value or "").strip().replace("-", "_")
    return LANG_ZH_CN if token.lower() in {"zh", "zh_cn", "chinese", "中文", "简体中文"} else LANG_EN


def set_current_language(value: object) -> str:
    """Set the process-local presentation language immediately.

    QSettings remains the persistence layer, but repaint-time code must not wait
    for the settings backend to flush before observing a language switch.
    """
    global _RUNTIME_LANGUAGE
    _RUNTIME_LANGUAGE = normalize_language(value)
    return _RUNTIME_LANGUAGE


def current_language() -> str:
    if _RUNTIME_LANGUAGE is not None:
        return _RUNTIME_LANGUAGE
    return normalize_language(QSettings().value("ui/language", LANG_EN))


# Engineering/source field names intentionally remain English when that is the
# clearest cross-company contract.  The dictionary focuses on navigation,
# workflow actions, help text and customer-facing review terminology.
ZH_CN: dict[str, str] = {
    # Shell / navigation
    "Project Overview": "项目总览",
    "Site Data Sources": "站点数据源",
    "Equipment Data Review": "设备数据审核",
    "RMU Data Review": "环网柜数据审核",
    "Signal Mapping Review": "信号映射审核",
    "Change Audit": "变更审计",
    "Review Versions": "审核版本",
    "Site History": "站点历史",
    "Report Export": "报告导出",
    "Settings": "设置",
    "PROJECT DATA": "项目数据",
    "No site selected": "未选择站点",
    "Migration Report · Select a site to validate and review migration data": "迁移报告 · 请选择站点进行数据校验与审核",
    "STATUS · SOURCES INCOMPLETE": "状态 · 数据源不完整",
    "Refresh Sources": "刷新数据源",
    "Run Validation": "运行校验",
    "Ready": "就绪",

    # Page headers
    "Saudi ADMS Migration Overview": "Saudi ADMS 迁移总览",
    "NARI delivery view for data-source readiness, automatic validation, human Review progress and formal Migration Report handover.": "NARI 交付视图：数据源就绪状态、自动校验、人工审核进度以及正式迁移报告交付。",
    "Choose the file each App table reads and review the exact fields used by this module.": "选择每个 App 表读取的文件，并检查本模块实际使用的字段映射。",
    "Review every equipment type across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD. Every detected equipment type uses the same Analysis, Review Status, Resolution, Comments and Needs Action lifecycle workflow.": "对 SE、ZENON DB、ZENON SLD、ADMS DB 和 ADMS SLD 中的所有设备类型进行统一审核。所有识别到的设备类型都使用同一套分析、审核状态、处理决议、备注和 Needs Action 流程。",
    "Review RMU consistency and close or flag exceptions.": "审核环网柜数据一致性，并关闭或标记异常。",
    "Review signal mapping grouped by RMU.": "按环网柜分组审核信号映射。",
    "Read-only trace of migration-review corrections, structured RMU Resolutions, display-name changes and Signal Mapping comments saved for project handover and traceability.": "只读追踪迁移审核修改、结构化 RMU 处理决议、显示名称变更和信号映射备注，用于项目交付与追溯。",
    "Create named Saudi ADMS migration-review snapshots before handover, rework or another migration cycle.": "在交付、返工或下一轮迁移前创建命名的 Saudi ADMS 审核快照。",
    "Persistent station revisions, issue/action records and signed PDF handover history. These records live in Project Data and survive application upgrades.": "持久保存站点版本、问题/处理记录及已签字 PDF 交付历史；这些数据存放在项目数据中，升级程序不会丢失。",
    "Generate the formal Excel migration-review workbook and a printable station modification / issue-closure PDF for signature.": "生成正式 Excel 迁移审核工作簿以及可打印签字的站点修改/问题关闭 PDF。",
    "Application identity, persistent Project Data, Site Repository, STANDARD management and deployment settings.": "应用信息、持久化项目数据、站点数据仓库、STANDARD 管理及部署设置。",

    # Common actions
    "Open Workspace": "打开工作区",
    "Select Workspace": "选择工作区",
    "Workspace": "工作区",
    "Open Site Folder": "打开站点目录",
    "Map Fields...": "字段映射...",
    "Assign Source...": "指定数据源...",
    "Show All": "显示全部",
    "Clear Selection": "清除选择",
    "Set Status": "设置状态",
    "Columns": "列设置",
    "Reset Columns": "重置列",
    "Search selected column...": "搜索所选列...",
    "All Columns": "所有列",
    "Update STANDARD...": "更新 STANDARD...",
    "Refresh Mapping": "刷新映射",
    "New Revision": "新建版本",
    "Add Issue / Action": "新增问题 / 处理",
    "Export Sign-off PDF": "导出签字 PDF",
    "Export Migration Report": "导出迁移报告",
    "Change...": "更改...",
    "Open Folder": "打开目录",
    "Open Setup Guide": "打开设置向导",
    "Save Detection Rules": "保存识别规则",
    "Use Selected": "使用所选版本",
    "Upload STANDARD(s)...": "上传 STANDARD...",
    "Use Built-in": "使用内置版本",
    "Open Current": "打开当前文件",
    "Save": "保存",
    "Cancel": "取消",
    "OK": "确定",
    "Close": "关闭",
    "Configure Equipment Comparison": "配置设备数据对比",
    "Configure Equipment Comparison...": "配置设备数据对比...",
    "Map Signal Fields...": "映射信号字段...",
    "— Not compared —": "— 不参与比较 —",
    "Key not set": "未设置主键",
    "Equipment Data Review · Configurable Sources": "设备数据审核 · 可配置数据源",
    "Add any number of CSV/XLSX/XLSM tables. For every table choose the key/index field used to join rows. Then define exactly which fields should be compared. All physical columns are shown by default; uncheck Show to hide a field for this site only. Source titles default to filenames and can be renamed. Filenames, worksheets and physical field names are never fixed by the App.": "可添加任意数量的 CSV/XLSX/XLSM 表。每个表分别选择用于关联行的主键/索引字段，再自行定义需要比较的字段。所有物理字段默认全部显示；取消 Show 可仅在当前现场隐藏字段。数据源标题默认使用文件名，也可以修改；程序不再写死文件名、工作表名或物理字段名。",
    "Source Tables": "数据源表",
    "Add File(s)": "添加文件",
    "Add Comparison Source Tables": "添加对比数据源表",
    "Equipment Comparison": "设备数据对比",
    "Remove": "移除",
    "Selected Source": "当前数据源",
    "Module Title": "模块标题",
    "Source File": "数据源文件",
    "Replace File...": "替换文件...",
    "Worksheet": "工作表",
    "Header Row": "表头行",
    "Key / Index Field": "主键 / 索引字段",
    "Physical Fields · Show / Hide": "物理字段 · 显示 / 隐藏",
    "Every detected source field is visible by default. Hiding a field changes only this site's Equipment Data Review presentation; it does not remove the field from comparison rules.": "识别到的所有源字段默认全部显示。隐藏字段只影响当前现场的设备数据审核显示，不会从比较规则中删除该字段。",
    "Show": "显示",
    "Physical Field": "物理字段",
    "Comparison Rules": "比较规则",
    "Normalization": "归一化方式",
    "Default Comparison Mode": "默认比较模式",
    "Comparison Mode": "比较模式",
    "Automatic by field title": "按字段标题自动识别",
    "FEEDER smart · station + number": "智能 FEEDER · 站号 + 馈线号",
    "SMART aliases · NORMAL / NONSMART": "SMART 别名 · NORMAL / NONSMART",
    "NOP contains · any NOP = NOP": "NOP 包含判断 · 含 NOP 即为 NOP",
    "Text / exact": "文本 / 精确比较",
    "FEEDER smart normalization decodes station + feeder number, including ADMS AH3NN values such as JED-CTL-AJWD-AH331 → AJWD-31.": "智能 FEEDER 归一化会解析站号和馈线号，包括将 ADMS 的 AH3NN 值（如 JED-CTL-AJWD-AH331）转换为 AJWD-31。",
    "Apply Smart FEEDER / SMART / NOP": "应用智能 FEEDER / SMART / NOP",
    "Apply site-local smart normalization to FEEDER/FDR, SMART and NOP rules.": "为当前站点的 FEEDER/FDR、SMART 和 NOP 规则应用智能归一化。",
    "Use site default": "使用站点默认模式",
    "Strict equality · blank participates": "严格一致 · 空值参与",
    "Ignore blank values": "忽略空值",
    "This is the site default. Each comparison field can inherit it or override it independently.": "这是当前站点的默认比较模式。每个比较字段可以继承默认模式，也可以单独覆盖。",
    "Each row is one Analysis field. Choose which physical field from each source participates and choose its comparison mode. Strict mode treats blank as a real value; Ignore Blank keeps the legacy behavior and excludes blank values from the comparison.": "每一行代表一个分析比较字段。请为各数据源选择参与比较的物理字段，并选择该字段的比较模式。严格模式会把空值作为真实比较值；忽略空值模式保留原来的宽松逻辑，比较时排除空值。",
    "Each row is one Analysis field. Choose which physical field from each source participates. Blank bindings are ignored. For each joined key, every bound source participates: all values equal = TRUE (including all blank); any blank/non-blank mix or other difference = FALSE.": "每一行代表一个分析比较字段。为每个数据源选择参与比较的物理字段，未绑定的数据源不参与。对每个已关联主键，所有已绑定数据源都参与比较：全部值相同 = TRUE（包括全部为空）；只要出现空值与非空值混合，或任意值不同 = FALSE。",
    "Comparison Field": "比较字段",
    "Add Comparison Field": "添加比较字段",
    "Remove Rule": "删除规则",
    "Save & Rebuild Review": "保存并重建设备审核",
    "One-time Site Transfer Package": "一次性站点迁移包",
    "Unified Site Folder": "统一站点目录",
    "Each site keeps its source files, project.db, Comments and Checked records in one folder. Copy the complete site folder to another workstation to continue the review.": "每个站点都会将源文件、project.db、Comments 和 Checked 记录保存在同一个目录中。将整个站点目录复制到其他工作站即可继续审核。",
    "At any point, this one-time action can copy the current site's source Excel files into its unified site folder. The unified site preserves Comments, Checked, Review Status, Resolution and Audit history. Original source files are never deleted.": "无论当前审核处于什么状态，都可以执行此一次性操作，将站点源 Excel 文件复制到统一站点目录。统一站点会保留 Comments、Checked、审核状态、处理决定和审计历史。原始源文件不会被删除。",
    "Prepare Transfer Package (One-time)": "准备迁移包（仅一次）",
    "Transfer Package Already Prepared": "迁移包已准备",
    "Site Folder Already Unified": "站点目录已统一",
    "Copy the current site's live source files into source_files for one-time transfer to another machine.": "将当前站点的源文件复制到 source_files 目录，用于一次性迁移到其他机器。",
    "Select a site before preparing the one-time unified site package.": "请先选择站点，再准备一次性统一站点迁移包。",
    "Site Transfer Package": "站点迁移包",
    "This one-time action can be performed at any review status. It will copy the current site's CSV/Excel source files into source_files, keep all existing review records, and update source links to local relative paths.\n\nOriginal source files will not be deleted or changed. Continue?": "无论当前审核处于什么状态，都可以执行此一次性操作。程序会将当前站点的 CSV/Excel 源文件复制到 source_files 目录，保留所有已有审核记录，并将源文件链接更新为本地相对路径。\n\n原始源文件不会被删除或修改。是否继续？",
    "Prepare Site Transfer Package": "准备站点迁移包",
    "Site Transfer Package Ready": "站点迁移包已准备",
    "Close the application, copy this entire site folder to the other machine, then select this folder as Source Workspace. The embedded project.db will provide the existing Comments and Checked records.": "关闭程序后，将整个站点文件夹复制到其他机器，再将该文件夹选择为源工作区。内置的 project.db 会提供已有的 Comments 和 Checked 记录。",
    "Replace Comparison Source File": "替换对比数据源文件",
    "Field / Analysis title:": "字段 / 分析标题：",
    "Configuration requires attention:": "配置需要处理：",
    "Comparison Configuration": "对比配置",
    "Fix the following before saving:": "保存前请修正以下问题：",
    "Configure Sources...": "配置数据源...",
    "Configurable Equipment Comparison": "可配置设备数据对比",
    "Any CSV / Excel": "任意 CSV / Excel",
    "Add any number of files; each site has its own configuration": "可添加任意数量文件；每个现场独立配置",
    "Choose each table's Key / Index and define any comparison fields. All source fields show by default.": "为每个表选择主键 / 索引，并定义任意比较字段；所有源字段默认显示。",
    "NOT CONFIGURED": "未配置",
    "Open the site-local configurable comparison editor": "打开当前现场的可配置对比编辑器",
    "Index / Key": "索引 / 主键",
    "Scope": "范围",
    "Configure Sources": "配置数据源",
    "Select a physical Source Field for every required SYSTEM field before applying.": "应用前请为每个必需的 SYSTEM 字段选择对应的物理源字段。",
    "SYSTEM mappings are unlocked. Use Edit System Mappings to bind every required semantic to a physical Source Field.": "SYSTEM 映射已解锁。请使用“编辑系统映射”将每个必需语义绑定到物理源字段。",
    "Click Unlock System Mappings... to map a non-standard physical header to the missing required SYSTEM field.": "点击“解锁系统映射...”可将非标准物理表头映射到缺失的必需 SYSTEM 字段。",
    "Remove Source": "移除数据源",
    "Review draft cannot be signed": "审核草稿不能签字",
    "The selected PDF was generated as a REVIEW DRAFT while Validation or Human Review was incomplete.\n\nRun Validation, complete the required review, and generate a formal sign-off PDF before attaching a signed copy.": "所选 PDF 是在校验或人工审核尚未完成时生成的 REVIEW DRAFT。\n\n请先运行校验并完成必要审核，再生成正式签字 PDF 后关联已签字文件。",

    # Review / state
    "Analysis": "分析",
    "Pass": "通过",
    "Has Issues": "存在问题",
    "Critical": "严重",
    "FALSE = mismatch": "FALSE = 不一致",
    "Remarks": "备注",
    "Resolution": "处理决议",
    "Row Locator": "行定位",
    "No.": "序号",
    "Checked": "已检查",
    "Review": "审核",
    "Unreviewed": "未审核",
    "Closed": "已关闭",
    "Needs Action": "需处理",
    "Equipment Case": "设备案例",
    "Time": "时间",
    "Case": "周期",
    "Status": "状态",
    "Issue": "问题",
    "Comments": "备注",
    "User": "用户",
    "RMU Action Tracking": "RMU 处理跟踪",
    "Open Full Lifecycle": "查看完整生命周期",
    "Shown only when the selected RMU has a formal Needs Action history. Signal tracking is intentionally excluded for now.": "仅当所选 RMU 存在正式的“需处理”历史时显示；当前暂不包含信号跟踪。",
    "The column name identifies which field failed; Review and Resolution stay neutral.": "列名表示发生不一致的字段；审核状态和处理决议本身保持中性。",
    "No validation data": "暂无校验数据",
    "Review 0 / 0 · Resolution 0 / 0 issues": "审核 0 / 0 · 问题处理决议 0 / 0",
    "Equipment Type": "设备类型",
    "All Equipment · ZENON SLD": "全部设备 · ZENON SLD",
    "All Equipment · Five Sources": "全部设备 · 五源数据",
    "Five Sources": "五源数据",
    "Source Coverage": "来源覆盖",
    "Sources": "来源数",
    "Missing Sources": "缺失来源",
    "ZENON SLD Quality": "ZENON SLD 数据质量",
    "ZENON SLD Inventory": "ZENON SLD 设备清单",
    "Data Quality": "数据质量",
    "Equipment Name": "设备名称",
    "Quality": "质量",
    "ATTENTION": "需关注",
    "REVIEW": "需复核",
    "OK": "正常",
    "Review Profile": "审核类型",
    "RMU (Active)": "RMU（当前启用）",
    "ALL REVIEWS": "全部审核状态",
    "UNREVIEWED": "未审核",
    "CLOSED": "已关闭",
    "NEEDS ACTION": "需处理",
    "ALL ANALYSIS": "全部分析结果",
    "PASSED": "通过",
    "ANY MISMATCH": "任意不一致",
    "1 ISSUE": "1 个问题",
    "2 ISSUES": "2 个问题",
    "MULTIPLE ISSUES": "多个问题",
    "CRITICAL": "严重",
    "NAME MISMATCH": "名称不一致",
    "FEEDER MISMATCH": "馈线不一致",
    "SMART MISMATCH": "SMART 不一致",
    "TYPE MISMATCH": "类型不一致",
    "IP MISMATCH": "IP 不一致",
    "LINK MISMATCH": "LINK 不一致",
    "ALL RMUS": "全部 RMU",
    "ISSUES ONLY": "仅显示问题",
    "ALL RESULTS": "全部结果",
    "MATCHED": "一致",
    "MISMATCHED": "不一致",
    "ZENON EXTRA": "仅 ZENON 存在",

    # Mapping dialog
    "App Column": "App 字段",
    "Source Field": "源字段",
    "Type": "类型",
    "SYSTEM · LOCKED": "SYSTEM · 已锁定",
    "SYSTEM · UNLOCKED": "SYSTEM · 已解锁",
    "SYSTEM · OPTIONAL": "SYSTEM · 可选",
    "USER": "用户字段",
    "Manual": "手动映射",
    "Exact": "精确匹配",
    "Built-in Alias": "内置别名",
    "Missing": "缺失",
    "Ambiguous": "存在歧义",
    "Mapped": "已映射",
    "Unmapped · blank": "未映射 · 空白",
    "Unlock System Mappings...": "解锁系统映射...",
    "System Mappings Unlocked": "系统映射已解锁",
    "Edit System Mappings...": "编辑系统映射...",
    "Edit System Mappings": "编辑系统映射",
    "System Mapping Assignments": "系统映射分配",
    "System Field": "系统字段",
    "Requirement": "要求",
    "Current Status": "当前状态",
    "Required": "必需",
    "System": "系统",
    "Apply System Mappings": "应用系统映射",
    "System Mapping Required": "需要系统映射",
    "Bind protected SYSTEM semantics to the current physical source headers. Use this when the file uses non-standard names such as DE_NAME instead of EQUIPMENT. This does not add phantom source columns: the main Map Fields table still mirrors the physical file exactly.": "将受保护的 SYSTEM 语义绑定到当前物理数据源表头。文件使用 DE_NAME 而不是 EQUIPMENT 等非标准列名时，可在这里手工指定。此操作不会生成虚假源列，主字段映射表仍与物理文件列完全一致。",
    "Required SYSTEM fields must resolve before Save. Manual selections are stored as explicit source-header bindings; Auto continues to use the declared aliases when they exist.": "保存前必须完成所有必需 SYSTEM 字段的映射。手工选择会保存为明确的源表头绑定；Auto 在存在已声明别名时仍继续自动识别。",
    "System mappings are UNLOCKED for this dialog. Use Edit System Mappings to bind missing or non-standard source headers; Save will ask for confirmation again.": "当前窗口已解锁系统映射。可使用“编辑系统映射”绑定缺失或非标准源字段；保存时仍会再次确认。",
    "Edit every protected SYSTEM semantic, including required fields that have no automatic alias match in the current physical header.": "编辑全部受保护的 SYSTEM 语义，包括当前物理表头中没有自动别名匹配的必需字段。",
    "Protected system mappings unlocked. Bind any missing SYSTEM field to a verified physical source header before Save.": "系统映射已解锁。保存前请将缺失的 SYSTEM 字段绑定到已确认的物理源字段。",
    "SYSTEM mappings updated in this dialog. Review the promoted rows, then Save to persist and refresh calculated data.": "当前窗口中的 SYSTEM 映射已更新。请检查已提升为系统字段的源列，然后保存以持久化并刷新计算数据。",
    "+ Add App Column": "+ 新增 App 字段",
    "Show": "显示",
    "Show All Fields": "显示全部字段",
    "Hide Optional Fields": "隐藏全部可选字段",
    "Show every optional and USER App field in Equipment Data Review. SYSTEM calculation fields are always shown.": "在设备数据审核中显示所有可选字段和 USER App 字段；SYSTEM 计算字段始终显示。",
    "Hide every optional and USER App field at once. SYSTEM calculation fields stay visible and cannot be hidden.": "一次隐藏所有可选字段和 USER App 字段；SYSTEM 计算字段始终保持显示且不能隐藏。",
    "Show this App field in Equipment Data Review. Uncheck to hide it without deleting its mapping or App definition.": "在设备数据审核中显示此 App 字段。取消勾选只会隐藏显示，不会删除字段映射或 App 字段定义。",
    "SYSTEM calculation field. It is always shown because it feeds matching, Analysis or validation.": "SYSTEM 计算字段会参与匹配、分析或校验，因此必须始终显示。",
    "SYSTEM calculation fields are always shown and cannot be hidden.": "SYSTEM 计算字段必须始终显示，不能隐藏。",
    "Application-global USER App column. Name and Source Field mapping remain saved even when the field is hidden.": "应用级全局 USER App 字段；即使隐藏，字段名称和源字段映射仍会保留。",
    "Presentation/reference field. Use the Show checkbox to hide or show it without deleting the field or mapping.": "展示 / 参考字段。可通过“显示”复选框隐藏或显示，不会删除字段或映射。",
    "Delete Column": "删除字段",
    "Move Column...": "移动字段...",
    "Restore Optional Columns": "恢复可选字段",
    "Reset Auto Mapping": "重置自动映射",
    "Unlock System Mappings": "解锁系统映射",
    "System calculation fields are protected. Their Source Field mapping feeds Analysis and validation across all sites.": "系统计算字段默认受保护，其源字段映射会用于所有站点的分析和校验。",
    "System mappings are UNLOCKED for this dialog only. Any protected mapping change will require confirmation again when you Save.": "系统映射仅在当前窗口中解锁；如果修改了受保护字段，保存时还会再次要求确认。",
    "Protected system mappings unlocked for this dialog. Verify each Source Field carefully before Save.": "当前窗口已解锁系统映射，请在保存前逐项确认源字段。",
    "SYSTEM · LOCKED fields are used by system-level Analysis, matching, and validation calculations.\n\nChanging a protected Source Field changes how that App Column is interpreted for ALL sites that use this source type. Only remap a system field when the new physical source column has been verified.\n\nUnlock protected system mappings for this dialog?": "SYSTEM · 已锁定字段会参与系统级分析、匹配和校验计算。\n\n修改受保护的源字段会改变该 App 字段在所有使用此数据源类型的站点中的解释方式。只有确认新的物理字段正确后才应重新映射。\n\n是否在当前窗口中解锁受保护的系统映射？",
    "Active source file:": "当前数据源文件：",
    "Equipment Data Review Columns": "设备数据审核列设置",
    "Choose visible Equipment Data Review columns": "选择设备数据审核中显示的列",
    "Review View": "审核视图",
    "Full View": "完整视图",
    "System Required": "系统必需字段",
    "Every mapped App field can be shown or hidden here. SYSTEM calculation fields are always visible because they feed matching, Analysis or validation. Optional built-in fields and USER App columns are presentation choices only and are hidden by default until you choose to show them. New App fields appear automatically and also start hidden by default. No source mapping, SQLite review data or exported report history is deleted by changing this view.": "这里可以选择显示或隐藏每个已映射的 App 字段。参与匹配、分析或校验的 SYSTEM 计算字段必须始终显示，不能隐藏。可选内置字段和 USER App 字段仅影响界面展示，默认全部隐藏，按需手动显示。以后新增的 App 字段会自动出现，并且默认也保持隐藏。修改这里的显示不会删除源字段映射、SQLite 审核数据或历史导出记录。",
    "Equipment Data Review column view saved": "设备数据审核列显示设置已保存",
    "Column width fitted to current content": "列宽已按当前内容自动适配",
    "Drag the header divider to resize; double-click the header to fit content": "拖动表头分隔线可调整列宽；双击表头可按内容自动适配",
    "Equipment Data Review columns reset: all current and future new columns are visible by default": "设备数据审核列已重置：当前列以及以后新增的列默认都会显示",
    "Show all protected system columns plus Remarks and Resolution / Comments.": "显示所有受保护的系统字段，以及备注和处理决议 / Comments。",
    "Show every current App field in Equipment Data Review.": "显示设备数据审核中当前所有 App 字段。",
    "Show only fields that the application requires for identity, source coverage and system calculations.": "仅显示设备标识、数据源覆盖和系统计算所必需的字段。",
    "Required by system calculation / matching / validation. This column cannot be hidden.": "该字段参与系统计算 / 匹配 / 校验，不能隐藏。",
    "Presentation-only column. Hide/show does not change source mapping or calculation logic.": "仅控制界面显示；隐藏或显示不会改变源字段映射或计算逻辑。",
    "All columns in this group are required by the system.": "该分组中的所有字段均为系统必需字段。",
    "All Equipment": "全部设备",
    "Equipment Action Tracking": "设备处理跟踪",
    "Shown only when the selected equipment has a formal Needs Action history. Signal tracking is intentionally excluded for now.": "仅当所选设备存在正式 Needs Action 历史时显示；当前不包含信号级跟踪。",

    # Source repository
    "Sites": "站点",
    "App Table": "App 表",
    "Source File": "数据源文件",
    "Sheet": "工作表",
    "Source Sheet": "数据源工作表",
    "Active sheet:": "当前工作表：",
    "File Path": "文件路径",
    "Fields Used in This Module (App → Source)": "本模块使用字段（App → 源字段）",
    "Unmapped Files": "未映射文件",
    "READY": "就绪",
    "PARTIAL": "部分就绪",
    "MAPPING REQUIRED": "需要字段映射",

    # Settings
    "Workspace & Project Data Setup": "工作区与项目数据设置",
    "Application": "应用",
    "Current user": "当前用户",
    "Site Repository": "站点数据仓库",
    "Project Data": "项目数据",
    "Legacy Project Data (compatibility)": "旧版项目数据（兼容用）",
    "Data policy": "数据策略",
    "Source Detection Rules": "数据源识别规则",
    "Signal Mapping STANDARD reference": "信号映射 STANDARD 参考",
    "Available STANDARD workbooks:": "可用 STANDARD 工作簿：",
    "Interface Language": "界面语言",
    "Language changes are saved for future launches. Technical field names and source headers remain unchanged so mapping/audit data is language-neutral.": "语言设置会保存并在下次启动继续使用。技术字段名和源文件表头保持不变，确保映射与审计数据不受语言影响。",
    "Setup complete. Each site's project.db is stored inside that site folder and will travel with its source files.": "设置已完成。每个站点的 project.db 都保存在站点目录内，会与源文件一起迁移。",
    "Source Workspace is not configured or is unavailable. Choose the folder that contains the site source files. Each site will keep its own project.db.": "数据源工作区未配置或不可用。请选择包含站点源文件的目录；每个站点都会使用自己的 project.db。",
    "Source Workspace / Site Repository is read-only during normal validation. New and migrated sites keep project.db, project.json, source_files and reports together inside each site folder. The separate Project Data location is retained only as legacy compatibility storage for importing older records. Review/Closed/Needs Action, Comments, Resolution, Change Audit, named revisions and issue/action records remain in project.db and survive application upgrades. Future SQLite schema upgrades are forward-only and create a backup before changing project.db. Automatic validation and review behavior remain unchanged.": "正常校验期间，数据源工作区 / 站点数据仓库为只读。新站点和已迁移站点都会将 project.db、project.json、source_files 和 reports 放在各自站点目录内。分离的项目数据目录仅作为导入旧版记录的兼容存储保留。Review/Closed/Needs Action、备注、处理决议、变更审计、命名版本和问题/处理记录都保存在 project.db 中，并在程序升级后保留。未来 SQLite 数据库结构升级仅向前兼容，并会在修改 project.db 前自动备份；自动校验和审核业务逻辑保持不变。",
    "Recommended filenames are not mandatory. Configure comma-separated filename keywords here; the detector also checks CSV/XLSX column structure. Ambiguous files remain unmapped until assigned manually.": "推荐文件名不是强制要求。可在此配置以逗号分隔的文件名关键字；程序也会检查 CSV/XLSX 的列结构。无法明确识别的文件会保持未映射状态，直到用户手工指定。",
    "Signal Mapping Review and every formal export use the explicitly selected application-wide STANDARD workbook. You may keep multiple validated STANDARD versions in the library. Uploading never changes the active version automatically; choose the workbook below and click Use Selected. Site Repository files are never modified.": "信号映射审核和所有正式导出都使用用户明确选择的应用级 STANDARD 工作簿。STANDARD 库可以保留多个已验证版本；上传新文件不会自动切换当前版本，请在下方选择工作簿并点击“使用所选版本”。站点数据仓库中的文件不会被修改。",
    "comma-separated filename keywords": "以逗号分隔的文件名关键字",
    "The active STANDARD is chosen manually. The application never switches to a newer file automatically.": "当前 STANDARD 由用户手工选择，程序不会自动切换到较新的文件。",
    "Choose the read-only Source Workspace and confirm the writable Project Data Storage location before starting site validation.": "开始站点校验前，请选择只读的数据源工作区，并确认可写的项目数据存储位置。",
    "Source Workspace is not configured or is unavailable. Choose the folder that contains the site source files.": "数据源工作区尚未配置或当前不可用，请选择包含站点数据源文件的文件夹。",
    "Not configured": "未配置",
    "Legacy User Override": "旧版用户覆盖",
    "Built-in": "内置",
    "Upload / Replace STANDARD... supports selecting multiple workbooks; same-name replacement requires confirmation.": "上传 / 替换 STANDARD 支持一次选择多个工作簿；同名文件替换前需要确认。",

    # Misc dashboard / export
    "Migration Workflow": "迁移流程",
    "Select a site to begin": "选择站点后开始",
    "1  Data Sources": "1  数据源",
    "2  Validation": "2  校验",
    "3  Human Review": "3  人工审核",
    "4  Migration Report": "4  迁移报告",
    "Equipment Data Review · RMU Profile": "设备数据审核 · RMU 类型",
    "No RMU validation loaded": "尚未加载 RMU 校验结果",
    "Total RMUs": "RMU 总数",
    "With Issues": "存在问题",
    "Closed / Issues": "已关闭 / 问题",
    "Review progress: 0 / 0 · 0%": "审核进度：0 / 0 · 0%",
    "Unified site review workbook": "统一站点审核工作簿",
    "Saudi ADMS Site: —": "Saudi ADMS 站点：—",
    "Delivery status: —": "交付状态：—",
    "Report folder: —": "报告目录：—",
}

# v0.8.156 bilingual coverage for dashboard, source repository and the generic
# all-equipment review workflow. Engineering acronyms and physical source
# headers intentionally remain unchanged.
ZH_CN.update({
    "Organization": "组织",
    "Project": "项目",
    "Workstream": "工作流",
    "Deliverable": "交付物",
    "Current Site": "当前站点",
    "Not selected": "未选择",
    "Setup required": "需要完成设置",
    "Configure Now": "立即配置",
    "Open Settings": "打开设置",
    "Current Migration Site": "当前迁移站点",
    "Active Data Sources": "当前数据源",
    "Latest version: —": "最新版本：—",
    "Equipment Data Review": "设备数据审核",
    "Equipment Type": "设备类型",
    "Device Type": "设备类型",
    "Equipment Type / Subtype": "设备类型 / 子类型",
    "Subtype": "子类型",
    "Feeder": "馈线",
    "Feeder / Scope": "馈线 / 范围",
    "Station": "站点",
    "Brand": "品牌",
    "Screen / Picture": "画面 / 图纸",
    "Function Location": "功能位置",
    "Resolution / Comments": "处理决议 / 备注",
    "Resolution / Comment": "处理决议 / 备注",
    "Source Coverage": "来源覆盖",
    "Sources": "来源数",
    "Missing Sources": "缺失来源",
    "Index": "索引",
    "Row Locator": "行定位",
    "Equipment Name": "设备名称",
    "All Equipment": "全部设备",
    "All Equipment · Five Sources": "全部设备 · 五源数据",
    "Five Sources": "五源数据",
    "Search site...": "搜索站点...",
    "Search RMU...": "搜索 RMU...",
    "Search signal...": "搜索信号...",
    "Review Signal Mismatches": "审核信号不一致",
    "Review RMU Issues": "审核 RMU 问题",
    "Run Validation First": "请先运行校验",
    "No RMU Issues": "无 RMU 问题",
    "No Signal Mismatches": "无信号不一致",
    "No equipment validation loaded": "尚未加载设备校验结果",
    "No Signal Mapping validation loaded": "尚未加载信号映射校验结果",
    "Equipment Review by Type": "按设备类型审核",
    "Total": "总数",
    "With Issues": "存在问题",
    "Review Progress": "审核进度",
    "Needs Action": "需处理",
    "Closed": "已关闭",
    "Unreviewed": "未审核",
    "Review": "审核",
    "Analysis": "分析",
    "Remarks": "备注",
    "Resolution": "处理决议",
    "Checked": "已检查",
    "No analysis": "无分析结果",
    "No source coverage": "无来源覆盖",
    "Validation Required": "需要校验",
    "SOURCES INCOMPLETE": "数据源不完整",
    "VALIDATION REQUIRED": "需要校验",
    "ACTION REQUIRED": "需要处理",
    "READY FOR EXPORT": "可导出",
    "REVIEW PENDING": "等待审核",
    "MISSING": "缺失",
    "Selected Version": "已选版本",
    "Manual Import": "手工导入",
    "Site Repository": "站点数据仓库",
    "Site Repository · Latest Version": "站点数据仓库 · 最新版本",
    "Workspace snapshot": "工作区快照",
    "Not available": "不可用",
    "No unmapped supported files": "没有未映射的支持文件",
    "SE Equipment": "SE Equipment",
    "Select a site": "选择站点",
    "Choose a repository root, then select a detected site.": "请选择工作区，然后选择已识别的站点。",
    "Review every equipment type across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD. Every detected equipment type uses the same Analysis, Review Status, Resolution, Comments and Needs Action lifecycle workflow.": "对 SE、ZENON DB、ZENON SLD、ADMS DB 和 ADMS SLD 中的所有设备类型进行审核。所有识别到的设备类型统一使用分析、审核状态、处理决议、备注以及需处理生命周期流程。",
    "Every equipment type is reviewed across SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD using the same Analysis / Resolution / Comments / lifecycle workflow.": "所有设备类型均在 SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD 五个来源中审核，并统一使用分析 / 处理决议 / 备注 / 生命周期流程。",
    "Every equipment type uses the five-source Analysis plus Unreviewed / Closed / Needs Action, Resolution, Comments and lifecycle workflow.": "所有设备类型统一使用五源分析，以及未审核 / 已关闭 / 需处理、处理决议、备注和生命周期流程。",
    "Fields Used in This Module (App → Source)": "本模块使用字段（App → 源字段）",
    "App Table": "App 表",
    "Source File": "数据源文件",
    "File Path": "文件路径",
    "Sheet": "工作表",
    "Last scan": "上次扫描",
    "Unmapped Files": "未映射文件",
})


# v0.8.156 final bilingual coverage for runtime dashboard/source/review text.
ZH_CN.update({
    "Search site...": "搜索站点...",
    "Review RMU Issues": "审核 RMU 问题",
    "Review Equipment Issues": "审核设备问题",
    "No Equipment Issues": "没有设备问题",
    "Run Validation First": "请先运行校验",
    "Showing equipment with Analysis issues": "正在显示存在分析问题的设备",
    "Open Equipment Data Review and show all equipment with automatic Analysis issues.": "打开设备数据审核，并仅显示自动分析发现问题的设备。",
    "Selected Version": "已选版本",
    "Site Repository · Latest Version": "站点数据仓库 · 最新版本",
    "Workspace snapshot": "工作区快照",
    "Not available": "不可用",
    "Reference not available": "参考文件不可用",
    "Review Signal Mismatches": "审核信号不一致",
    "ADMS Points": "ADMS 点数",
    "Matched": "一致",
    "Mismatched": "不一致",
    "ZENON Extra": "ZENON 额外项",
    "Need Action": "需处理",
    "Review Progress": "审核进度",
    "Total": "总数",
    "Pass": "通过",
    "Equipment Type": "设备类型",
    "Device Type": "设备类型",
    "Source Coverage": "来源覆盖",
    "Missing Sources": "缺失来源",
    "All Equipment": "全部设备",
    "All Reviews": "全部审核状态",
    "All Analysis": "全部分析结果",
    "Set Equipment Review Status": "设置设备审核状态",
    "Equipment Review Comments": "设备审核备注",
    "Equipment Action Tracking": "设备处理跟踪",
    "No equipment validation loaded": "尚未加载设备校验结果",
    "Equipment Data Review is ready after source validation.": "完成数据源校验后即可进行设备数据审核。",
    "Every equipment type uses the same five-source review workflow.": "所有设备类型统一使用五源审核流程。",
    "READY": "就绪",
    "MISSING": "缺失",
    "PARTIAL": "部分就绪",
    "MAPPING REQUIRED": "需要字段映射",
    "ACTION REQUIRED": "需要处理",
    "REVIEW PENDING": "待审核",
    "SOURCES INCOMPLETE": "数据源不完整",
    "VALIDATION REQUIRED": "需要校验",
    "VALIDATION INCOMPLETE": "校验未完成",
    "READY FOR EXPORT": "可导出",
    "AUTO": "自动",
    "MANUAL": "手动",
    "Current Migration Site": "当前迁移站点",
    "Active Data Sources": "当前数据源",
    "Site Repository": "站点数据仓库",
    "Manual Import": "手动导入",
    "Site Repository": "站点数据仓库",
    "Review all equipment types across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD using the same review states, comments and lifecycle workflow.": "对 SE、ZENON DB、ZENON SLD、ADMS DB 和 ADMS SLD 五个来源中的所有设备类型执行统一审核状态、备注和生命周期流程。",
    "Each row is one real source table. CSV and Excel (.xlsx/.xlsm) are supported for every site source role. Physical filenames are not business constraints: manual assignment plus field mapping is authoritative, and explicit Refresh can discover arbitrary filenames by schema fields. Excel sheet defaults to AUTO (first usable sheet in workbook order) and can be pinned per site without changing the global field mapping. File Path shows the reviewer-facing location. Fields Used shows exactly which App fields this module reads from that file. Missing source fields stay blank. Changing one Source File re-reads only that table. Refresh Sources re-scans versions and re-reads changed files; Run Validation force re-reads all active files. While the App is open, live file metadata is watched and changed inputs are refreshed in the background.": "每一行对应一个真实数据源表。所有站点数据源均支持 CSV 和 Excel（.xlsx/.xlsm）。物理文件名不是业务约束：手动指定和字段映射具有最终权威性，显式刷新还可根据表结构识别任意文件名。Excel 工作表默认使用 AUTO（按工作簿顺序选择第一个可用工作表），也可按站点固定指定，且不会改变全局字段映射。文件路径显示审核人员实际使用的位置；本模块使用字段明确显示 App 字段与源字段的对应关系。缺失源字段保持为空。更换单个数据源文件时只重新读取该表；刷新数据源会重新扫描版本并读取有变化的文件；运行校验会强制重新读取所有有效数据源。应用运行期间还会监视文件元数据，并在输入发生变化时后台刷新。",
    "Equipment review backed by the authoritative all-equipment ZENON-SLD inventory. Every detected DeviceType uses the same five-source Analysis/Resolution/Comments/lifecycle workflow.": "设备审核以权威的全设备 ZENON-SLD 清单为基础。识别到的每一种 DeviceType 均使用相同的五源分析、处理决议、备注和生命周期流程。",
})

# v0.8.157 source-page translation hardening.  These are the exact strings
# currently rendered by Site Data Sources; keeping the complete prose here
# prevents later English copy edits from silently bypassing Chinese mode.
ZH_CN.update({
    "AUTO uses the source-preferred business sheet when available; otherwise it uses the first usable sheet in workbook order.": "AUTO 会优先使用该数据源配置的业务工作表；若不存在，则按工作簿顺序使用第一个可用工作表。",
    "Fields Used in This Module (App ← Source)": "本模块使用字段（App ← 源字段）",
    "Each row is one real source table. CSV and Excel (.xlsx/.xlsm) are supported for every site source role. Physical filenames are not business constraints: manual assignment plus field mapping is authoritative, and explicit Refresh can discover arbitrary filenames by schema fields. AUTO still uses published V versions / detection rules as convenient discovery hints. Click Source File to return to AUTO, pin a version, or browse any supported table. For Excel, Sheet defaults to AUTO (the source-preferred business sheet when available, otherwise the first usable sheet) and can be pinned per site without changing the global field mapping. File Path shows the reviewer-facing location. Fields Used shows exactly which App fields this module reads from that file. Missing source fields stay blank. Changing one Source File re-reads only that table. Refresh Sources re-scans versions and re-reads changed files; Run Validation force re-reads all active files. While the App is open, live file metadata is watched and changed inputs are refreshed in the background.": "每一行对应一个真实数据源表。所有站点数据源都支持 CSV 和 Excel（.xlsx/.xlsm）。物理文件名不是业务限制：手动指定数据源并完成字段映射后，该映射就是实际使用依据；主动刷新也可以根据字段结构识别任意文件名。AUTO 仍会优先参考已发布的 V 版本和数据源识别规则；点击‘数据源文件’可恢复 AUTO、固定某个版本或浏览任意受支持的表格文件。Excel 的工作表默认使用 AUTO：若该数据源配置了首选业务工作表则优先使用，否则按工作簿顺序选择第一个可用工作表；也可以按站点固定工作表，而且不会改变全局字段映射。‘文件路径’显示审核人员实际使用的文件位置；‘本模块使用字段’显示 App 字段与物理源字段的实际对应关系。缺失的源字段保持为空。更换一个数据源文件只重新读取该表；‘刷新数据源’会重新扫描版本并读取发生变化的文件；‘运行校验’会强制重新读取所有当前数据源。应用运行期间还会监视文件元数据，并在输入发生变化时自动后台刷新。",
    "Review every equipment type across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD. Every detected equipment type uses the same Analysis, Review Status, Resolution, Comments and Needs Action lifecycle workflow.": "对 SE、ZENON DB、ZENON SLD、ADMS DB 和 ADMS SLD 五个来源中的所有设备类型进行审核。识别到的每一种设备类型都统一使用分析、审核状态、处理决议、备注和‘需处理’生命周期流程。",
    "SE Equipment List": "SE Equipment List",
    "ZENON SLD Equipment Inventory": "ZENON SLD 设备清单",
    "0 sites": "0 个站点",
    "Site scope": "站点范围",
    "Files deliberately left unmapped because no source type was sufficiently certain.": "由于无法可靠判断数据源类型，这些文件暂时保持未映射。",
    "Map source fields to App columns, or add a new App column.": "将源字段映射到 App 字段，或新增 App 字段。",
    "Choose a workspace folder such as D:\\Workspace\\SS": "请选择工作区目录，例如 D:\\Workspace\\SS",
})

# Modal dialogs and review controls.  Static Qt dialogs are routed through the
# localized wrappers in main_window.py, while custom QDialog subclasses are
# translated automatically on show.
ZH_CN.update({
    "Equipment Review": "设备审核",
    "Equipment Resolution": "设备处理决议",
    "Save Equipment Resolution": "保存设备处理决议",
    "Add Equipment Review Comment": "新增设备审核备注",
    "Open Resolution / Comment...": "打开处理决议 / 备注...",
    "View Full Equipment Lifecycle...": "查看完整设备生命周期...",
    "Mark Unreviewed": "标记为未审核",
    "Mark Closed": "标记为已关闭",
    "New Review Comment": "新增审核备注",
    "Add Comment": "新增备注",
    "Continue from Latest": "从最新备注继续",
    "Latest Saved Comment (read-only)": "最新已保存备注（只读）",
    "No saved comment": "暂无已保存备注",
    "No previous equipment review comment has been recorded.": "尚未记录设备审核备注。",
    "Previous comments are immutable. Add a new comment below, or use Continue from Latest to copy the latest saved text into the new editor and extend it. Opening or cancelling this dialog never changes an existing comment.": "历史备注不可修改。请在下方新增备注，或点击“从最新备注继续”复制上一条内容后补充。打开或取消本窗口都不会改变已有备注。",
    "Enter a new review comment. Save adds one new history record; it never edits or deletes an earlier comment.": "请输入新的审核备注。保存后会新增一条历史记录，不会编辑或删除之前的备注。",
    "Tip: use Continue from Latest when the new review is an extension of the previous note. Use a blank New Review Comment only to cancel—blank Save is blocked so prior text cannot be accidentally cleared.": "提示：如果本次审核是在上一条备注基础上补充，请使用“从最新备注继续”。空白内容不能保存，因此不会误清除历史备注。",
    "Issue": "问题",
    "Source Values from Validation": "校验数据源值",
    "Customer Resolution / Agreed Action": "客户处理决议 / 约定措施",
    "Latest Customer Comment (read-only)": "最新客户备注（只读）",
    "New Customer Comment (Optional)": "新增客户备注（可选）",
    "Unresolved": "未处理",
    "Needs Action · correction required": "需处理 · 需要整改",
    "Accept Exception · no source correction": "接受例外 · 不修改源数据",
    "Others · custom resolution": "其他 · 自定义处理决议",
    "Save Resolutions": "保存处理决议",
    "Validation Required": "需要先校验",
    "Automatic Analysis": "自动分析",
    "Read-only field": "只读字段",
    "Source Mapping": "数据源字段映射",
    "Source Loaded · Mapping Required": "数据源已加载 · 需要字段映射",
    "Choose Active File": "选择当前文件",
    "Assign Source": "指定数据源",
    "Import Source File": "导入数据源文件",
    "Migration Validation complete": "迁移校验完成",
    "Migration Validation failed": "迁移校验失败",
    "Select Source Workspace": "选择数据源工作区",
    "Select Project Data Storage": "选择项目数据存储目录",
    "Select Project Data Folder": "选择项目数据目录",
    "Upload STANDARD workbook(s)": "上传 STANDARD 工作簿",
    "Set Signal Review Status": "设置信号审核状态",
    "Set Equipment Review Status": "设置设备审核状态",
    "Version Description": "版本说明",
    "What changed in this version?": "本版本有哪些变更？",
    "Revision Notes": "修订说明",
    "Describe the site work included in this revision.": "说明本次修订包含的站点工作。",
    "Version name": "版本名称",
    "New Site Revision": "新建站点修订",
    "Revision name": "修订名称",
    "Prepared By": "编制人",
    "Enter the name of the person preparing / exporting this report:": "请输入编制 / 导出本报告的人员姓名：",
    "Select a site first.": "请先选择站点。",
    "Select exactly one equipment row to open Resolution / Comment.": "请选择且仅选择一条设备记录以打开处理决议 / 备注。",
    "Select one or more cells / RMU rows first.": "请先选择一个或多个单元格 / 设备行。",
    "Select one or more cells / equipment rows first.": "请先选择一个或多个单元格 / 设备行。",
    "Read-only source": "只读数据源",
    "Mapping saved": "映射已保存",
    "Unsupported Source": "不支持的数据源",
    "Site required": "需要选择站点",
    "Workspace required": "需要选择工作区",
    "Save failed": "保存失败",
    "Export failed": "导出失败",
    "PDF export failed": "PDF 导出失败",
    "Attach failed": "附件关联失败",
})


# v0.8.164 comprehensive Simplified-Chinese presentation audit.
#
# Scope: all workflow/meta UI outside the physical source-data contract.  The
# five physical source names, source headers, App/internal field keys and table
# body audit values remain language-neutral so saved mapping/review data is not
# rewritten by a presentation-language change.
ZH_CN.update({
    # Global shell / runtime status
    "Data Migration": "数据迁移",
    "Migration Report": "迁移报告",
    "Automatically calculated from source readiness, validation and human Review progress.": "根据数据源就绪情况、校验结果和人工审核进度自动计算。",
    "Re-scan source versions and re-read only active files whose content changed. AUTO switches to the highest V version; pinned files remain pinned.": "重新扫描数据源版本，仅重新读取内容发生变化的当前文件。AUTO 会切换到最高 V 版本；已固定的文件保持不变。",
    "Force re-read every active source file, then run full RMU and Signal Mapping validation.": "强制重新读取所有当前数据源文件，然后执行完整的设备与信号映射校验。",
    "Loading...": "正在加载...",
    "Please wait while the current view is prepared.": "正在准备当前视图，请稍候。",
    "Site selected": "已选择站点",

    # Change Audit
    "What is the Audit Log?": "什么是变更审计？",
    "Whenever a reviewer changes RMU Data Review, Signal Mapping Review, source mapping or Resolution data, the application stores an immutable audit record. Module and Field are shown with business-facing names while the original internal field key remains available in the Field tooltip for technical traceability.": "当审核人员修改设备数据审核、信号映射审核、数据源映射或处理决议时，程序都会保存一条不可修改的审计记录。模块和字段使用业务显示名称，同时在字段提示中保留原始内部字段键，便于技术追溯。",
    "No audit records yet": "暂无变更审计记录",
    "Changes made in RMU Data Review or Signal Mapping Review will appear here automatically with original value, new value, reviewer and timestamp.": "设备数据审核或信号映射审核中的修改会自动记录在这里，包括原值、新值、审核人员和时间。",
    "Module": "模块",
    "Record": "记录",
    "Field": "字段",
    "Original Value": "原值",
    "New Value": "新值",
    "Reason": "原因",
    "Modified By": "修改人",
    "Modified At": "修改时间",

    # Review Versions
    "Save Version": "保存版本",
    "Version": "版本",
    "Description": "说明",
    "Created By": "创建人",
    "Created At": "创建时间",
    "No saved versions yet": "暂无已保存版本",
    "Save a named version before handover or another migration cycle. Version snapshots preserve RMU Data Review state, structured Resolutions and Signal Mapping review metadata.": "在交付或下一轮迁移前保存一个命名版本。版本快照会保留设备数据审核状态、结构化处理决议和信号映射审核元数据。",

    # Site History summary / revision history
    "Site: —": "站点：—",
    "Latest revision: —": "最新版本：—",
    "Issue / Action items: 0": "问题 / 处理项：0",
    "RMU Follow-up: Open 0 · Closed 0": "RMU 跟踪：未关闭 0 · 已关闭 0",
    "Lifecycle: Open 0 · Closed 0": "生命周期：未关闭 0 · 已关闭 0",
    "Audit records: 0": "审计记录：0",
    "Sign-off PDFs: 0": "签字 PDF：0",
    "Revision History": "版本历史",
    "Revision": "版本",
    "Snapshot Version": "快照版本",
    "Category": "类别",
    "Equipment": "设备",
    "Action Taken": "处理措施",
    "Result": "结果",
    "By": "处理人",
    "Updated": "更新时间",
    "Issue / Action Register": "问题 / 处理登记",
    "Formal Need Action lifecycle for both RMUs and Signals. Every new Needs Action opens a case; comments, RMU resolutions, Signal ADD/MODIFY/DELETE remarks, validation changes and the explicit close are appended to its timeline. Reopening a closed item creates a new case. Double-click a case to inspect every event.": "RMU 和信号统一使用正式的“需处理”生命周期。每次新的“需处理”都会创建一个案例；备注、RMU 处理决议、信号 ADD/MODIFY/DELETE 备注、校验变化以及明确关闭操作都会追加到时间线。已关闭项目再次进入“需处理”时会创建新的案例。双击案例可查看全部事件。",
    "Need Action Lifecycle": "需处理生命周期",
    "Case": "案例",
    "Point": "点号",
    "Signal": "信号",
    "Opened": "打开时间",
    "Opened By": "打开人",
    "Closed": "已关闭",
    "Closed By": "关闭人",
    "Participants": "参与人数",
    "Events": "事件数",
    "Last Activity": "最后活动时间",
    "Once an RMU enters Needs Action it stays in this follow-up register until that RMU is explicitly Closed. A later source refresh or Unreviewed reset does not silently remove the open follow-up item.": "RMU 一旦进入“需处理”，就会一直保留在该跟踪登记中，直到被明确设置为“已关闭”。后续刷新数据源或重置为“未审核”都不会自动删除尚未关闭的跟踪项。",
    "RMU Needs Action Tracking": "RMU 需处理跟踪",
    "First Needs Action": "首次需处理时间",
    "Last Needs Action": "最近需处理时间",
    "Closed At": "关闭时间",
    "Open Count": "打开次数",
    "Last Reason": "最近原因",
    "All existing edits from earlier application versions remain here. This is the same immutable per-site audit data used by Change Audit and the sign-off PDF snapshot.": "早期程序版本产生的所有已有修改都会保留在这里。这与“变更审计”和签字 PDF 快照使用的是同一份不可修改的站点审计数据。",
    "Change Audit History": "变更审计历史",
    "Attach Signed PDF": "关联已签字 PDF",
    "Open Selected PDF": "打开所选 PDF",
    "Generated PDF": "生成的 PDF",
    "Generated By": "生成人",
    "Generated At": "生成时间",
    "Signed PDF": "已签字 PDF",
    "Signed At": "签字时间",
    "PDF Sign-off History": "PDF 签字历史",

    # Report Export
    "Migration Report Export": "迁移报告导出",
    "The export contains exactly five sheets. Equipment Data Review is always exported from the App review model. Signal Mapping Review is exported when configured; otherwise its sheet is kept as a NOT CONFIGURED placeholder so Equipment export is never blocked. STANDARD is copied from the active application reference; Import Sources and Change Audit Log provide traceability.": "导出的工作簿固定包含五个工作表。设备数据审核始终由 App 审核模型生成；信号映射审核已配置时导出，未配置时保留 NOT CONFIGURED 占位工作表，不再阻断设备审核报告导出。STANDARD 从当前启用的应用级参考文件复制；Import Sources 和 Change Audit Log 用于追溯。",
    "Open Site Workspace": "打开站点工作区",
    "Station modification & issue-closure sign-off PDF": "站点修改与问题关闭签字 PDF",
    "Creates an A4 outstanding-action PDF for the selected site. It shows only open RMU Needs Action items, separates Analog / Telemetry and Status / Cmd signal Needs Action, and includes the reviewer-selected RMU Resolution / next action plus reviewer/time so the field team knows what to do next. Closed records, RMU manual verification, the separate Issue / Action Register and Change Audit are not rendered in the PDF; they remain preserved in Project Data. The PDF snapshot and SHA-256 hash are stored in Project Data.": "为所选站点生成 A4 待处理事项签字 PDF。PDF 仅显示尚未关闭的 RMU“需处理”项目，并分别列出 Analog / Telemetry 与 Status / Cmd 信号的“需处理”项，同时包含审核人员选择的 RMU 处理决议 / 下一步措施以及审核人员和时间，便于现场人员明确后续操作。已关闭记录、RMU 人工确认、独立的问题 / 处理登记和变更审计不会写入该 PDF，但会继续保存在项目数据中。PDF 快照及 SHA-256 哈希也会保存在项目数据中。",
    "Sign-off history: —": "签字历史：—",
    "Open Site History": "打开站点历史",
    "Delivery status: select a site and run validation": "交付状态：请选择站点并运行校验",
    "Delivery status: Ready for formal Migration Report export": "交付状态：可正式导出迁移报告",

    # Signal Mapping Review
    "Sources: —": "数据源：—",
    "Mode: calculated": "模式：计算结果",
    "Mode: Calculated": "模式：计算结果",
    "Rows: 0": "行数：0",
    "Rows: loading…": "行数：正在加载…",
    "Open IOA File": "打开 IOA 文件",
    "No Signal Mapping Review loaded": "尚未加载信号映射审核",
    "Signal Mapping Review is not available": "信号映射审核当前不可用",
    "Load ZENON-ADMS-IOA.csv and ADMS-SLD.csv, then run validation.": "请加载 ZENON-ADMS-IOA.csv 和 ADMS-SLD.csv，然后运行校验。",
    "Analog": "模拟量",
    "Status/Cmd": "状态/命令",
    "Status / Cmd": "状态 / 命令",
    "← All RMUs": "← 全部 RMU",
    "Choose a column, or search across all visible signal data.": "选择一个列进行搜索，或在所有当前可见的信号数据中搜索。",
    "Set Unreviewed / Closed / Needs Action for the selected signal row(s).": "将所选信号行设置为未审核 / 已关闭 / 需处理。",
    "Action / Remark": "处理 / 备注",
    "Choose ADD / MODIFY / DELETE and enter the required reviewer remark for one selected signal row. Both are saved in Comments.": "为一条所选信号选择 ADD / MODIFY / DELETE，并填写必需的审核备注；两者会一起保存到 Comments。",
    "Need Action Summary": "需处理汇总",
    "Total 0 · Analog 0 · Status/Cmd 0": "总数 0 · 模拟量 0 · 状态/命令 0",
    "ADMS Implementation Summary": "ADMS 实现汇总",
    "ZENON-only points for this RMU": "该 RMU 仅 ZENON 存在的点",
    "Click a Need Action item to jump to that signal. Click an ADMS implementation item, or its automatic Comments cell, to highlight the ADMS implementation.": "点击“需处理”项目可跳转到对应信号；点击 ADMS 实现项目或其自动生成的 Comments 单元格，可高亮对应的 ADMS 实现。",
    "Need Action signal is not visible in the current RMU view.": "该需处理信号当前未显示在此 RMU 视图中。",
    "No RMU selected": "未选择 RMU",
    "0 ZENON-only points": "0 个仅 ZENON 存在的点",
    "No confident ADMS implementation match was found for this ZENON-only signal.": "未能为该仅 ZENON 存在的信号找到可靠的 ADMS 实现匹配。",
    "ADMS implementation was located but is not visible in the current RMU view.": "已定位到 ADMS 实现，但当前 RMU 视图中不可见。",
    "Signal Mapping filters cleared · showing all rows": "已清除信号映射筛选 · 显示全部行",
    "Signal selection cleared": "已清除信号选择",
    "Source order: STANDARD → ADMS → ZENON · ADMS/ZENON from ZENON-ADMS-IOA.csv": "数据源顺序：STANDARD → ADMS → ZENON · ADMS/ZENON 来自 ZENON-ADMS-IOA.csv",
    "Source processing is already running. Please wait for it to finish.": "数据源处理正在运行，请等待完成。",
    "Signal Mapping Review unavailable": "信号映射审核不可用",
    "Auto-loading active Signal Mapping sources…": "正在自动加载当前信号映射数据源…",
    "Loading Signal Mapping Review automatically…": "正在自动加载信号映射审核…",
    "Signal Mapping auto-load failed": "信号映射自动加载失败",
    "No cached Signal Mapping validation · Run Validation": "没有缓存的信号映射校验结果 · 请运行校验",
    "Open Signal Mapping Review. The detailed table is loaded only when that module is opened.": "打开信号映射审核。详细表格仅在进入该模块时加载。",
    "Run Validation to calculate Signal Mapping results.": "运行校验以计算信号映射结果。",
    "Open Signal Mapping Review filtered to MISMATCHED.": "打开信号映射审核，并筛选为 MISMATCHED。",
    "No signal mismatches were found. Use the left navigation to open the full Signal Mapping Review.": "未发现信号不一致。可通过左侧导航打开完整的信号映射审核。",
    "Open Settings to upload multiple STANDARD workbooks and explicitly choose the active reference.": "打开设置，可上传多个 STANDARD 工作簿并明确选择当前使用的参考版本。",
    "Re-read the Signal Mapping source files and rebuild validation results in the background.": "重新读取信号映射数据源文件，并在后台重建校验结果。",

    # Setup / persistent project data dialog
    "Set up Migration Report Tool": "设置迁移报告工具",
    "Choose your source workspace and Project Data storage": "选择数据源工作区和项目数据存储位置",
    "The app reads migration source files from the Source Workspace and stores review history, comments, resolutions, revisions and generated reports under Project Data. These locations are remembered for future launches and can be changed later in Settings.": "程序从数据源工作区读取迁移源文件，并在项目数据目录中保存审核历史、备注、处理决议、版本和生成的报告。程序会记住这些位置，后续也可以在设置中修改。",
    "1  Source Workspace (read-only)": "1  数据源工作区（只读）",
    "Choose the folder that contains one subfolder per site and the source CSV/XLSX files used by the migration review.": "请选择包含各站点子目录以及迁移审核所需 CSV/XLSX 源文件的文件夹。",
    "Browse...": "浏览...",
    "2  Project Data Storage (writable)": "2  项目数据存储（可写）",
    "Choose where the app keeps project.db, Review/Needs Action decisions, Comments, Change Audit, revisions and report snapshots. Keep this outside the release folder.": "请选择用于保存 project.db、审核/需处理决策、备注、变更审计、版本和报告快照的位置。建议放在程序发布目录之外。",
    "You can choose Configure Later. The app will keep showing a setup reminder until the required locations are configured.": "可以选择“稍后配置”。在必需位置完成配置前，程序会持续显示设置提醒。",
    "Configure Later": "稍后配置",
    "Save & Continue": "保存并继续",

    # Generic dialogs / lifecycle / edit UI
    "Review / Edit Value": "审核 / 编辑值",
    "Every accepted change is written to the SQLite audit history.": "每次确认的修改都会写入 SQLite 审计历史。",
    "Reason / comment for this modification": "本次修改的原因 / 备注",
    "Comment": "备注",
    "Copy the latest saved comment into the New Review Comment editor. The saved history is not changed until you save a new comment.": "将最新已保存备注复制到“新增审核备注”编辑框。只有保存新备注后，历史记录才会新增，不会修改旧记录。",
    "Choose one resolution for each FALSE Analysis field. Customer Comments are optional and independent from the Resolution choice; changing a comment never changes Analysis or the selected Resolution. Both the latest comment and every historical comment change are retained. Resolution choices record the agreed handling only and never change Review Status. Choosing a value equal to ADMS DB does not close the equipment, and choosing a different source does not open it automatically. Use the separate Review Status control to mark Needs Action, Closed, or Unreviewed.": "请为每个 Analysis=FALSE 的字段选择一个处理决议。客户备注为可选项，并与处理决议相互独立；修改备注不会改变 Analysis 或已选择的处理决议。最新备注和全部历史备注都会保留。处理决议只记录约定的处理方式，绝不会自动修改审核状态；即使选择的值与 ADMS DB 相同也不会自动关闭，选择其他来源也不会自动进入需处理。请通过独立的审核状态操作明确设置“需处理 / 已关闭 / 未审核”。",
    "Choose one resolution for each FALSE configured Analysis field. Customer Comments are optional and independent from the Resolution choice; changing a comment never changes Analysis or the selected Resolution. Both the latest comment and every historical comment change are retained. Resolution choices record the agreed handling only and never change Review Status. Use the separate Review Status control to mark Needs Action, Closed, or Unreviewed. A Needs Action item stays open until a reviewer explicitly changes its Review Status.": "请为每个已配置且 Analysis=FALSE 的字段选择一个处理决议。客户备注为可选项，并与处理决议相互独立；修改备注不会改变 Analysis 或已选择的处理决议。最新备注和全部历史备注都会保留。处理决议只记录约定的处理方式，绝不会自动修改审核状态。请通过独立的审核状态操作明确设置“需处理 / 已关闭 / 未审核”；设备一旦被人工标记为“需处理”，会一直保持该状态，直到审核人员明确修改审核状态。",
    "Enter the agreed custom Resolution value / instruction...": "请输入约定的自定义处理决议 / 指令...",
    "Copy the latest saved comment into the new comment editor. Existing history remains read-only.": "将最新已保存备注复制到新增备注编辑框；已有历史保持只读。",
    "Add a new reviewer/customer comment for this issue. Leave blank to keep the latest saved comment unchanged. Previous comments are never edited or deleted.": "为该问题新增审核人员 / 客户备注。留空则保持最新已保存备注不变；历史备注永远不会被编辑或删除。",
    "Resolution and Customer Comments are stored independently. Existing comments are read-only in this dialog. Leave New Customer Comment blank to keep the latest comment unchanged, or add/continue a comment to append a new review-history record. RMU Action Tracking / Full Lifecycle retains the full history once the RMU has a Needs Action case.": "处理决议和客户备注独立保存。本窗口中的历史备注为只读。新增客户备注留空则保持最新备注不变；填写或继续补充备注会追加一条新的审核历史记录。RMU 一旦进入“需处理”案例，处理跟踪 / 完整生命周期会保留全部历史。",
    "Save Resolutions & Comments": "保存处理决议和备注",
    "Signal Action / Remark": "信号处理 / 备注",
    "Choose the actual rectification action, then enter the reviewer remark. Both are required and are saved together in Comments.": "请选择实际整改操作，然后填写审核备注。两项均为必填，并一起保存到 Comments。",
    "Required remark / agreed rectification note...": "必填备注 / 已约定整改说明...",
    "Append-only lifecycle history from the first formal Needs Action through comments/resolutions/actions, validation changes and explicit closure. Closed items reopened later start a new case.": "生命周期历史仅追加不覆盖：从第一次正式进入“需处理”开始，持续记录备注、处理决议、操作、校验变化以及明确关闭。已关闭项目后续重新打开时会创建新案例。",
    "No formal Needs Action lifecycle has been recorded for this item.": "该项目尚未记录正式的“需处理”生命周期。",
    "App Version": "App 版本",
    "Before": "修改前",
    "After": "修改后",
    "Event": "事件",
    "Select an event to inspect the frozen lifecycle snapshot.": "请选择一个事件以查看冻结的生命周期快照。",
    "Final Status": "最终状态",
    "Scope": "范围",
    "State at Event": "事件时状态",
    "Before → After": "修改前 → 修改后",
    "Site Issue / Action Record": "站点问题 / 处理记录",
    "This record is stored in the selected site's persistent Project Data and remains available after application upgrades.": "该记录保存在所选站点的持久化项目数据中，程序升级后仍会保留。",
    "RMU name / feeder / signal / equipment ID": "RMU 名称 / 馈线 / 信号 / 设备 ID",
    "Describe the issue found at this site": "描述该站点发现的问题",
    "Describe the action taken or required": "描述已采取或需要采取的措施",
    "Optional notes": "可选备注",

    # Source mapping / column-order dialog presentation
    "Drag columns into any order, or use the move buttons. This changes only how columns are displayed inside this source group; Source Field mapping and automatic Analysis are not changed.": "可拖动列调整顺序，也可以使用移动按钮。这里只改变该数据源分组中的列显示顺序，不会修改源字段映射或自动 Analysis。",
    "Reset Default Order": "恢复默认顺序",
    "Apply Order": "应用顺序",
    "Allow remapping of SYSTEM · LOCKED fields for this dialog only. A confirmation is required because these mappings feed system calculations.": "仅在当前窗口允许重新映射 SYSTEM · 已锁定字段。由于这些映射参与系统计算，操作前需要再次确认。",
    "Create a new App column and map it to a physical source field.": "新建 App 字段并将其映射到物理源字段。",
    "System logic columns are protected. User-added and optional presentation columns can be removed.": "系统逻辑字段受保护；用户新增字段和可选展示字段可以删除。",
    "Reorder App columns inside this source group. This changes presentation only.": "调整该数据源分组内 App 字段顺序；仅影响显示。",
    "Restore optional built-in presentation columns previously removed from this App table.": "恢复此前从该 App 表中移除的可选内置展示字段。",
    "App column name. Renaming changes presentation only; validation keeps the same internal field.": "App 字段名称。重命名只影响显示，校验仍使用相同的内部字段。",
    "Explicit blank mapping. This App field will display an empty value and no physical Source Field will be used. Choose Auto to resume normal header-name detection.": "显式空映射。该 App 字段会显示为空，并且不使用任何物理源字段。选择 Auto 可恢复正常的表头名称自动识别。",
    "SYSTEM calculation mapping is protected. Click 'Unlock System Mappings...' to remap this Source Field. Changing it affects Analysis/validation for all sites.": "SYSTEM 计算映射受保护。点击“解锁系统映射...”后才可重新映射该源字段；修改会影响所有站点的 Analysis / 校验。",
    "Application-global App column name. The same column is shown for every site.": "应用级全局 App 字段名称；所有站点显示同一个字段。",
    "Global Source Field selection. Saving it here applies the same mapping to every station.": "全局源字段选择；在此保存后，相同映射会应用于所有站点。",
    "Application-global USER App column. Name, deletion and Source Field mapping all apply to every station.": "应用级全局 USER App 字段；名称、删除和源字段映射都会应用于所有站点。",
    "Added App column": "新增的 App 字段",
    "Column display order changed. Save to apply it to RMU Data Review and workbook exports.": "列显示顺序已调整。保存后将应用于设备数据审核和工作簿导出。",
    "No optional built-in columns are hidden.": "当前没有隐藏的可选内置字段。",
    "Optional built-in columns restored. Save to keep them visible.": "已恢复可选内置字段；保存后保持显示。",
    "Optional built-in fields will use Auto mapping after Save. Protected SYSTEM mappings were left unchanged; unlock them first if you intend to reset those mappings too.": "保存后，可选内置字段将恢复为 Auto 映射；受保护的 SYSTEM 映射保持不变。如需同时重置 SYSTEM 映射，请先解锁。",
    "Built-in source fields will use Auto mapping after Save. Explicit blank selections are cleared.": "保存后，内置源字段将使用 Auto 映射，并清除显式空映射选择。",
    "Protected system mapping changes were not saved. Review the mappings or Cancel.": "受保护的系统映射修改尚未保存。请检查映射，或取消本次操作。",
    "Mapping saved. Refreshing affected data in the background...": "映射已保存，正在后台刷新受影响的数据...",

    # Derived Table Builder
    "Derived Table Builder": "派生表构建器",
    "Map existing source tables, add project-local fields, join by business keys, calculate new fields, preview the result and export a new CSV/XLSX. This builder does not change the existing RMU or Signal validation algorithms.": "映射现有源表、增加项目本地字段、按业务键连接、计算新字段、预览结果并导出新的 CSV/XLSX。该构建器不会修改现有设备或信号校验算法。",
    "Output Tables": "输出表",
    "+ New Table": "+ 新建表",
    "Delete": "删除",
    "Table Name": "表名",
    "Base Source": "基础数据源",
    "Optional business purpose": "可选业务用途",
    "Fields": "字段",
    "Joins": "连接",
    "Preview": "预览",
    "Save Configuration": "保存配置",
    "Export CSV": "导出 CSV",
    "Export Excel": "导出 Excel",
    "Insert Source Field": "插入源字段",
    "Insert Reference": "插入引用",
    "Internal Key": "内部键",
    "Mapping / Formula": "映射 / 公式",
    "Output Field": "输出字段",
    "+ Add Field": "+ 新增字段",
    "Remove Field": "移除字段",
    "Join Source": "连接数据源",
    "Join Type": "连接类型",
    "Left Expression": "左侧表达式",
    "Right Field": "右侧字段",
    "+ Add Join": "+ 新增连接",
    "Remove Join": "移除连接",
    "Click Preview to calculate the table. Preview shows up to 500 rows; export writes all rows.": "点击“预览”计算表格。预览最多显示 500 行，导出会写入全部行。",
    "Choose which source columns are visible. This changes only the desktop review view; the source workbook remains read-only.": "选择需要显示的源字段列。这里只改变桌面审核视图，源工作簿保持只读。",
    "Source Only": "仅源字段",

    # Runtime messages / tooltips across non-equipment pages
    "Source detection rules saved and repository re-scanned": "数据源识别规则已保存，并已重新扫描站点数据仓库",
    "Select a site and configure its source Workspace first": "请先选择站点并配置数据源工作区",
    "Setup saved · loading Source Workspace...": "设置已保存 · 正在加载数据源工作区...",
    "Setup confirmed": "设置已确认",
    "Loading workspace index...": "正在加载工作区索引...",
    "Choose AUTO or one worksheet for this site's Excel source. Sheet selection is site/file-level; App field mapping remains global by source type.": "可选择 AUTO 或该站点 Excel 数据源中的某个工作表。工作表选择属于站点 / 文件级设置；App 字段映射仍按数据源类型全局生效。",
    "App column configuration updated globally.": "App 字段配置已全局更新。",
    "Issue / Action record saved in persistent Site History": "问题 / 处理记录已保存到持久化站点历史",
    "Run Validation before reviewing RMU issues.": "请先运行校验，再审核 RMU 问题。",
    "Open Equipment Data Review filtered to ANY MISMATCH.": "打开设备数据审核，并筛选为 ANY MISMATCH。",
    "No equipment Analysis issues were found. Use the left navigation to open Equipment Data Review.": "未发现设备 Analysis 问题。可通过左侧导航打开设备数据审核。",
})


ZH_CN.update({
    "Choose which Source Field feeds each App Column. The App-column configuration is global across all sites: built-in display names, USER-added columns, explicit Source Field selections and saved column order are shared by every station. If a station's physical file does not contain the selected Source Field, that column remains visible and is shown as unmapped/blank. For SYSTEM fields: Auto shows the currently resolved header as 'Auto → Header'; Blank forces an empty value; selecting a physical header creates an explicit Manual mapping. SYSTEM calculation mappings are protected by default; use Unlock System Mappings before deliberately remapping them. A later new source column can be selected manually, or you can switch back to Auto at any time. Use the Show checkbox to control whether a field appears in Equipment Data Review; hiding a field never deletes its App definition or mapping. SYSTEM calculation fields are always shown and cannot be hidden.": "选择每个 App 字段由哪个源字段提供数据。App 字段配置在所有站点之间全局共享：内置显示名称、USER 新增字段、显式源字段选择以及保存的字段顺序都会应用于每个站点。如果某个站点的物理文件不包含已选择的源字段，该列仍会保留，但其值显示为未映射 / 空白。对于 SYSTEM 字段：Auto 会显示当前自动解析到的表头（Auto → Header）；Blank 强制为空；选择物理表头会建立显式 Manual 映射。SYSTEM 计算映射默认受保护，需要先使用“解锁系统映射”才能主动重映射。以后新增的源字段可以手动选择，也可以随时切回 Auto。通过“显示”复选框控制字段是否出现在设备数据审核中；隐藏字段不会删除 App 字段定义或映射。SYSTEM 计算字段始终显示且不能隐藏。",
    "Start from Base Source, then add joins in order. Left Expression references a source already joined; Right Field belongs to the source on this row. Example: adms_db.rmu = zenon_sld.rmu. LEFT keeps base rows, INNER keeps matches, FULL also keeps unmatched right-side rows.": "从基础数据源开始，再按顺序添加连接。左侧表达式引用已经加入的源；右侧字段属于当前行的数据源。例如：adms_db.rmu = zenon_sld.rmu。LEFT 保留基础源行，INNER 仅保留匹配行，FULL 还会保留右侧未匹配行。",
    "Select an event to inspect its frozen lifecycle snapshot.": "请选择一个事件以查看该事件的冻结生命周期快照。",
    "Open Signal Mapping Review and show only mismatched signals.": "打开信号映射审核，并仅显示不一致信号。",
    "Last scan: —": "上次扫描：—",
    "Choose the exact table column to search. Use All Columns only when a cross-column fuzzy search is intended.": "请选择要搜索的具体表格列；只有需要跨列模糊搜索时才使用“所有列”。",
    "Filter only by the manual human Review state. Automated Analysis is filtered separately.": "仅按人工审核状态筛选；自动 Analysis 结果使用独立筛选条件。",
    "Filter by Analysis result": "按 Analysis 结果筛选",
    "Clear search and every Equipment Review/Analysis filter; keep column layout and review data unchanged.": "清除搜索以及所有设备审核 / Analysis 筛选条件；列布局和审核数据保持不变。",
    "Explicitly clear the current Equipment Data Review selection": "明确清除当前设备数据审核中的选中项",
    "Set the selected equipment row(s) to Unreviewed, Closed or Needs Action. Structured Resolution remains available by double-clicking FALSE/Resolution cells.": "将所选设备行设置为未审核、已关闭或需处理。双击 FALSE / 处理决议单元格仍可维护结构化处理决议。",
    "Show or hide Equipment Data Review groups and fields": "显示或隐藏设备数据审核中的分组和字段",
    "Restore the default Equipment Data Review column visibility; filters are controlled by Show All": "恢复设备数据审核默认列显示；筛选条件由“显示全部”控制",
    "Total = all rows for the active Equipment Type. Shown = rows after filters. Each displayed issue count is the number of equipment rows where that Analysis field is FALSE. Zero-count fields are hidden.": "总数 = 当前设备类型的全部行；显示 = 应用筛选后的行。每个问题计数表示对应 Analysis 字段为 FALSE 的设备行数；计数为 0 的字段会隐藏。",
    "Review is the human workflow state. Resolution counts structured decisions for active FALSE Analysis fields.": "审核表示人工工作流状态；处理决议统计当前 FALSE Analysis 字段的结构化决策数量。",
    "Open a larger read-only lifecycle viewer including cases, events and frozen snapshots.": "打开更大的只读生命周期查看器，包含案例、事件和冻结快照。",
    "Equipment filters cleared · showing all rows": "设备筛选已清除 · 显示全部行",
    "No RMU Data Review rows could be built. Check Site Data Sources, then reopen this module.": "无法构建设备数据审核行。请检查站点数据源，然后重新打开该模块。",
    "Resolution 0 / 0 issue decisions · Human status is independent": "处理决议 0 / 0 个问题决策 · 人工审核状态独立维护",
})

# v0.8.168 source-driven review visibility. Physical source headers and App
# engineering labels remain language-neutral; explanatory UI is localized.
ZH_CN.update({
    "This table mirrors the live physical source header: one physical source column equals one App row. A newly added Excel/CSV column is detected after the file is saved and appears automatically; its default App name is the source header itself. You may rename the App label later without changing the physical Source Field. Canonical SYSTEM semantics are attached to the matching physical row and stay locked visible because they feed matching, Analysis or validation. Optional rows can be shown/hidden for Equipment Data Review without deleting their mapping. Absent physical columns are not rendered as phantom rows.": "此表实时镜像当前物理数据源表头：一个物理源列对应一个 App 字段行。Excel/CSV 保存后若新增列，程序会自动识别并显示；新增字段默认直接使用源表头作为 App 名称，之后可修改 App 显示名称，但不会改变物理源字段。匹配到的 SYSTEM 语义会绑定到对应物理列，并因参与匹配、Analysis 或校验而强制显示。可选字段可控制是否显示在设备数据审核中，隐藏不会删除映射；当前物理文件不存在的列不会生成虚假字段。",
        "This table mirrors the live physical source header: one physical source column equals one App row. A newly added Excel/CSV column is detected after the file is saved and appears automatically; its default App name is the source header itself. You may rename the App label later without changing the physical Source Field. Canonical SYSTEM semantics are attached to the matching physical row and stay locked visible because they feed matching, Analysis or validation. Optional rows are hidden by default and can be shown/hidden for Equipment Data Review without deleting their mapping. Map Fields settings are global by App/source type: mapping, App display names, Show/Hide and column order saved at one station are reused by every station. The physical source file and Excel sheet remain station-specific. Absent physical columns are not rendered as phantom rows.": "此表实时镜像当前物理数据源表头：一个物理源列对应一个 App 字段行。Excel/CSV 保存后若新增列，程序会自动识别并显示；新增字段默认直接使用源表头作为 App 名称，之后可修改 App 显示名称，但不会改变物理源字段。匹配到的 SYSTEM 语义会绑定到对应物理列，并因参与匹配、Analysis 或校验而强制显示。可选字段默认隐藏，可控制是否显示在设备数据审核中，隐藏不会删除映射。字段映射设置按 App/数据源类型全局共享：在任一站点保存的映射、App 显示名称、显示/隐藏和字段顺序都会应用到所有站点；物理数据源文件和 Excel 工作表仍保持站点独立。当前物理文件不存在的列不会生成虚假字段。",
"This dialog controls App/meta columns such as Index, Source Coverage, Analysis, Remarks and Resolution. Physical SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD columns follow the Show checkboxes in Map Fields directly, so there is only one visibility setting for source fields. SYSTEM calculation fields are always visible because they feed matching, Analysis or validation. No source mapping, SQLite review data or exported report history is deleted by changing this view.": "此窗口只控制 App 自身的辅助列，例如行定位、源覆盖、Analysis、备注和处理决议。SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD 的物理源字段直接跟随“字段映射”窗口中的“显示”复选框，因此源字段只有一套显示设置。参与匹配、Analysis 或校验的 SYSTEM 计算字段始终显示。修改显示不会删除源映射、SQLite 审核数据或历史导出记录。",
    "Defaults to the physical source header. You may rename the App label; the underlying system key/mapping does not change.": "默认使用物理源表头作为 App 显示名称。可以修改 App 名称，但底层系统字段键和映射关系不会改变。",
    "SYSTEM calculation mapping is protected. Click 'Unlock System Mappings...' to remap this Source Field.": "SYSTEM 计算映射已受保护。如需重新映射此源字段，请先点击“解锁系统映射...”。",
    "Physical source column:": "物理源字段：",
    "Source-driven row: this App field is bound to this physical source header. Rename the App label if needed; the physical column remains unchanged.": "此行为源字段驱动的 App 字段，已绑定到当前物理源表头。可以修改 App 显示名称，但物理源字段保持不变。",
    "Physical source column discovered from the live file. The App display name can be changed; visibility is presentation-only.": "从当前实际文件中发现的物理源字段。可以修改 App 显示名称；显示/隐藏只影响界面展示。",
    "Physical source column": "物理源字段",
})


# v0.8.164 modal-dialog coverage. File-filter patterns and engineering tokens
# intentionally remain unchanged.
ZH_CN.update({
    "Replace Draft?": "替换草稿？",
    "The New Review Comment editor already contains text. Replace the draft with the latest saved comment?": "新增审核备注编辑框中已有内容。是否用最新已保存备注替换当前草稿？",
    "New Comment Required": "需要新增备注",
    "Enter a new Review comment before saving. Existing comments are read-only and remain unchanged.": "保存前请输入新的审核备注。已有备注为只读并保持不变。",
    "The New Customer Comment editor already contains text. Replace the draft with the latest saved comment?": "新增客户备注编辑框中已有内容。是否用最新已保存备注替换当前草稿？",
    "Comment Required": "需要填写备注",
    "Confirm System Mapping Changes": "确认系统映射修改",
    "Add App Column": "新增 App 字段",
    "New App column name:": "新 App 字段名称：",
    "App Column name cannot be blank.": "App 字段名称不能为空。",
    "Added App Column name cannot be blank.": "新增 App 字段名称不能为空。",
    "New Output Table": "新建输出表",
    "Table Name:": "表名：",
    "Delete Output Table": "删除输出表",
    "Derived Table Preview": "派生表预览",
    "Export Derived CSV": "导出派生 CSV",
    "Export Derived Excel": "导出派生 Excel",
    "Select ADD / MODIFY / DELETE and enter a remark before saving.": "保存前请选择 ADD / MODIFY / DELETE，并填写备注。",
    "Enter the issue description before saving.": "保存前请输入问题描述。",
    "Issue required": "需要填写问题",
    "Choose an existing Source Workspace folder before continuing.": "继续前请选择一个存在的数据源工作区目录。",
    "Source Workspace required": "需要数据源工作区",
    "Choose a Project Data storage folder before continuing.": "继续前请选择项目数据存储目录。",
    "Project Data required": "需要项目数据目录",
    "Project Data unavailable": "项目数据不可用",
    "Use separate folders": "请使用不同目录",
    "Source Workspace and Project Data Storage must be separate locations. Project Data should not be stored inside the read-only source workspace.": "数据源工作区与项目数据存储必须使用不同位置。项目数据不应存放在只读的数据源工作区内部。",
    "RMU Check": "RMU 检查",
    "Equipment Lifecycle": "设备生命周期",
    "Select exactly one equipment row to view its full lifecycle.": "请选择且仅选择一条设备记录以查看完整生命周期。",
    "Signal Check": "信号检查",
    "Select exactly one signal row, then click Action / Remark.": "请选择且仅选择一条信号记录，然后点击“处理 / 备注”。",
    "Signal Lifecycle": "信号生命周期",
    "Select exactly one signal row to view its Need Action lifecycle.": "请选择且仅选择一条信号记录以查看其“需处理”生命周期。",
    "This signal has not entered formal Needs Action yet.": "该信号尚未进入正式的“需处理”状态。",
    "Load a Signal Mapping Review first.": "请先加载信号映射审核。",
    "Select a site and Source Workspace first.": "请先选择站点和数据源工作区。",
    "Select one or more signal cells / rows first.": "请先选择一个或多个信号单元格 / 行。",
    "Signal Mapping source values are read-only. Right-click any cell (or use Set Status) to mark the row Unreviewed / Closed / Needs Action; Action / Remark is stored in Comments in project.db.": "信号映射源值为只读。右键任意单元格（或使用“设置状态”）可将该行标记为未审核 / 已关闭 / 需处理；“处理 / 备注”会保存到 project.db 的 Comments 中。",
    "No Signal Mapping source is loaded.": "尚未加载信号映射数据源。",
    "STANDARD Already Exists": "STANDARD 已存在",
    "STANDARD Validation Failed": "STANDARD 校验失败",
    "STANDARD Library": "STANDARD 库",
    "Use Selected STANDARD": "使用所选 STANDARD",
    "STANDARD Selection Failed": "STANDARD 选择失败",
    "The bundled STANDARD table is already active.": "当前已经使用内置 STANDARD 表。",
    "Use Built-in STANDARD": "使用内置 STANDARD",
    "Select the bundled STANDARD reference? Uploaded STANDARD versions will remain in the library.": "是否选择内置 STANDARD 参考文件？已经上传的 STANDARD 版本仍会保留在库中。",
    "STANDARD Reference": "STANDARD 参考",
    "Change Project Data": "更改项目数据位置",
    "Choose a valid Workspace first.": "请先选择有效的工作区。",
    "Select a Workspace first.": "请先选择工作区。",
    "IOA STANDARD": "IOA STANDARD",
    "The application STANDARD reference is managed by Update STANDARD on Signal Mapping Review.": "应用级 STANDARD 参考文件通过信号映射审核页面中的“更新 STANDARD”进行管理。",
    "Choose how this App Table resolves its physical source file.\n\nAUTO: use the highest semantic V version; if no published V exists, use the configured Source Detection Rules/base filename.\nPIN: use the exact V version you select, even when a newer version exists.\nMANUAL: browse any CSV/XLSX/XLSM filename; field mapping, not filename, defines the source role.": "请选择该 App 表如何确定实际物理数据源文件。\n\nAUTO：使用语义版本最高的 V 版本；如果没有发布 V 版本，则使用已配置的数据源识别规则 / 基础文件名。\nPIN：固定使用你选择的具体 V 版本，即使存在更高版本也不会自动切换。\nMANUAL：浏览并选择任意 CSV/XLSX/XLSM 文件；数据源角色由字段映射决定，而不是由文件名决定。",
    "The active source is not an Excel workbook.": "当前数据源不是 Excel 工作簿。",
    "The workbook contains no worksheets.": "该工作簿不包含任何工作表。",
    "Select an App Table first.": "请先选择一个 App 表。",
    "The application STANDARD reference is managed with Update STANDARD / Restore Built-in, not site file selection.": "应用级 STANDARD 参考文件通过“更新 STANDARD / 恢复内置版本”管理，不通过站点文件选择管理。",
    "The selected source file is no longer available.": "所选数据源文件已不可用。",
    "Select a table in the current module first.": "请先选择当前模块中的一个表。",
    "Replace Source": "替换数据源",
    "Select a site from Site Repository first. No separate Project needs to be created.": "请先从站点数据仓库选择一个站点，无需另外创建 Project。",
    "Workspace restriction": "工作区限制",
    "Select a site from Site Data Sources before running validation.": "运行校验前，请先在站点数据源中选择站点。",
    "Select a Workspace before running validation.": "运行校验前，请先选择工作区。",
    "No RMU review data": "没有 RMU 审核数据",
    "Run Validation before saving a version.": "保存版本前请先运行校验。",
    "Manual snapshot": "手工快照",
    "Version saved": "版本已保存",
    "Site modification / issue closure checkpoint": "站点修改 / 问题关闭检查点",
    "One or more active Excel/CSV source selections or the active STANDARD workbook changed after the last Validation.\n\nRun Validation first. The PDF is only generated from the currently selected source files after they have been recalculated.": "上次校验后，一个或多个当前 Excel/CSV 数据源选择或当前 STANDARD 工作簿发生了变化。\n\n请先重新运行校验。PDF 只会基于当前所选数据源文件重新计算后生成。",
    "Enter a name before exporting the PDF report.": "导出 PDF 报告前请输入姓名。",
    "Prepared By Required": "需要填写编制人",
    "Sign-off PDF generated": "签字 PDF 已生成",
    "Select a generated PDF record first.": "请先选择一条已生成的 PDF 记录。",
    "Select report": "选择报告",
    "Signed PDF attached": "已关联签字 PDF",
    "Select a PDF record first.": "请先选择一条 PDF 记录。",
    "File not found": "文件不存在",
    "One or more active Excel/CSV source selections or the active STANDARD workbook changed after the last Validation.\n\nRun Validation first. The Excel report is only exported from the currently selected source files after they have been recalculated.": "上次校验后，一个或多个当前 Excel/CSV 数据源选择或当前 STANDARD 工作簿发生了变化。\n\n请先重新运行校验。Excel 报告只会基于当前所选数据源文件重新计算后导出。",
    "Run Validation before exporting.": "导出前请先运行校验。",
    "Review not complete": "审核尚未完成",
    "Export complete": "导出完成",
})

ZH_CN.update({
    "Validation required": "需要校验",
})

# v0.8.164 final presentation sweep. These strings are still UI/help text,
# not physical source headers or persisted engineering values. Some appear as
# suffixes inside runtime-composed tooltips; ZH_EMBEDDED below translates those
# fragments without touching arbitrary source data.
ZH_CN.update({
    "The timeline preserves reopen/close cycles, Resolution choices, review comments, manual checks and validation-result changes.": "时间线会保留重新打开/关闭周期、处理决议、审核备注、人工检查以及校验结果变化。",
    "STANDARD → ADMS → ZENON · ADMS/ZENON from combined IOA": "STANDARD → ADMS → ZENON · ADMS/ZENON 数据来自合并 IOA",
    "Checked means the reviewer inspected this equipment and accepted it as passed.": "勾选表示审核人员已检查该设备，并确认其审核通过。",
    "STANDARD: —": "STANDARD：—",
    "Affected RMUs by field:": "按字段统计受影响 RMU：",
    "Built-in App column": "内置 App 字段",
    "Checked means the reviewer inspected this signal and accepted it as passed.": "勾选表示审核人员已检查该信号，并确认其审核通过。",
    "Double-click to set Review status.": "双击可设置审核状态。",
    "Click to choose an existing version or browse another file for this App Table.": "点击可选择已有版本，或为此 App 表浏览并选择其他文件。",
    "Human Review:": "人工审核：",
    "The selected source file was loaded successfully, but its physical column names no longer satisfy the current App mapping.\n\nThis is not a source-file error. Remap the required App Columns to the new Source Fields, then Save and run Validation.": "所选数据源文件已成功加载，但其物理列名已不再满足当前 App 映射。\n\n这不是数据源文件错误。请将必需的 App 字段重新映射到新的源字段，然后保存并重新运行校验。",
    "Right-click any cell to set Unreviewed / Closed / Needs Action for this equipment row.": "右键任意单元格可将该设备行设置为未审核 / 已关闭 / 需处理。",
    "Auto has no matching Source Field in the current file.": "AUTO 在当前文件中没有匹配的源字段。",
    "The App value will remain blank. Choose a physical Source Field manually, keep Auto selected so a future matching header can be detected, or choose 'Blank · no source field' for an intentional blank.": "该 App 值将保持为空。可以手工选择物理源字段；也可以保留 AUTO，以便以后自动识别匹配表头；若希望明确保持空值，请选择“Blank · no source field”。",
    "Click this Source File cell to use AUTO, pin a specific V version, or browse another file. AUTO prefers the highest parsable V version; if none exists it falls back to Source Detection Rules. An explicit user choice always has priority.": "点击此数据源文件单元格可使用 AUTO、固定某个 V 版本，或浏览并选择其他文件。AUTO 优先使用可解析的最高 V 版本；若不存在，则回退到数据源识别规则。用户明确选择始终具有最高优先级。",
    "Click the Sheet cell/button to change this site's sheet without changing global field mapping.": "点击工作表单元格/按钮可更改当前站点使用的工作表，不会改变全局字段映射。",
    "Double-click this row or click Map Fields to change mapping.": "双击此行或点击“字段映射”可修改映射。",
    "Equipment selection cleared": "已清除设备选择",
    "No ZENON-only implementation notes for this RMU.": "该 RMU 没有仅 ZENON 存在的实现说明。",
    "ADMS implementation not found": "未找到 ADMS 实现",
    "match(es)": "个匹配",
    "not found": "未找到",
    "Calculated from site CSV + ADMS SLD + STANDARD": "基于站点 CSV + ADMS SLD + STANDARD 计算",
})

# Safe prose fragments that can be embedded after dynamic identifiers or other
# tooltip text. Keep this list intentionally specific; never do unrestricted
# substring translation of short engineering tokens such as Type, RMU or IP.
ZH_EMBEDDED: tuple[tuple[str, str], ...] = (
    ("The timeline preserves reopen/close cycles, Resolution choices, review comments, manual checks and validation-result changes.", "时间线会保留重新打开/关闭周期、处理决议、审核备注、人工检查以及校验结果变化。"),
    ("Checked means the reviewer inspected this equipment and accepted it as passed.", "勾选表示审核人员已检查该设备，并确认其审核通过。"),
    ("Built-in App column", "内置 App 字段"),
    ("Checked means the reviewer inspected this signal and accepted it as passed.", "勾选表示审核人员已检查该信号，并确认其审核通过。"),
    ("Double-click to set Review status.", "双击可设置审核状态。"),
    ("Click to choose an existing version or browse another file for this App Table.", "点击可选择已有版本，或为此 App 表浏览并选择其他文件。"),
    ("Human Review:", "人工审核："),
    ("Right-click any cell to set Unreviewed / Closed / Needs Action for this equipment row.", "右键任意单元格可将该设备行设置为未审核 / 已关闭 / 需处理。"),
    ("Auto has no matching Source Field in the current file.", "AUTO 在当前文件中没有匹配的源字段。"),
    ("The App value will remain blank. Choose a physical Source Field manually, keep Auto selected so a future matching header can be detected, or choose 'Blank · no source field' for an intentional blank.", "该 App 值将保持为空。可以手工选择物理源字段；也可以保留 AUTO，以便以后自动识别匹配表头；若希望明确保持空值，请选择“Blank · no source field”。"),
    ("Click this Source File cell to use AUTO, pin a specific V version, or browse another file. AUTO prefers the highest parsable V version; if none exists it falls back to Source Detection Rules. An explicit user choice always has priority.", "点击此数据源文件单元格可使用 AUTO、固定某个 V 版本，或浏览并选择其他文件。AUTO 优先使用可解析的最高 V 版本；若不存在，则回退到数据源识别规则。用户明确选择始终具有最高优先级。"),
    ("Click the Sheet cell/button to change this site's sheet without changing global field mapping.", "点击工作表单元格/按钮可更改当前站点使用的工作表，不会改变全局字段映射。"),
    ("Double-click this row or click Map Fields to change mapping.", "双击此行或点击“字段映射”可修改映射。"),
    ("Earlier comments are retained and become visible here once the equipment has Needs Action history. Signal Mapping is excluded for now.", "较早备注会继续保留；设备出现需处理历史后会在这里显示。当前不包含信号映射。"),
    ("Use Update STANDARD on Signal Mapping Review to replace it.", "如需替换，请在信号映射审核页面使用“更新 STANDARD”。"),
    ("Fields used by ", "使用字段："),
    ("Legacy mapping '", "旧版映射“"),
    ("' is not controlling this field because Auto currently resolves to '", "”当前不控制此字段，因为 AUTO 当前解析为“"),
    ("'. Choose a physical Source Field from this list if you want to make an explicit Manual mapping, or keep Auto.", "”。如需明确设置手工映射，请从列表中选择物理源字段；否则保留 AUTO。"),
    ("Auto currently resolves this App field to Source Field '", "AUTO 当前将此 App 字段解析到源字段“"),
    ("'. The Auto option always means automatic header-name detection; choose a physical Source Field to override it, or choose 'Blank · no source field' to keep the App field intentionally empty.", "”。AUTO 始终表示自动表头识别；可选择物理源字段覆盖它，或选择“Blank · no source field”明确保持该 App 字段为空。"),
    ("Manual Source Field mapping is active: '", "当前启用了手工源字段映射：“"),
    ("'. Choose Auto to remove the manual mapping and return to automatic header-name detection.", "”。选择 AUTO 可移除手工映射并恢复自动表头识别。"),
)

# Prefix patterns for dynamic labels.  The suffix/value is deliberately left
# untouched because it is usually a site/RMU/file identifier rather than prose.
ZH_PREFIXES: tuple[tuple[str, str], ...] = (
    ("Map Fields · ", "字段映射 · "),
    ("RMU Action Tracking · ", "RMU 处理跟踪 · "),
    ("Site: ", "站点："),
    ("Latest revision: ", "最新版本："),
    ("Issue / Action items: ", "问题 / 处理项："),
    ("RMU Follow-up: ", "RMU 跟踪："),
    ("Lifecycle: ", "生命周期："),
    ("Audit records: ", "审计记录："),
    ("Sign-off PDFs: ", "签字 PDF："),
    ("Sign-off history: ", "签字历史："),
    ("Sources: ", "数据源："),
    ("Mode: ", "模式："),
    ("Saudi ADMS Site: ", "Saudi ADMS 站点："),
    ("Inputs: ", "输入："),
    ("Missing: ", "缺失："),
    ("Error: ", "错误："),
    ("STANDARD unavailable: ", "STANDARD 不可用："),
    ("STANDARD already active: ", "STANDARD 已是当前版本："),
    ("Built-in STANDARD selected: ", "已选择内置 STANDARD："),
    ("Workspace index warning: ", "工作区索引警告："),
    ("Project Data confirmed: ", "项目数据已确认："),
    ("Project Data: ", "项目数据："),
    ("Source Workspace: ", "数据源工作区："),
    ("Sources refreshed · ", "数据源已刷新 · "),
    ("Source loaded · ", "数据源已加载 · "),
    ("Automatic source refresh failed · ", "自动数据源刷新失败 · "),
    ("Manual source mapping saved: ", "手工数据源映射已保存："),
    ("Validation complete · ", "校验完成 · "),
    ("Site revision created: ", "站点版本已创建："),
    ("Highlighted Need Action signal: ", "已高亮需处理信号："),
    ("Signal Mapping auto-load failed · ", "信号映射自动加载失败 · "),
    ("RMU Data Review auto-load failed · ", "RMU 数据审核自动加载失败 · "),
    ("Equipment Data Review load failed · ", "设备数据审核加载失败 · "),
    ("Ready · ", "就绪 · "),
    ("Working · ", "处理中 · "),
    ("Report folder: ", "报告目录："),
    ("Delivery status: ", "交付状态："),
    ("Move Columns · ", "移动字段 · "),
    ("Select exactly one Resolution for ", "请为以下项目选择且只能选择一个处理决议："),
    ("Stable App field: ", "稳定 App 字段："),
    ("Open RMU ", "打开 RMU "),
    ("Fields used by ", "使用字段："),
    ("Application STANDARD: ", "应用 STANDARD："),
    ("Calculated from site CSV + ADMS SLD + ", "基于站点 CSV + ADMS SLD + "),
    ("Active source file: ", "当前数据源文件："),
    ("Site scope: ", "站点范围："),
    ("Active: ", "当前："),
    ("Path: ", "路径："),
)


def _reverse_exact_translation(source: str) -> str:
    """Return a canonical English presentation string for rendered zh-CN.

    Besides exact dictionary values, a few runtime summaries use translated
    prefixes/tokens around identifiers and counts. Reversing those patterns is
    what makes zh-CN -> English switching immediate even after a page has
    refreshed dynamic labels while Chinese was active.
    """
    for english, chinese in ZH_CN.items():
        if source == chinese:
            return english

    # Some runtime tooltips append a known prose sentence after an identifier.
    # Reverse only the deliberately safe embedded prose fragments here. Never
    # replace every ZH_CN value as a substring: short values such as “关闭”,
    # “审核” or “版本” can occur inside a larger dynamic sentence and would
    # corrupt it before the structured reverse patterns below can match.
    restored_all = source
    for english, chinese in sorted(ZH_EMBEDDED, key=lambda item: len(item[1]), reverse=True):
        if chinese and chinese in restored_all:
            restored_all = restored_all.replace(chinese, english)
    if restored_all != source:
        source = restored_all

    match = re.match(r"^迁移报告 · 用户：(.*?) · 站点数据库：(.*)$", source)
    if match:
        return f"Migration Report · User: {match.group(1)} · Site DB: {match.group(2)}"
    match = re.match(r"^RMU 跟踪：未关闭 (\d+) · 已关闭 (\d+)$", source)
    if match:
        return f"RMU Follow-up: Open {match.group(1)} · Closed {match.group(2)}"
    match = re.match(r"^生命周期：未关闭 (\d+) · 已关闭 (\d+)$", source)
    if match:
        return f"Lifecycle: Open {match.group(1)} · Closed {match.group(2)}"
    match = re.match(r"^签字 PDF：(\d+) · 已签字：(\d+)$", source)
    if match:
        return f"Sign-off PDFs: {match.group(1)} · Signed: {match.group(2)}"
    match = re.match(r"^签字历史：已生成 (\d+) · 已签字 (\d+) · 最新版本 (.*)$", source)
    if match:
        return f"Sign-off history: {match.group(1)} generated · {match.group(2)} signed · latest revision {match.group(3)}"
    match = re.match(r"^交付状态：(.*?) · 当前可导出审核草稿；正式交付前请完成人工审核。$", source)
    if match:
        state = tr(match.group(1), LANG_EN)
        return f"Delivery status: {state} · Export is available as a review draft; complete Human Review before formal handover."
    match = re.match(r"^已选择站点：(.*)$", source)
    if match:
        return f"Site selected: {match.group(1)}"
    match = re.match(r"^行数 (\d+) · 更新时间 (.*?)(?: · 审核重置 (\d+))?$", source)
    if match:
        suffix = f" · Review reset {match.group(3)}" if match.group(3) else ""
        return f"Rows {match.group(1)} · Updated {match.group(2)}{suffix}"
    match = re.match(r"^行数：(\d+) · 列数：(\d+)(?: · 公式警告：(\d+)（首条：(.*)）)?$", source)
    if match:
        suffix = f" · Formula warnings: {match.group(3)} (first: {match.group(4)})" if match.group(3) else ""
        return f"Rows: {match.group(1)} · Columns: {match.group(2)}{suffix}"
    if source.startswith("自动加载失败 · "):
        return "Auto-load failed · " + source[len("自动加载失败 · "):]
    if source.startswith("数据源已加载 · ") and source.endswith(" · 需要校验"):
        middle = source[len("数据源已加载 · "):-len(" · 需要校验")]
        return f"Source loaded · {middle} · Validation required"
    match = re.match(r"^审核设备问题（(\d+)）$", source)
    if match:
        return f"Review Equipment Issues ({match.group(1)})"
    match = re.match(r"^审核信号不一致（(\d+)）$", source)
    if match:
        return f"Review Signal Mismatches ({match.group(1)})"
    match = re.match(r"^未映射文件（(\d+)）$", source)
    if match:
        return f"Unmapped Files ({match.group(1)})"
    match = re.match(r"^(.+?) 正在运行$", source)
    if match:
        return f"{match.group(1)} is already running"
    match = re.match(r"^RMU (.*?) 人工检查 (.*?) · 已保存$", source)
    if match:
        return f"RMU {match.group(1)} manual check {match.group(2)} · saved"
    match = re.match(r"^信号人工检查 (.*?) · RMU (.*?) · 已保存$", source)
    if match:
        return f"Signal manual check {match.group(1)} · RMU {match.group(2)} · saved"
    match = re.match(r"^已新增“(.+?)”。请选择其源字段后保存；该配置会应用到所有站点。$", source)
    if match:
        return f"Added '{match.group(1)}'. Choose its Source Field, then Save; both will apply to every station."
    match = re.match(r"^已移除“(.+?)”。保存后 App 表修改生效。$", source)
    if match:
        return f"Removed '{match.group(1)}'. Save to apply the App table change."
    match = re.match(r"^(.+?) 列顺序$", source)
    if match:
        return f"{match.group(1)} column order"
    match = re.match(r"^(.+?) · 新增审核备注$", source)
    if match:
        return f"{match.group(1)} · Add Review Comment"
    match = re.match(r"^(.+?) 需处理生命周期$", source)
    if match:
        return f"{match.group(1)} Need Action Lifecycle"
    match = re.match(r"^(.+?) 完整生命周期$", source)
    if match:
        return f"{match.group(1)} Full Lifecycle"
    match = re.match(r"^(.+?) 完整生命周期 · (.+)$", source)
    if match:
        return f"{match.group(1)} Full Lifecycle · {match.group(2)}"
    match = re.match(r"^(.+?) 生命周期 · (.+)$", source)
    if match:
        return f"{match.group(1)} Lifecycle · {match.group(2)}"
    match = re.match(r"^(.+?) 处理跟踪 · (.+)$", source)
    if match:
        return f"{match.group(1)} Action Tracking · {match.group(2)}"
    match = re.match(r"^已保存 · (.*)$", source)
    if match:
        return f"Saved · {match.group(1)}"
    match = re.match(r"^已导出 · (.*)$", source)
    if match:
        return f"Exported · {match.group(1)}"
    match = re.match(r"^将 (.+?) 指定为：$", source)
    if match:
        return f"Assign {match.group(1)} to:"
    match = re.match(r"^(.+?) 已保存到站点审计数据库。$", source)
    if match:
        return f"{match.group(1)} has been saved in the site audit database."
    if source.startswith("已签字副本保存至：\n\n"):
        return "Signed copy saved to:\n\n" + source[len("已签字副本保存至：\n\n"):]
    if source.startswith("记录中的 PDF 在以下位置不可用：\n\n"):
        return "The recorded PDF is not available at:\n\n" + source[len("记录中的 PDF 在以下位置不可用：\n\n"):]
    match = re.match(r"^当前 STANDARD：(.*?)。信号映射将基于当前所选数据源重新计算。$", source)
    if match:
        return f"Active STANDARD: {match.group(1)}. Signal Mapping will recalculate from current selected sources."
    match = re.match(r"^已记录设备 (.*?) 的审计项：(.*)$", source)
    if match:
        return f"Audit entry recorded for equipment {match.group(1)}: {match.group(2)}"
    match = re.match(r"^正在显示包含 (\d+) 条不一致信号的 RMU$", source)
    if match:
        return f"Showing RMUs containing {match.group(1)} mismatched signal row(s)"
    match = re.match(r"^已为 (.*?) 高亮 (\d+) 条 ADMS 实现记录。$", source)
    if match:
        return f"Highlighted {match.group(2)} ADMS implementation row(s) for {match.group(1)}."
    match = re.match(r"^已更新 (\d+) 条信号审核记录：(.*)$", source)
    if match:
        status = {"未审核": "UNREVIEWED", "已关闭": "CLOSED", "需处理": "NEEDS ACTION"}.get(match.group(2), tr(match.group(2), LANG_EN))
        return f"Signal Review updated for {match.group(1)} row(s): {status}"
    match = re.match(r"^检测到数据源变化 · (.*?) · 正在后台刷新$", source)
    if match:
        return f"Source change detected · {match.group(1)} · refreshing in background"
    match = re.match(r"^信号映射审核已就绪 · (\d+) 行$", source)
    if match:
        return f"Signal Mapping Review ready · {match.group(1)} row(s)"
    match = re.match(r"^(.*?)[：:]字段映射已保存，相关数据已刷新 · 全局映射已生效$", source)
    if match:
        return f"{match.group(1)}: field mapping saved and affected data refreshed · global mapping active"
    match = re.match(r"^已新增 (\d+) 个数据源文件 · 准备好后请运行校验$", source)
    if match:
        return f"Added {match.group(1)} source file(s) · Run Validation when ready"
    match = re.match(r"^设备审核已更新：(\d+) 行 → (.*)$", source)
    if match:
        status = {"未审核": "UNREVIEWED", "已关闭": "CLOSED", "需处理": "NEEDS ACTION"}.get(match.group(2), tr(match.group(2), LANG_EN))
        return f"Equipment Review updated: {match.group(1)} row(s) → {status}"
    match = re.match(r"^数据源已加载 · (.*?) · 校验前需要完成字段映射$", source)
    if match:
        return f"Source loaded · {match.group(1)} · Map Fields required before Validation"

    reverse_prefixes = tuple((zh, en) for en, zh in ZH_PREFIXES) + (
        ("状态 · ", "STATUS · "),
        ("最新版本：", "Latest version: "),
        ("审核进度：", "Review progress: "),
        ("上次扫描：", "Last scan: "),
        ("总数 ", "Total "),
        ("显示 ", "Shown "),
        ("剩余 ", "Remaining "),
        ("自动 → ", "AUTO → "),
        ("手动 → ", "MANUAL → "),
    )
    for zh_prefix, en_prefix in reverse_prefixes:
        if source.startswith(zh_prefix):
            return en_prefix + source[len(zh_prefix):]

    reverse_tokens = (
        ("审核进度", "Review progress"),
        ("RMU 审核", "RMU Review"),
        ("设备审核", "Equipment Review"),
        ("当前需处理", "Current Needs Action"),
        ("跟踪未关闭", "Follow-up Open"),
        ("存在问题", "With Issues"),
        ("未审核", "Unreviewed"),
        ("已关闭", "Closed"),
        ("需处理", "Needs Action"),
        ("一致率", "Match rate"),
        ("不一致", "Mismatched"),
        ("一致", "Matched"),
        ("行数：", "Rows:"),
        ("更新时间：", "Updated:"),
    )
    restored = source
    for zh_token, en_token in reverse_tokens:
        restored = restored.replace(zh_token, en_token)
    return restored



# v0.8.184 configurable-source/profile Chinese localization hardening.
# Engineering values, physical headers, profile names and filenames remain raw;
# only presentation text is localized.
ZH_CN.update({
    "Configuration Reuse / Inheritance": "配置复用 / 继承",
    "Mode": "配置模式",
    "Profile": "配置模板",
    "Local · this site only": "本地配置 · 仅当前站点",
    "Inherit global profile · explicit sync": "继承全局模板 · 手动同步",
    "Apply / Sync": "应用 / 同步",
    "Save Current as Profile...": "将当前配置保存为模板...",
    "Update Selected Profile": "更新所选模板",
    "Delete Profile": "删除模板",
    "A profile reuses source roles/order/titles, Key/Index defaults, Show/Hide defaults, default/per-field comparison modes and comparison field mappings. Physical file paths are never inherited; the target site keeps its own live files. Global profile changes never silently rewrite a site: press Apply / Sync, review the result, then Save & Rebuild Review.": "模板可复用数据源角色、顺序、标题、主键/索引默认值、字段显示/隐藏默认值、站点默认/字段级比较模式以及比较字段映射。模板绝不继承其他站点的物理文件路径；目标站点始终使用自己的实时源文件。全局模板更新不会静默改写站点配置：请先点击“应用 / 同步”，检查结果后再“保存并重建设备审核”。",
    "Available Site Files": "现场可用文件",
    "Refresh": "刷新",
    "Re-scan this site's folders for CSV/XLSX/XLSM files. Discovery never silently adds a file to a review.": "重新扫描当前站点目录中的 CSV/XLSX/XLSM 文件。新发现的文件只进入文件池，不会自动加入审核。",
    "Files may stay Unused, be added to Equipment Review, or be assigned to a Signal Mapping role. Optional Equipment/ and SignalMapping/ subfolders are supported.": "文件可以保持未使用，也可以加入设备数据审核，或指定给信号映射审核。支持可选的 Equipment/ 和 SignalMapping/ 子目录，但不强制要求目录结构。",
    "Add → Equipment": "加入设备审核",
    "Use for Signal...": "用于信号映射...",
    "Equipment Sources": "设备审核数据源",
    "Drag equipment sources to change their order. The order is saved with this site and used in comparison results.": "可拖动设备审核数据源调整顺序。顺序会随当前站点保存，并用于比较结果。",
    "Move Up": "上移",
    "Move Down": "下移",
    "Enable / Disable": "启用 / 禁用",
    "Participate in Equipment Data Review": "参与设备数据审核",
    "Review Participation": "审核参与状态",
    "Latest file in family (AUTO)": "同系列最新文件（自动）",
    "Pin this exact file": "固定使用当前文件",
    "Version Mode": "版本选择方式",
    "Automatically derived from filename; editable for similar versions": "根据文件名自动生成；同系列版本可手工调整",
    "File Family": "文件系列",
    "Active Source File": "当前源文件",
    "— Select reusable profile —": "— 请选择可复用模板 —",
    "Reusable Comparison Profile": "可复用对比模板",
    "Profile name:": "模板名称：",
    "Update Reusable Profile": "更新可复用模板",
    "Delete Reusable Profile": "删除可复用模板",
    "Apply Comparison Profile": "应用对比模板",
    "Select a profile first.": "请先选择一个模板。",
    "Site File Pool": "现场文件池",
    "Select a site file first.": "请先选择一个现场文件。",
    "Signal Mapping Source": "信号映射数据源",
    "Use selected file as:": "将所选文件用于：",
    "ZENON / IOA source": "ZENON / IOA 数据源",
    "ADMS SLD source": "ADMS SLD 数据源",
    "Version Selection": "版本选择",
    "Source version mode:": "数据源版本方式：",
    "Latest file in same family (AUTO)": "同系列最新文件（自动）",
    "Source": "数据源",
    "Unused": "未使用",
    "Equipment": "设备审核",
    "Equipment (disabled)": "设备审核（已禁用）",
    "Signal · IOA": "信号映射 · IOA",
    "Signal · ADMS SLD": "信号映射 · ADMS SLD",
    "latest": "最新",
    "Family:": "文件系列：",
    "Family versions:": "同系列版本：",
    "File:": "文件：",
    "Usage:": "用途：",
    "Resolved:": "当前解析：",
    "AUTO latest family resolution": "自动使用同系列最新版本",
    "Pinned physical file": "固定物理文件",
    "CSV / no worksheet": "CSV / 无工作表",
    "Select key / index field...": "请选择主键 / 索引字段...",
    "Column position:": "列位置：",
    "Physical header:": "物理表头：",
    "ON": "启用",
    "OFF": "禁用",
    "No source table configured yet.": "当前还没有配置设备审核数据源。",
    "Add at least one source table.": "请至少添加一个设备审核数据源。",
    "Enable at least one Equipment Data Review source.": "请至少启用一个设备数据审核数据源。",
    "Inheritance mode requires a reusable profile. Select a profile or switch Mode to Local.": "继承模式需要选择一个可复用模板。请选择模板，或将配置模式切换为本地配置。",
    "Equipment Data Review accepts any number of CSV/XLSX/XLSM tables. Each site independently defines source titles, worksheets, header rows, Key / Index fields, comparison rules and visible physical fields.": "设备数据审核支持任意数量的 CSV/XLSX/XLSM 数据表。每个站点可独立设置数据源标题、工作表、表头行、主键/索引字段、比较规则以及需要显示的物理字段。",
    "Equipment Data Review supports any number of configured CSV/XLSX/XLSM source tables. Each site chooses its own source files, Key / Index fields, comparison fields and visible columns while keeping the existing Analysis, Review Status, Resolution, Comments and Needs Action lifecycle workflow.": "设备数据审核支持任意数量的已配置 CSV/XLSX/XLSM 数据表。每个站点可自行选择源文件、主键/索引字段、比较字段和显示列，同时继续沿用现有的分析、审核状态、处理决议、备注和需处理生命周期流程。",
    "This dialog controls App/meta columns such as Index, Source Coverage, Analysis, Remarks and Resolution. Physical source columns follow the Show checkboxes in the configurable Equipment Data Review source editor, so each site has one visibility setting per source field. SYSTEM calculation fields are always visible because they feed matching, Analysis or validation. No source mapping, SQLite review data or exported report history is deleted by changing this view.": "此窗口用于控制索引、来源覆盖、分析、备注、处理决议等 App/元数据列。物理源字段的显示状态直接沿用“设备数据审核 · 可配置数据源”中的显示复选框，因此每个站点、每个数据源字段只有一套显示设置。SYSTEM 计算字段始终保持可见，因为它们参与匹配、分析或校验。修改显示设置不会删除任何源字段映射、SQLite 审核数据或已导出的报告历史。",
    "Equipment Data Review is fully configurable per site: add any number of CSV/Excel tables, choose each table's key/index field, and define the fields to compare. Every detected physical field is visible by default and may be hidden for that site. Source titles default to filenames and can be renamed. Signal Mapping Review keeps its existing source roles and mapping workflow. AUTO still uses published V versions / detection rules as convenient discovery hints. Click Source File to return to AUTO, pin a version, or browse any supported table. For Excel, Sheet defaults to AUTO (the source-preferred business sheet when available, otherwise the first usable sheet) and can be pinned per site without changing the global field mapping. File Path shows the reviewer-facing location. Fields Used shows exactly which App fields this module reads from that file. Missing source fields stay blank. Changing one Source File re-reads only that table. Refresh Sources re-scans versions and re-reads changed files; Run Validation force re-reads all active files. While the App is open, live file metadata is watched and changed inputs are refreshed in the background.": "设备数据审核按站点完全可配置：可加入任意数量的 CSV/Excel 数据表，为每张表选择自己的主键/索引字段，并自行定义需要比较的字段。识别到的物理字段默认全部显示，也可以仅在当前站点隐藏。数据源标题默认取文件名并允许修改。信号映射审核继续保留原有的数据源角色与映射流程。自动模式可根据同系列文件版本选择最新文件，也可以固定某个版本或浏览指定任意支持的表格。Excel 工作表可自动选择，也可按站点固定；文件路径始终指向审核人员实际使用的实时源文件。“本模块使用字段”显示 App 字段与物理字段的实际对应关系。缺失字段保持为空。替换单个源文件时只重读该表；刷新数据源会重新扫描文件版本并读取变化内容；运行校验会强制重读当前启用的数据源。应用运行期间也会监测实时文件变化并在后台刷新。",
    "CONFIGURED": "已配置",
    "CONFIGURABLE": "可配置",
    "NO TABULAR FILES": "未发现表格文件",
    "Data source count is configurable per site": "数据源数量由各站点自由配置",
    "Add/remove arbitrary Equipment Data Review source tables and configure each Key / Index, comparison field, title and site-local field visibility.": "新增或移除任意设备审核数据源，并配置每个数据源的主键/索引、比较字段、模块标题以及当前站点的字段显示状态。",
    "Map fields for the currently selected legacy Signal Mapping source. Equipment Data Review uses Configure Equipment Comparison.": "为当前选中的信号映射数据源配置字段映射。设备数据审核请使用“配置设备数据对比”。",
    "Reading configured Equipment Data Review source tables": "正在读取已配置的设备审核数据源",
    "Reading configured equipment source tables": "正在读取已配置的设备数据源",
    "Re-reading configured Equipment Data Review source tables": "正在重新读取已配置的设备审核数据源",
    "Configurable equipment review": "可配置设备审核",
    "Legacy equipment review": "旧版设备审核",
    # v0.8.186 generic equipment lifecycle, configurable recognition and export UI.
    "Total Equipment": "设备总数",
    "Equipment Needs Action Tracking": "设备需处理跟踪",
    "Equipment Follow-up: Open 0 · Closed 0": "设备跟踪：未关闭 0 · 已关闭 0",
    "Once any equipment enters Needs Action it stays in this follow-up register until that equipment is explicitly Closed. A later source refresh or Unreviewed reset does not silently remove the open follow-up item.": "任何设备一旦进入“需处理”，就会持续保留在此跟踪清单中，直到该设备被明确关闭。后续刷新数据源或重置为未审核，都不会静默移除仍未关闭的跟踪项。",
    "Equipment": "设备",
    "Type": "类型",
    "Category / Source Hint": "分类 / 数据源提示",
    "Filename Keywords": "文件名关键字",
    "Built-in hint": "内置提示",
    "Custom hint": "自定义提示",
    "Add Category": "新增分类",
    "Remove Category": "删除分类",
    "Source recognition is optional. Filename rules only provide discovery/classification hints; arbitrary filenames are supported and manual file selection plus Key/Index/comparison mapping always has priority. Add as many custom hint categories as needed.": "数据来源识别为可选功能。文件名规则只用于发现和分类提示；支持任意文件名，用户手工选择文件以及主键/索引/比较字段配置始终具有最高优先级。可按需要新增任意数量的自定义分类。",
    "Recognition hint:": "识别提示：",
    "No recognition hint": "无识别提示",
    "Choose Sign-off PDF Save Location": "选择签字 PDF 保存位置",
    "Choose Migration Report Save Location": "选择迁移报告保存位置",
    "Export location: choose a path when exporting": "导出位置：导出时由用户选择保存路径",
    "Equipment Data Summary": "设备数据汇总",
    "Equipment Need Action Register": "设备需处理清单",
    "Equipment Review": "设备审核",
    "View Full Equipment Lifecycle...": "查看完整设备生命周期...",
    "Equipment Lifecycle": "设备生命周期",
    "Configurable comparison mode uses the union of the configured Key / Index values. Legacy projects retain the historical Equipment Type filters until a configurable source contract is saved.": "可配置对比模式使用所有已配置主键 / 索引值的并集。旧项目在明确保存可配置数据源方案之前，仍保留原有设备类型筛选方式。",
    "Add/remove arbitrary CSV/Excel tables, choose each Key / Index field, comparison fields, source titles and site-local source-field visibility": "新增/移除任意 CSV/Excel 表，并配置每张表的主键 / 索引、比较字段、数据源标题以及当前站点字段显示状态",
    "Show or hide application/meta columns. Physical source fields are shown/hidden in Configure Sources.": "显示或隐藏应用/元数据列。实际源字段请在“配置数据源”中设置显示/隐藏。",
    "These rules are optional recognition hints, not source requirements. Filenames may be arbitrary; manual file selection, Key/Index and field mapping are authoritative. Built-in categories help legacy AUTO discovery, and you may add any number of extra categories for your own site/file families.": "这些规则只是可选的数据来源识别提示，并非数据源强制要求。文件名可以任意；手工选择文件以及主键/索引和字段映射始终具有最高优先级。内置分类仅用于兼容旧版自动发现，也可按现场/文件系列新增任意数量分类。",
    "Add Source Recognition Category": "新增数据来源识别分类",
    "Category name (for recognition/display only):": "分类名称（仅用于识别提示/显示）：",
    "Affected equipment by field:": "按字段统计受影响设备：",
    "Configured comparison fields use the same Unreviewed / Closed / Needs Action, Resolution, Comments and lifecycle workflow as the historical review.": "已配置的比较字段继续沿用原有的未审核 / 已关闭 / 需处理、处理决议、备注和生命周期工作流。",
    "Built-in recognition categories are kept for backward-compatible AUTO discovery. Clear their keywords to disable the filename hint; they are never mandatory.": "内置识别分类仅用于兼容旧版自动发现。清空关键字即可关闭对应文件名提示；这些规则从不作为强制条件。",
    "Export location: choose a save path for every Excel/PDF export": "导出位置：每次导出 Excel/PDF 时由用户选择保存路径",
    "Live Source": "实时数据源",
    "所选 PDF 是在校验/审核未完成时生成的 REVIEW DRAFT。\n\n请先重新运行“校验”并完成需要的人工审核，然后重新生成正式签字 PDF。": "所选 PDF 是在校验/审核未完成时生成的 REVIEW DRAFT。\n\n请先重新运行“校验”并完成需要的人工审核，然后重新生成正式签字 PDF。",
})

def tr(text: object, language: str | None = None) -> str:
    source = "" if text is None else str(text)
    lang = normalize_language(language if language is not None else current_language())
    if lang == LANG_EN:
        return _reverse_exact_translation(source)
    if source in ZH_CN:
        return ZH_CN[source]
    embedded = source
    for english, chinese in ZH_EMBEDDED:
        if english in embedded:
            embedded = embedded.replace(english, chinese)
    if embedded != source:
        source = embedded
    # Runtime-composed shell/history/export text. Keep identifiers and data
    # values unchanged while localizing the surrounding presentation labels.
    match = re.match(r"^Migration Report · User: (.*?) · Site DB: (.*)$", source)
    if match:
        return f"迁移报告 · 用户：{match.group(1)} · 站点数据库：{match.group(2)}"
    match = re.match(r"^Equipment Follow-up: Open (\d+) · Closed (\d+)$", source)
    if match:
        return f"设备跟踪：未关闭 {match.group(1)} · 已关闭 {match.group(2)}"
    match = re.match(r"^RMU Follow-up: Open (\d+) · Closed (\d+)$", source)
    if match:
        return f"RMU 跟踪：未关闭 {match.group(1)} · 已关闭 {match.group(2)}"
    match = re.match(r"^Lifecycle: Open (\d+) · Closed (\d+)$", source)
    if match:
        return f"生命周期：未关闭 {match.group(1)} · 已关闭 {match.group(2)}"
    match = re.match(r"^Sign-off PDFs: (\d+) · Signed: (\d+)$", source)
    if match:
        return f"签字 PDF：{match.group(1)} · 已签字：{match.group(2)}"
    match = re.match(r"^Sign-off history: (\d+) generated · (\d+) signed · latest revision (.*)$", source)
    if match:
        return f"签字历史：已生成 {match.group(1)} · 已签字 {match.group(2)} · 最新版本 {match.group(3)}"
    match = re.match(r"^Delivery status: (.*?) · Export is available as a review draft; complete Human Review before formal handover\.$", source)
    if match:
        state = tr(match.group(1), LANG_ZH_CN)
        return f"交付状态：{state} · 当前可导出审核草稿；正式交付前请完成人工审核。"
    match = re.match(r"^Site selected: (.*)$", source)
    if match:
        return f"已选择站点：{match.group(1)}"
    match = re.match(r"^Rows (\d+) · Updated (.*?)(?: · Review reset (\d+))?$", source)
    if match:
        suffix = f" · 审核重置 {match.group(3)}" if match.group(3) else ""
        return f"行数 {match.group(1)} · 更新时间 {match.group(2)}{suffix}"
    match = re.match(r"^Rows: (\d+) · Columns: (\d+)(?: · Formula warnings: (\d+) \(first: (.*)\))?$", source)
    if match:
        suffix = f" · 公式警告：{match.group(3)}（首条：{match.group(4)}）" if match.group(3) else ""
        return f"行数：{match.group(1)} · 列数：{match.group(2)}{suffix}"
    if source.startswith("Auto-load failed · "):
        return "自动加载失败 · " + source[len("Auto-load failed · "):]
    if source.startswith("Source loaded · ") and source.endswith(" · Validation required"):
        middle = source[len("Source loaded · "):-len(" · Validation required")]
        return f"数据源已加载 · {middle} · 需要校验"
    match = re.match(r"^Review Equipment Issues \((\d+)\)$", source)
    if match:
        return f"审核设备问题（{match.group(1)}）"
    match = re.match(r"^Review Signal Mismatches \((\d+)\)$", source)
    if match:
        return f"审核信号不一致（{match.group(1)}）"
    match = re.match(r"^Unmapped Files \((\d+)\)$", source)
    if match:
        return f"未映射文件（{match.group(1)}）"
    match = re.match(r"^(.+?) is already running$", source)
    if match:
        return f"{match.group(1)} 正在运行"
    match = re.match(r"^RMU (.*?) manual check (.*?) · saved$", source)
    if match:
        return f"RMU {match.group(1)} 人工检查 {match.group(2)} · 已保存"
    match = re.match(r"^Signal manual check (.*?) · RMU (.*?) · saved$", source)
    if match:
        return f"信号人工检查 {match.group(1)} · RMU {match.group(2)} · 已保存"
    match = re.match(r"^Added '(.+?)'\. Choose its Source Field, then Save; both will apply to every station\.$", source)
    if match:
        return f"已新增“{match.group(1)}”。请选择其源字段后保存；该配置会应用到所有站点。"
    match = re.match(r"^Removed '(.+?)'\. Save to apply the App table change\.$", source)
    if match:
        return f"已移除“{match.group(1)}”。保存后 App 表修改生效。"
    match = re.match(r"^(.+?) column order$", source)
    if match:
        return f"{match.group(1)} 列顺序"
    match = re.match(r"^(.+?) · Add Review Comment$", source)
    if match:
        return f"{match.group(1)} · 新增审核备注"
    match = re.match(r"^(.+?) Need Action Lifecycle$", source)
    if match:
        return f"{match.group(1)} 需处理生命周期"
    match = re.match(r"^(.+?) Full Lifecycle$", source)
    if match:
        return f"{match.group(1)} 完整生命周期"
    match = re.match(r"^(.+?) Lifecycle · (.+)$", source)
    if match:
        return f"{match.group(1)} 生命周期 · {match.group(2)}"
    match = re.match(r"^(.+?) Full Lifecycle · (.+)$", source)
    if match:
        return f"{match.group(1)} 完整生命周期 · {match.group(2)}"
    match = re.match(r"^(.+?) Action Tracking · (.+)$", source)
    if match:
        return f"{match.group(1)} 处理跟踪 · {match.group(2)}"
    match = re.match(r"^Saved · (.*)$", source)
    if match:
        return f"已保存 · {match.group(1)}"
    match = re.match(r"^Exported · (.*)$", source)
    if match:
        return f"已导出 · {match.group(1)}"
    match = re.match(r"^Assign (.+?) to:$", source)
    if match:
        return f"将 {match.group(1)} 指定为："
    match = re.match(r"^(.+?) has been saved in the site audit database\.$", source)
    if match:
        return f"{match.group(1)} 已保存到站点审计数据库。"
    if source.startswith("Signed copy saved to:\n\n"):
        return "已签字副本保存至：\n\n" + source[len("Signed copy saved to:\n\n"):]
    if source.startswith("The recorded PDF is not available at:\n\n"):
        return "记录中的 PDF 在以下位置不可用：\n\n" + source[len("The recorded PDF is not available at:\n\n"):]
    match = re.match(r"^Active STANDARD: (.*?)\. Signal Mapping will recalculate from current selected sources\.$", source)
    if match:
        return f"当前 STANDARD：{match.group(1)}。信号映射将基于当前所选数据源重新计算。"
    match = re.match(r"^Audit entry recorded for equipment (.*?): (.*)$", source)
    if match:
        return f"已记录设备 {match.group(1)} 的审计项：{match.group(2)}"
    match = re.match(r"^Showing RMUs containing (\d+) mismatched signal row\(s\)$", source)
    if match:
        return f"正在显示包含 {match.group(1)} 条不一致信号的 RMU"
    match = re.match(r"^Highlighted (\d+) ADMS implementation row\(s\) for (.*?)\.$", source)
    if match:
        return f"已为 {match.group(2)} 高亮 {match.group(1)} 条 ADMS 实现记录。"
    match = re.match(r"^Signal Review updated for (\d+) row\(s\): (.*)$", source)
    if match:
        return f"已更新 {match.group(1)} 条信号审核记录：{tr(match.group(2), LANG_ZH_CN)}"
    match = re.match(r"^(\d+) physical source column\(s\) loaded · one source column = one App row\.$", source)
    if match:
        return f"已加载 {match.group(1)} 个物理源字段 · 一个源字段对应一个 App 字段行。"
    match = re.match(r"^(\d+) physical source column\(s\) loaded\. Missing required system mapping\(s\): (.*?)\.$", source)
    if match:
        return f"已加载 {match.group(1)} 个物理源字段。缺少必要的系统映射：{match.group(2)}。"
    match = re.match(r"^Source change detected · (.*?) · refreshing in background$", source)
    if match:
        return f"检测到数据源变化 · {match.group(1)} · 正在后台刷新"
    match = re.match(r"^Signal Mapping Review ready · (\d+) row\(s\)$", source)
    if match:
        return f"信号映射审核已就绪 · {match.group(1)} 行"
    match = re.match(r"^(.*?): field mapping saved and affected data refreshed · global mapping active$", source)
    if match:
        return f"{match.group(1)}：字段映射已保存，相关数据已刷新 · 全局映射已生效"
    match = re.match(r"^Added (\d+) source file\(s\) · Run Validation when ready$", source)
    if match:
        return f"已新增 {match.group(1)} 个数据源文件 · 准备好后请运行校验"
    match = re.match(r"^Equipment Review updated: (\d+) row\(s\) → (.*)$", source)
    if match:
        return f"设备审核已更新：{match.group(1)} 行 → {tr(match.group(2), LANG_ZH_CN)}"
    match = re.match(r"^Source loaded · (.*?) · Map Fields required before Validation$", source)
    if match:
        return f"数据源已加载 · {match.group(1)} · 校验前需要完成字段映射"
    match = re.match(r"^Total (\d+) · Analog (\d+) · Status/Cmd (\d+)$", source)
    if match:
        return f"总数 {match.group(1)} · 模拟量 {match.group(2)} · 状态/命令 {match.group(3)}"
    match = re.match(r"^Needs Action history · Cases (\d+) · Open (\d+) · Closed (\d+) · Review comments (\d+)\. Earlier comments are retained and become visible here once the equipment has Needs Action history\. Signal Mapping is excluded for now\.$", source)
    if match:
        return f"需处理历史 · 周期 {match.group(1)} · 未关闭 {match.group(2)} · 已关闭 {match.group(3)} · 审核备注 {match.group(4)}。较早备注会继续保留；设备出现需处理历史后会在这里显示。当前不包含信号映射。"
    match = re.match(r"^Highlighted Need Action signal: (.*?)\.$", source)
    if match:
        return f"已高亮需处理信号：{match.group(1)}。"
    match = re.match(r"^(\d+) ZENON-only point\(s\) · (\d+) ADMS implementation\(s\) located(?: · (\d+) not found)?$", source)
    if match:
        suffix = f" · {match.group(3)} 个未找到" if match.group(3) else ""
        return f"仅 ZENON 存在点 {match.group(1)} 个 · 已定位 ADMS 实现 {match.group(2)} 个{suffix}"
    match = re.match(r"^(.+?) (.+?) Review comment added · history (\d+) record\(s\) · previous comments retained$", source)
    if match:
        return f"{match.group(1)} {match.group(2)} 已新增审核备注 · 历史记录 {match.group(3)} 条 · 以前的备注已保留"
    match = re.match(r"^Equipment Data Review ready · (.*?) · (\d+) row\(s\)$", source)
    if match:
        return f"设备数据审核已就绪 · {match.group(1)} · {match.group(2)} 行"
    match = re.match(r"^(.+?) (.+?) Resolution saved · Review: (.*?) · (.*)$", source)
    if match:
        return f"{match.group(1)} {match.group(2)} 处理决议已保存 · 审核：{tr(match.group(3), LANG_ZH_CN)} · {match.group(4)}"
    match = re.match(r"^Signal Mapping Review cannot load yet · missing (.*?)\. Configure it in Site Data Sources\.$", source)
    if match:
        return f"信号映射审核暂时无法加载 · 缺少 {match.group(1)}。请在站点数据源中完成配置。"

    # Common runtime-composed status strings. Translate only presentation
    # tokens; identifiers, filenames and numeric values remain untouched.
    dynamic_prefixes = (
        ("STATUS · ", "状态 · "),
        ("Status · ", "状态 · "),
        ("Latest version: ", "最新版本："),
        ("Review progress: ", "审核进度："),
        ("Last scan: ", "上次扫描："),
        ("Total ", "总数 "),
        ("Shown ", "显示 "),
        ("Remaining ", "剩余 "),
    )
    for prefix, translated in dynamic_prefixes:
        if source.startswith(prefix):
            suffix = source[len(prefix):]
            # Exact status suffixes are safe to translate recursively; the
            # recursion always receives a shorter string.
            return translated + (ZH_CN.get(suffix, suffix))
    for status in ("ACTION REQUIRED", "REVIEW PENDING", "SOURCES INCOMPLETE", "VALIDATION REQUIRED", "VALIDATION INCOMPLETE", "READY FOR EXPORT", "READY", "PARTIAL", "MISSING", "MAPPING REQUIRED", "UNREVIEWED", "CLOSED", "NEEDS ACTION"):
        if source == status:
            return ZH_CN.get(status, status)
        if source.startswith(status + "   ") or source.startswith(status + " · "):
            return ZH_CN.get(status, status) + source[len(status):]
    # Common runtime-composed dashboard/review sentences.  Replace only
    # presentation tokens; source identifiers and values are kept unchanged.
    dynamic_replacements = (
        ("Review progress", "审核进度"),
        ("RMU Review", "RMU 审核"),
        ("Equipment Review", "设备审核"),
        ("Remaining", "剩余"),
        ("Current Needs Action", "当前需处理"),
        ("Follow-up Open", "跟踪未关闭"),
        ("Affected RMUs by field", "按字段统计受影响 RMU"),
        ("No analysis mismatches", "无分析不一致"),
        ("Total", "总数"),
        ("Shown", "显示"),
        ("Pass", "通过"),
        ("With Issues", "存在问题"),
        ("Unreviewed", "未审核"),
        ("Closed", "已关闭"),
        ("Needs Action", "需处理"),
        ("Matched", "一致"),
        ("Mismatched", "不一致"),
        ("Match rate", "一致率"),
        ("Rows:", "行数："),
        ("Updated:", "更新时间："),
        ("Signal Review", "信号审核"),
        ("ADMS Points", "ADMS 点数"),
        ("ZENON Extra", "ZENON 额外"),
        ("Signals", "信号"),
        ("RMUs", "RMU"),
        ("Need Action", "需处理"),
        ("Analog", "模拟量"),
        ("Status/Cmd", "状态/命令"),
        ("Type", "类型"),
        ("Resolution", "处理决议"),
        ("Unresolved", "未处理"),
        ("Cases", "周期"),
        ("Current", "当前"),
        ("Participants", "参与人员"),
        ("Events", "事件"),
        ("Review comments", "审核备注"),
        ("mismatches", "不一致项"),
        ("issue decision(s)", "问题决议"),
    )
    if any(token in source for token, _translated in dynamic_replacements) and (" · " in source or ": " in source):
        translated_source = source
        for token, translated in dynamic_replacements:
            translated_source = translated_source.replace(token, translated)
        if translated_source != source:
            return translated_source
    # Generic equipment comment/lifecycle dialog titles.
    match = re.match(r"^(.+?) Review Comments$", source)
    if match:
        return f"{match.group(1)} 审核备注"
    match = re.match(r"^Resolve (.+?) Issues$", source)
    if match:
        return f"处理 {match.group(1)} 问题"
    match = re.match(r"^Review Comment History · (\d+) record\(s\)$", source)
    if match:
        return f"审核备注历史 · {match.group(1)} 条记录"
    match = re.match(r"^(.+?) · (\d+) issue(?:s)? require (\d+) Resolution decision(?:s)?$", source)
    if match:
        return f"{match.group(1)} · {match.group(2)} 个问题需要 {match.group(3)} 个处理决议"
    for prefix, translated in (("AUTO → ", "自动 → "), ("MANUAL → ", "手动 → ")):
        if source.startswith(prefix):
            return translated + source[len(prefix):]
    for prefix, translated in ZH_PREFIXES:
        if source.startswith(prefix):
            return translated + source[len(prefix):]
    return source


def _source_property(obj, name: str, current: str) -> str:
    """Return the language-neutral source text for a presentation property.

    Many labels in this application are runtime summaries (counts, selected
    site/source, validation state).  Earlier builds cached the very first label
    forever, so a later dynamic English update could be overwritten by stale
    text when the user switched language.  Treat a value that is neither the
    cached source nor its current translation as a new source string.
    """
    prop_name = f"_i18n_source_{name}"
    source = obj.property(prop_name)
    if source is None:
        source = current
        obj.setProperty(prop_name, source)
        return str(source)
    source = str(source)
    current = str(current or "")
    # Recognize both supported renderings regardless of which language has
    # already been written to QSettings.  The old implementation only compared
    # against the *new* current language; during zh-CN -> English it therefore
    # mistook the visible Chinese translation for a newly generated source
    # string and cached it permanently.
    known_renderings = {source, tr(source, LANG_EN), tr(source, LANG_ZH_CN)}
    if current and current not in known_renderings:
        source = tr(current, LANG_EN)
        obj.setProperty(prop_name, source)
    return source


def mark_combo_for_translation(combo: QComboBox) -> None:
    """Mark a business-key combo whose itemData stores language-neutral keys."""
    combo.setProperty("_i18n_translate_items", True)
    for i in range(combo.count()):
        if combo.itemData(i) is None:
            combo.setItemData(i, combo.itemText(i))


def translate_combo_items(combo: QComboBox, language: str) -> None:
    if not bool(combo.property("_i18n_translate_items")):
        return
    for i in range(combo.count()):
        source = combo.itemData(i)
        if source is None:
            source = combo.itemText(i)
            combo.setItemData(i, source)
        combo.setItemText(i, tr(source, language))


def translate_widget_tree(root: QWidget, language: str | None = None) -> None:
    """Translate presentation UI without translating auditable table body data.

    Table *body* values remain the original engineering/business tokens.  Normal
    UI/meta headers may be localized; the five physical source names and source
    field contracts are kept in their original English/source form by the
    source-table/grouped-header renderers.
    """
    lang = normalize_language(language if language is not None else current_language())

    widgets = [root] + root.findChildren(QWidget)
    for widget in widgets:
        if widget.isWindow():
            source = _source_property(widget, "window_title", widget.windowTitle())
            if source:
                widget.setWindowTitle(tr(source, lang))

        if isinstance(widget, QLabel):
            source = _source_property(widget, "text", widget.text())
            translated = tr(source, lang)
            if translated != widget.text():
                widget.setText(translated)
        elif isinstance(widget, QAbstractButton):
            source = _source_property(widget, "text", widget.text())
            widget.setText(tr(source, lang))
        elif isinstance(widget, QGroupBox):
            source = _source_property(widget, "title", widget.title())
            widget.setTitle(tr(source, lang))

        tooltip = widget.toolTip()
        if tooltip:
            source_tip = _source_property(widget, "tooltip", tooltip)
            translated_tip = tr(source_tip, lang)
            if translated_tip != widget.toolTip():
                widget.setToolTip(translated_tip)

        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            if placeholder:
                source_placeholder = _source_property(widget, "placeholder", placeholder)
                widget.setPlaceholderText(tr(source_placeholder, lang))
        if isinstance(widget, QComboBox):
            translate_combo_items(widget, lang)
        if isinstance(widget, QTabWidget):
            source_titles = widget.property("_i18n_source_tabs")
            if source_titles is None:
                source_titles = [widget.tabText(i) for i in range(widget.count())]
                widget.setProperty("_i18n_source_tabs", source_titles)
            for i, source_title in enumerate(list(source_titles or [])):
                if i < widget.count():
                    widget.setTabText(i, tr(source_title, lang))
        if isinstance(widget, QTableWidget):
            # Translate only the UI/meta header text. Table body values are
            # auditable data and are never rewritten. Physical source names and
            # engineering headers are painted raw by their dedicated renderers.
            for col in range(widget.columnCount()):
                item = widget.horizontalHeaderItem(col)
                if item is None:
                    continue
                key = f"_i18n_source_header_{col}"
                source_header = widget.property(key)
                if source_header is None:
                    source_header = item.text()
                    widget.setProperty(key, source_header)
                item.setText(tr(source_header, lang))

    for action in root.findChildren(QAction):
        source = _source_property(action, "text", action.text())
        action.setText(tr(source, lang))
