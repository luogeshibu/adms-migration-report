"""Compatibility facade for application services.

New code should import from schema/paths/parsers/storage/adapters/comparison/reporting directly.
The facade keeps the UI and third-party extensions stable while the project is modularized.
"""
from .schema import APP_NAME, APP_VERSION, DATA_GROUPS, COLUMNS, COMPARISON_GROUPS, COMPARISON_COLUMNS, EDITABLE_COLUMNS, REPORT_MERGES, REPORT_GROUP_STARTS, SOURCE_TYPES, COMPARISON_COLUMN_SCHEMA_VERSION, migrate_comparison_visible_columns
from .paths import app_root, resource_root, project_data_root, project_data_root_is_configured, confirm_project_data_root, set_project_data_root, workspace_root, is_inside_workspace
from .parsers import normalize_key, clean, read_csv_rows, read_excel_rows
from .storage import ProjectStore
from .adapters import SourceAdapter, WorkspaceFileAdapter, DBAPIQueryAdapter
from .comparison import list_index, build_comparison
from .importing import ImportResult, import_source
from .reporting import export_report

__all__ = [
    'APP_NAME','APP_VERSION','DATA_GROUPS','COLUMNS','COMPARISON_GROUPS','COMPARISON_COLUMNS','EDITABLE_COLUMNS','REPORT_MERGES','REPORT_GROUP_STARTS','SOURCE_TYPES','COMPARISON_COLUMN_SCHEMA_VERSION','migrate_comparison_visible_columns',
    'app_root','resource_root','project_data_root','project_data_root_is_configured','confirm_project_data_root','set_project_data_root','workspace_root','is_inside_workspace',
    'normalize_key','clean','read_csv_rows','read_excel_rows',
    'ProjectStore','SourceAdapter','WorkspaceFileAdapter','DBAPIQueryAdapter',
    'list_index','build_comparison','ImportResult','import_source','export_report'
]
