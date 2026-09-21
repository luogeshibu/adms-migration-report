# NARI Saudi ADMS Migration Report v0.8.215

## v0.8.215 修复 Admin 操作误报共享目录不可用

- Admin 状态读取、普通设置、强制接管和释放改用 Qt 后台线程执行，不再启动 Windows 多进程。
- 避免轻量共享 SQLite 操作因子进程启动/返回失败而显示“共享目录不可用”。
- 共享目录仍然保持非阻塞访问，按钮结果会直接刷新到当前页面。

## v0.8.214 增加 Admin 强制接管

- 新增 `Force Takeover Admin`，用于原 Admin 机器不可用、无法点击 Release Admin 的恢复场景。
- 强制接管前必须确认；普通 `Set as Admin` 仍然遵守持久锁定规则，不会自动抢占。
- 接管结果仍写入共享 Admin 记录，包含用户、机器名、IP 和客户端 ID。

## v0.8.213 Admin 改为持久锁定，不再依赖心跳

- 移除共享 Admin 的工作站心跳和在线列表。
- Admin 一旦写入共享库就持续有效，不会因为机器离线、关机或网络暂时中断而自动换人。
- 只有当前 Admin 主动点击 Release Admin 后，其他工作站才能接管；Admin 记录仍保存用户名、机器名、IP 和稳定客户端 ID。
- 保留旧心跳表结构以兼容已有共享数据库，但新版本不再读写心跳记录。

## v0.8.212 修复共享 Admin 按钮状态不刷新

- “设为 Admin”和“Release Admin”改为后台写入共享数据库，避免网络共享响应慢时卡住界面。
- 点击成功后立即更新当前窗口的 Admin 状态，不再因为旧的后台读取结果把按钮恢复成“设为 Admin”。
- 共享数据库仍以 `\\172.16.21.101\Share Folder\Downstream Report\_shared\global_settings.db` 为准。

## v0.8.211 打开共享站点不再自动移动源文件

- 选择站点时只读取目录，不再自动把根目录的 CSV/XLSX 移到 `source_files`。
- 同时兼容根目录源文件和 `source_files` 布局，避免共享文件被 Excel 或其他工作站占用时触发 WinError 32。
- 只有明确执行迁移/整理操作时才会复制或整理源文件。

## v0.8.210 共享盘加载超时与启动可恢复

- 共享目录索引、Admin 状态、工作站心跳和共享显示设置都有明确超时，不再因为断开的 Windows 共享盘无限 Loading。
- 启动阶段只在后台检查共享目录；检查失败会提示重新选择目录，主界面不会一直卡在忙碌状态。
- Admin 状态等非关键后台任务改为静默重试，不影响用户打开软件和继续查看审核记录。

## v0.8.209 修复 Windows 后台进程重复启动主界面

- Windows `spawn` 后台进程不再重复执行 `main.py` 和创建第二个主窗口。
- 修复后台 worker 与主界面互相等待造成的“未响应”和无法结束问题。

## v0.8.208 启动与退出稳定性

- 延迟共享 Admin 数据库读取，避免共享盘不可用时卡在启动画面。
- 共享 Admin 状态和工作站心跳改为独立后台进程读取/写入。
- 关闭窗口时停止后台任务并增加有界退出保护，避免残留 Python 进程。

## v0.8.207 设置页面自适应布局

- 设置页改为自适应宽度、垂直滚动布局，长文本会正常换行，卡片不会因窗口高度或 Windows 缩放比例变小而互相重叠。
- 保留大屏横向布局，同时兼容较小窗口、笔记本分辨率和 125%/150% 系统缩放。

## v0.8.206 同名用户识别与内网工作站在线发现

- Admin 身份以每台工作站的稳定 `client_id` 为准，同时显示用户名、机器名和内网 IP；两个工作站使用同一个 Windows 用户名也不会互相覆盖 Admin 权限。
- 每个运行中的 App 每 30 秒向共享目录 `_shared/global_settings.db` 写入一次轻量在线心跳，设置页显示最近 90 秒在线的工作站、用户、机器名、IP、版本和 Admin 标记。
- 工作站发现依赖已经存在的 Windows 共享目录，不做全网 IP 扫描、不需要 UDP 广播，也不需要额外开放防火墙端口；共享目录不可用时，心跳失败不会影响本地审核。
- 旧版共享数据库会自动创建心跳表，不删除既有模板、配置、Comments、Checked 或审核记录。

## v0.8.205 共享 Admin 身份与审核员权限收紧

- Admin 身份显示用户名、机器名和工作站 IP，解决多个工作站使用同名账号的问题。
- 非 Admin 只能选择站点/查看数据源并填写 Comments、Checked、Review、Resolution；不能选择或替换源文件、修改字段显示、映射、模板、STANDARD 或审核列配置。
- 旧版 `_shared/global_settings.db` 会自动增加 IP 字段，不删除既有模板和审核数据。

## v0.8.204 共享配置 Admin 模式

- 共享目录中的第一台工作站可以认领全局配置 Admin；同一共享目录下只有一个 Admin。
- Admin 维护设备审核配置、字段显示/隐藏、比较规则和全局模板；其他工作站自动同步并只读使用。
- Comments、Checked、Review、Resolution 和 Audit 记录继续允许所有用户写入，且仍保存在各站点自己的 `project.db` 中。
- Admin 可以主动释放权限，下一台工作站再认领；原有站点目录和历史数据不删除。

## Unified site migration

Settings includes a one-time **Prepare Transfer Package** action that can be used
at any review status. It combines a site's live CSV/Excel inputs with its existing `project.db` and `project.json`,
then stores source links as site-relative paths. Copy the resulting site folder
to another machine to retain Comments, Checked, Review, Resolution and Audit
history. New sites use the same in-place layout automatically; legacy split
Project Data sites remain compatible until migrated.

The organized site layout keeps source CSV/XLSX/XLSM files under
`source_files/`, generated deliverables under `reports/`, and
`project.db` / `project.json` at the site root. The whole site folder remains
the portable unit.

## v0.8.203 测试数据隔离与模板字段映射修复

- 测试运行时使用临时全局设置数据库，不再读取或修改共享盘中的真实模板、字段映射和显示隐藏配置。
- 正式工作站仍然使用共享仓库下的 `_shared/global_settings.db`，全局模板功能不变。
- 模板比较字段现在会随表头名称一起保存并在目标站点重新匹配。

## v0.8.202 全局模板字段映射与显示状态同步

- 模板同时保存物理字段的显示/隐藏状态和比较规则实际使用的表头名称。
- 应用模板到其他站点时，比较字段按字段 ID、表头和字段标签重新匹配，避免规则变成“—不参与比较—”。
- 目标站点确实没有字段时继续保留告警，不阻止其他配置保存。

- 全局比较模板现在同时保存隐藏字段的物理表头名称，不再只依赖某个站点生成的内部字段 ID。
- 将模板应用到其他站点时，会按字段 ID、表头和字段标签自动重新匹配，因此不同站点的 Excel 字段顺序或内部 ID 不同，也能同步显示/隐藏设置。
- 保存或更新模板时使用共享仓库下的 `_shared/global_settings.db`，所有连接到同一个共享仓库的应用都能选择同一套全局模板。
- 如果目标站点完全没有模板配置的字段，只显示告警，不阻止继续保存；模板不会保存其他站点的物理文件路径。

## v0.8.199 共享配置复用、字段告警与英文审核状态

全局比较配置现在会完整复用比较字段、归一化方式、启用状态和字段显示配置。目标站点缺少模板中的物理字段时保留配置并显示非阻塞告警，不会静默丢失规则。英文界面中的 Review 状态统一显示为 Unreviewed / Closed / Needs Action；中文界面继续显示为未审核 / 已关闭 / 需处理。

## v0.8.198 共享站点目录与站点内项目数据库

设备数据审核现在把“数据重算”和“用户操作”彻底分开。站点/数据源真正变化时才重新构建设备审核数据集；搜索、审核状态筛选、Analysis 筛选以及“显示全部”只对已加载行做本地显示/隐藏，不再启动后台进程、不再重新读取 Excel/CSV、不再重建整张表。

设备行、审核状态、Resolution、行索引和 Needs Action 跟踪键会在当前站点会话中缓存。设置 Review Status 时界面先立即更新，再由后台事务持久化；汇总计数和 Resolution 进度从缓存增量读取。点击普通设备行时，如果该设备从未进入 Needs Action，也不会再读取完整生命周期。

该优化不改变 Strict / Ignore Blank 比较结果、Resolution 与 Review Status 解耦、Comments 历史、Needs Action 生命周期、报告导出或列宽行为。


## v0.8.195 修复 Others 自定义处理决议无法保存

设备数据审核的处理决议窗口中，选择 **Others · custom resolution** 后，旧版会在真正写入 SQLite 之前引用未定义的 `field_label`，因此自定义处理意见和新 Customer Comment 看起来可以输入，但点击保存后无法落库。v0.8.195 已修复该分支：按当前比较字段动态取得显示名后再生成处理决议说明，并继续通过现有的一次事务同时保存 Resolution 与 Customer Comment。

如果“新增客户备注”留空，仍保持上一条已保存备注，不会生成重复历史。该修复不改变 v0.8.194 的异步 Excel 导出、Checked 批量后台写入、可选比较模式和 Needs Action 生命周期。


## v0.8.194 Excel 导出不再强制 Signal Mapping + 审核交互继续提速

设备数据审核和信号映射审核现在在 Excel 导出层面彻底解耦。站点即使只配置了设备审核的 CSV/XLSX/XLSM，没有 `ZENON-ADMS-IOA` 或 ADMS-SLD 信号映射输入，也可以正常导出迁移报告。工作簿仍保持五个固定 Sheet，`Signal Mapping Review` 在未配置时显示 `NOT CONFIGURED` 占位说明，而不是抛出 FileNotFoundError 阻断整个报告。

Excel 生成已经移到后台线程执行，OpenPyXL 构建和保存过程中主界面不再被同步阻塞。设备审核 Sheet 导出也移除了逐设备查询 Comments/Resolution 的 N+1 数据库访问：Review 与 Resolution 状态一次性预加载后再生成工作表。

Row Locator 的 `Checked / 已检查` 继续优化为 60ms 防抖批量写入：勾选后界面立即响应，多个连续勾选通过独立 ProjectStore 数据库连接在后台一次事务提交，SQLite 写锁等待不再发生在 Qt GUI 线程。Dashboard、Audit、Site History 和 Export 仍按需惰性刷新。



## v0.8.193 审核 Check 热路径性能优化

设备数据审核 Row Locator 的 **Checked / 已检查** 不再在每次点击后同步重建 Audit、Site History 和 Export 大表。勾选后只执行当前设备的轻量 SQLite 持久化并立即保留当前界面状态；Dashboard、Audit、Site History、Export 仅标记为待刷新，等用户真正打开对应页面时再更新。

普通设备如果从未进入过 Needs Action 生命周期，勾选 Check 时也不再构造完整生命周期快照，避免额外读取 comparison row、review row 和 resolution 数据。已有正式 Needs Action 历史的设备仍完整记录 CHECK_CHANGED 生命周期事件，审计语义不变。Signal Mapping 的 Checked 也采用同样的惰性页面刷新策略。

本版本不改变 Check 的业务含义、不改变 v0.8.192 比较模式、Review Status / Resolution 解耦、Comments、Needs Action 生命周期、导出、Profile 或列宽行为。

## v0.8.192 比较模式可选择：站点默认 + 字段级覆盖

设备数据审核的可配置 Comparison Rule 现在同时保留两套比较语义，并由用户配置：

- **严格一致 · 空值参与（Strict）**：所有已绑定数据源都参与；全部相同为 TRUE（包括全部为空）；空值/非空值混合或任意非空值不同为 FALSE。
- **忽略空值（Ignore Blank）**：恢复 v0.8.190 及以前的宽松逻辑；空值不参与比较，一个有效值也视为 TRUE；有效值彼此不同为 FALSE；全部为空时结果为 N/A/空白。

每个站点都有一个“默认比较模式”。每一条比较字段规则还可以选择“使用站点默认模式”，或单独强制为 Strict / Ignore Blank。因此同一个站点可以让 FEEDER、TYPE 使用严格模式，而 Manufacturer、SMART 等字段继续忽略空值。

已有 v0.8.191 配置升级后默认保持 **Strict**，不会因为升级自动改变现有 TRUE/FALSE 结果。全局比较模板/站点继承会同时保存站点默认模式以及每个字段的覆盖模式。

## v0.8.191 可配置比较改为严格空值一致性

设备数据审核的可配置 Comparison Rule 不再忽略空值。对每一个已绑定的数据源，空值也参与比较：全部相同（包括全部为空）为 TRUE；只要出现空值/非空值混合，或任意非空值不同，即为 FALSE。缺少该主键行的已绑定数据源按空值参与；未绑定到该比较规则的数据源不参与。

其余 v0.8.190 的自动列宽、手工列宽记忆，v0.8.189 的 Resolution 与 Review Status 解耦，以及审核生命周期、Comments、导出、Profile、Signal Mapping 均保持不变。


## v0.8.190 设备审核列宽自动适配

设备数据审核主表在保留 v0.8.188 手动拖拽列宽和持久化能力的基础上，新增**内容感知自动列宽**。每次完成当前设备数据集渲染后，程序会根据列标题、均匀采样的现场数据以及该字段的最长文本自动放大尚未被用户手工调整过的列；例如 `processed_name`、`Functional Location`、manufacturer、IP 以及任意动态 CSV/XLSX 字段不再只使用固定初始宽度。

自动适配以原 schema 宽度作为最小基准，并设置 520 px 上限，避免单个异常超长文本把整个表格撑坏。为保证 2,000+ 行现场的流畅性，不调用会遍历全部单元格的 `resizeColumnToContents()`：程序只对均匀样本和该字段的最长候选值进行字体宽度测量。搜索/筛选时使用完整当前设备数据集计算列宽，因此不会因为过滤结果变化而频繁跳动。

**用户手工列宽始终优先**：只要审核人员拖过某一列，该列就继续使用并持久化用户宽度，不会被自动适配覆盖。双击列头可清除该列的手工宽度并立即重新按当前内容自动适配。中文/英文列头 Tooltip 也提示拖拽和双击操作。

## v0.8.189 Review Status 与处理决议彻底解耦

设备审核中的 **处理决议（Resolution）** 只记录“这条问题最终采用什么处理方案”，不再自动修改审核状态。即使选择的值与 ADMS DB 完全一致，也不会自动 `CLOSED`；选择与 ADMS DB 不同的来源也不会自动进入 `NEEDS ACTION`。

审核状态由审核人员通过独立的“设置状态”操作明确维护：一旦人工标记为 `NEEDS ACTION`，后续选择来源、修改 Resolution 或补充 Comments 都不会把它自动关闭；只有审核人员明确改成 `CLOSED`（或人工改回 `UNREVIEWED`）时状态才变化。历史状态和生命周期记录不会被本版本批量改写。



## v0.8.188 Manual Equipment Review column resize

设备数据审核主表的所有业务列/来源字段列现在都支持直接拖拽表头分隔线调整列宽。像 `processed_name`、Functional Location、Manufacture、IP 或任意现场自定义 Excel/CSV 字段过长时，不再只能看省略内容。手工调整后的列宽按稳定字段键保存，刷新数据源、切换站点、动态重建列或重启软件后仍会恢复；隐藏/显示列不会清掉用户设置的宽度。

## v0.8.187 Review save responsiveness

- Selection/status dialogs now use explicit **Save / 保存** and **Cancel / 取消** buttons instead of the platform Qt `OK` translation that could appear as `正常`.
- Equipment Review Resolution/comment/status saves no longer rebuild the full Site History page while the reviewer is working in Equipment Data Review. Audit, Dashboard, Version, Site History and Export pages are marked dirty and refresh when opened.
- Single-equipment save/repaint paths query only that equipment's review record instead of loading the full review table.
- Manual comment saves update only the selected equipment row and its compact Needs Action timeline; they do not recalculate unrelated summary/resolution counters.
- Existing append-only Comments, Resolution, Needs Action lifecycle, audit history and persistence semantics are unchanged.

## v0.8.186 Recursive site source discovery

站点源文件状态和可配置文件池现在统一按站点目录递归发现 CSV/XLSX/XLSM；`Equipment/`、`SignalMapping/` 以及用户自行创建的更深层子目录都可以被发现，不再因文件不在站点根目录而显示“未发现表格文件”。


## v0.8.185 Configurable UX, explicit export paths, all-equipment tracking

- Equipment source configuration layout/presentation refined for the reusable-profile and live-source workflow.
- Every Migration Report Excel and sign-off PDF export requires an explicit Save As path selected by the user; formal exports are no longer silently written to the default reports directory.
- The actual external Excel export path/time is persisted so Dashboard delivery readiness remains correct even when the file is saved outside Project Data.
- Equipment Needs Action tracking now covers every equipment type, not only RMU. Once any equipment enters NEEDS ACTION, the existing durable lifecycle continues to track it until an explicit CLOSED transition.
- Sign-off PDF equipment summary/action register is generic across equipment types.
- Source-recognition rules are optional hints only. Physical filenames can be arbitrary; explicit user source assignment/configuration always wins.
- Source recognition categories are extensible rather than fixed to the historical SE/ZENON/ADMS roles.
- Preserves v0.8.184 Chinese localization/unlimited Equipment sources, v0.8.183 reusable profiles/inheritance, v0.8.182 direct live-source/no-copy behavior and no-wheel protection.

## v0.8.184 Chinese UI cleanup and unlimited Equipment source status

Chinese mode now fully localizes the configurable source/file-pool/profile workflow. UI labels and help text are Chinese, while source filenames, worksheet names, physical Excel/CSV headers, user-defined module/profile names and comparison-field names remain literal engineering data.

Equipment Data Review no longer presents a fixed source-count requirement in the station list. There is no `0/6`, `4/6` or similar legacy denominator: a site may use any number of enabled Equipment sources. Readiness for configurable Equipment Data Review is based on the sources that the user actually enabled plus the saved comparison rules. Disabled sources are excluded. Signal Mapping keeps its own independent input requirements and validation logic.

The Site Data Sources page, configurable comparison placeholder row, source-pool controls, profile inheritance controls, AUTO/pinned version controls, validation feedback and workflow detail are localized for Chinese mode. Existing v0.8.183 profile inheritance, v0.8.182 direct live-source reads/no-copy behavior, no-wheel protection, review lifecycle, audit and report/export behavior are unchanged.


## v0.8.183 reusable comparison profiles and site inheritance

Equipment Data Review comparison configuration can now be reused across stations without re-entering the same Key / Index and field mappings at every site. **Configuration Reuse / Inheritance** supports named application-wide profiles stored in `global_settings.db`. A profile contains logical source roles/order/titles, file-family hints, worksheet/header defaults, Key / Index defaults, Show/Hide defaults and comparison rules/bindings.

Physical CSV/XLSX/XLSM paths are **never** stored in a reusable profile. When a profile is applied at another station, the target station keeps its own live source paths; matching roles are resolved by stable source id, file family, then module title, and a new role can automatically bind to a matching file family in that station's file pool. Site-only extra sources are retained.

Two usage patterns are supported:

- **Local · this site only**: completely independent station configuration. A profile may still be applied once as a starting copy.
- **Inherit global profile · explicit sync**: the station records which reusable profile it inherits. Global profile changes are never pushed silently into reviewed station data. The station shows that a profile update is available; press **Apply / Sync**, review mappings, then **Save & Rebuild Review**.

A station can publish its current logical configuration with **Save Current as Profile...**, update the selected reusable profile, or delete a profile. Deleting a profile does not delete or rewrite any station's saved comparison configuration.


## v0.8.182 live source direct read and input safety

- Configurable Equipment Data Review sources are **references to the real CSV/XLSX/XLSM files**, not copies. The application saves the selected path/configuration and continues to store review/audit state in `project.db`, but it does not copy these source workbooks into Project Data/workspace.
- A five-second stat watcher observes active configured sources. If the same file is edited in place, or an AUTO family switches to a newer version, the application re-reads the live file and rebuilds the affected review projection in the background.
- Historical timestamped source copies from older releases are kept only for backward compatibility/audit; when the original/repository file can be resolved, configurable mode rebinds to that live file.
- Every `QComboBox` and spin-style value selector is protected application-wide from mouse-wheel changes. Reviewers must explicitly click/open or use the keyboard to change a selection. Normal table/page scrolling is not blocked.


## v0.8.181 flexible source pool

The station folder is now a **file pool**, not an implicit review contract. Press **Refresh** in Configure Equipment Comparison to discover CSV/XLSX/XLSM files. New files remain **Unused** until explicitly assigned. A file can be added to Equipment Data Review, or assigned to one of the existing Signal Mapping inputs. Equipment sources can be renamed, enabled/disabled without deletion, and switched between **Latest file in family (AUTO)** and **Pin this exact file**.

Optional folder organization is supported and recommended for larger sites:

```text
SITE/
  Equipment/
    SE.xlsx
    SE-V2.xlsx
    ZENON DB.xlsx
  SignalMapping/
    ZENON-ADMS-IOA.csv
    ADMS-SLD.xlsx
```

This layout is **not mandatory**. Existing flat station folders remain compatible. The application never moves or renames source files automatically.

## NARI Saudi ADMS Migration Report v0.8.179



### v0.8.179 source-selection synchronization fix

- Fixes the configurable source editor so clicking another source always refreshes Module Title, Source File, Worksheet, Header Row, Key / Index and physical fields from that exact source.
- Prevents programmatic QListWidget refresh from emitting nested selection changes.
- Saves the previous source editor by explicit source id before loading the newly selected source.
- No comparison semantics, review lifecycle, export, PDF, signal mapping, or site persistence rules are changed.

### v0.8.178 configurable Equipment Data Review sources

- **Equipment Data Review input is now 100% site-configurable.** It is no longer a hard-coded five-table contract (`SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD`). A station can add any number of `.csv`, `.xlsx` or `.xlsm` tables, using any filenames.
- Each source independently selects its **worksheet**, **header row** and **Key / Index Field**. Different files may use different physical key headers such as `DE_NAME`, `DeviceName`, `device_name`, `EQUIPMENT` or any other column.
- Reviewers create arbitrary **Comparison Rules**. A rule binds the physical field to compare from each participating source, so one logical check may compare differently named columns across files. Sources that do not participate in a rule can be left unbound.
- Comparison semantics remain the existing application rule: blank values are ignored; one available value is `TRUE`; multiple available values are `TRUE` when equal and `FALSE` when any available value differs. No new business-specific normalization is silently imposed on configurable fields.
- Every physical source field is **visible by default in configurable mode**. Show/Hide is stored per station and per source, and hiding is presentation-only; the raw value remains available for comparison/audit.
- A source/module title defaults to the selected filename and can be renamed by the reviewer. The Equipment Data Review grid automatically rebuilds its source groups, physical columns and Analysis columns from the active station configuration.
- The union of all configured source keys drives the review rows. Source coverage is calculated dynamically as `present/configured` instead of assuming five files.
- Existing downstream behavior is retained: review status, Checked, Unreviewed / Needs Action / Closed lifecycle, comments, resolutions, source-change audit, Excel/PDF reporting, sign-off flow and Signal Mapping remain on the existing v0.8.177 workflow.
- Existing v0.8.177 stations stay in legacy mode until a reviewer explicitly saves a configurable comparison. Opening the configuration dialog may offer current legacy files as an editable proposal, but **Cancel does not mutate the station**.

### v0.8.177 formal-build test isolation

- `build.ps1` now runs regression tests with an isolated build-local `MIGRATION_REPORT_TOOL_USER_DATA_ROOT` and `MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT`.
- Formal builds no longer read or mutate the operator's real `global_settings.db`, Map Fields mappings, visibility preferences, STANDARD selection, or persistent site project data.
- This removes machine-dependent regression failures where a valid production mapping such as `ZENON SLD Equipment Name -> DeviceName` caused legacy regression fixtures using `RMU`/`Feeder` headers to fail.
- The operator environment variables are restored in `finally` even when a regression test fails.
- Application business behavior from v0.8.176 is unchanged.

### v0.8.176 equipment identity semantic cleanup

- The protected SYSTEM identity is now displayed canonically as **Equipment Name**, never as the legacy presentation label **RMU**.
- The internal key `rmu` is retained only for database/project backward compatibility; it no longer defines the user-facing business meaning.
- System Mapping Assignments and protected-mapping confirmation dialogs use canonical business semantics, independent of user presentation labels or physical Excel headers.
- Legacy physical headers named `RMU` remain valid aliases and do not require source-file changes.

### v0.8.175 global Map Fields synchronization

Map Fields configuration is shared by source/App table across every station: explicit source mapping, App display names, Show/Hide and column order saved at one station are reused everywhere. Physical source files and Excel sheet selection remain station-specific.

### v0.8.174 reliable unlocked SYSTEM remapping

- Unlocking SYSTEM mappings now opens an explicit **System Mapping Assignments** editor covering every protected semantic, including required fields that have no automatic alias match in the current file.
- Non-standard physical headers such as `DE_NAME` can be deliberately bound to `Equipment Name` without adding phantom rows to the source-driven Map Fields table.
- After unlocking, the button remains enabled as **Edit System Mappings...** so the reviewer can reopen the editor at any time before Save.
- Save validation recognizes missing-to-manual protected changes and requires the existing second confirmation before persistence.
- Required schema errors now guide the reviewer back to SYSTEM mapping instead of leaving an unlocked dialog in a dead end.

### v0.8.173 source-version change lifecycle

- Once an equipment/RMU has ever entered **Needs Action**, later physical-source value changes are appended to its lifecycle whenever Refresh/Validation recalculates the comparison.
- Audit is field-diff based: only values that actually changed are recorded. Example: `ADMS SLD · TYPE: 2L1T → 3L1T`; unchanged FEEDER/SMART/etc. fields create no noise.
- Source provenance records the source role plus filename/version/hash, so switching `ADMS-SLD.xlsx → ADMS-SLD-V1.xlsx` or overwriting the same filename with new content can both be traced.
- A source change after a case is closed is appended to the latest historical case without reopening it. A later explicit **Needs Action** still opens the next equipment case.
- Equipment with no Needs Action history do not receive these lifecycle source-change events.
- AUTO file choice is version-first: the highest semantic filename suffix wins (`V3 > V2.9 > V1`); modification time is only a tie-breaker for the same version. If no valid V-version exists, the newest matching unversioned/canonical file is used. Explicit PIN/MANUAL selection overrides AUTO.


### v0.8.172 complete status lifecycle after Needs Action

- Once an equipment has entered Needs Action, later explicit states such as Unreviewed and Closed stay in its append-only lifecycle, including post-close changes.
- Automatic validation/source refresh resets to Unreviewed are also retained when Needs Action history exists.
- New Needs Action after a closed case still creates the next case; Unreviewed/Closed alone never reopens a formal case.
- Compact tracking uses equipment-scoped case labels such as `8881B-001`.

### v0.8.171 default-hide optional fields

- On first use of each source type, Map Fields now shows only SYSTEM calculation fields as enabled for Equipment Data Review.
- Every optional built-in/source-driven field starts hidden by default.
- Reviewers can still use **Show All Fields** or individual checkboxes; an explicit choice is persisted and respected on later opens.
- New Excel/CSV columns discovered later also start hidden unless explicitly shown.

### v0.8.170 review-draft export compatibility

- Restores the historical workflow where reports can still be exported while the project is `VALIDATION REQUIRED`, provided the user explicitly confirms a **review draft** export.
- The draft uses the most recently calculated review data stored in `project.db`; changed source files are not represented until Validation is run again.
- Sign-off PDFs generated in this state are visibly marked `REVIEW DRAFT · VALIDATION REQUIRED · NOT FOR FINAL HANDOVER / SIGNATURE` and use `_DRAFT_` in the filename.
- A draft PDF cannot be attached back as a signed formal report.
- If the project has never been validated and contains no calculated review rows, export remains blocked because there is no meaningful report data to export.
- Formal export behavior remains unchanged when the project reaches `READY FOR EXPORT`.

### v0.8.169 PDF issue-register contract

- RMU action PDF = one issue type / field per row.
- `Issue Type` replaces the ambiguous `Modification Item`.
- No `TBD` wording is emitted; unresolved values use explicit `Not specified` / `Not available in ADMS DB`.
- Manual Needs Action attempts to classify FEEDER / SMART / TYPE / IP / BRAND / DEVICE DATA / SOURCE DATA.
- PDF table rows are kept together at page boundaries and table headers repeat on continuation pages.


### v0.8.168 source visibility contract

Equipment Data Review now mirrors the current physical source header for each of the five equipment sources. Map Fields → Show is the authoritative visibility setting for physical source columns; absent physical columns never appear as phantom Review columns. SYSTEM calculation rows remain forced visible whenever that physical row exists.

This release makes Map Fields follow the real source table schema. If the active source sheet has 5 columns, Map Fields shows 5 rows. If the saved Excel/CSV later gains 3 columns, those 3 columns are discovered automatically and appear as new App rows. A newly discovered field defaults to the same App name as its physical header, while the App label can still be renamed afterward.

Canonical fields used by matching, Analysis, and validation remain SYSTEM-protected and always visible. Optional fields are hidden by default and can be shown from Map Fields without deleting mappings. The current dialog never creates extra phantom rows for columns that do not exist in the physical source file.

Map Fields no longer exposes a manual Add App Column action in this source-driven view. This guarantees that a 5-column source renders 5 rows, not 8 or 10 synthetic rows.

## v0.8.182 live-source rule

Equipment Data Review configurable sources and assigned Signal Mapping files are read **directly from the selected physical CSV/XLSX/XLSM path**. The application stores the path/configuration and review results in project data, but it does not create a new source-workbook copy for this workflow. If a selected file changes, the live-source watcher re-reads it. All drop-down and spin-style selection controls reject mouse-wheel value changes globally.
