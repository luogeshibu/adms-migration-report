from pathlib import Path

ROOT = Path(__file__).parents[1]
MAIN = (ROOT / 'src' / 'migration_report_tool' / 'ui' / 'main_window.py').read_text(encoding='utf-8')
PDF = (ROOT / 'src' / 'migration_report_tool' / 'infrastructure' / 'export' / 'signoff_pdf.py').read_text(encoding='utf-8')
VERSION = (ROOT / 'src' / 'migration_report_tool' / 'version.py').read_text(encoding='utf-8')


def _function_block(source: str, name: str, next_name: str) -> str:
    start = source.index(f'    def {name}(')
    end = source.index(f'    def {next_name}(', start)
    return source[start:end]


def test_pdf_rmu_open_list_has_no_comments_column():
    assert '<th>Modification Item</th>' in PDF
    assert '<th>Original Value</th>' in PDF
    assert '<th>Target Value</th>' in PDF
    assert '<th>Source</th>' in PDF
    assert '<th>Remarks</th>' in PDF
    block = PDF[PDF.index('def _rmu_action_tracking_rows'):PDF.index('def _signal_need_action_rows')]
    assert 'item.get("comments")' in block
    assert 'colspan="9"' in block
    assert 'manual_comment' in PDF

def test_rmu_status_and_manual_comment_do_not_full_refresh():
    status = _function_block(MAIN, 'set_comparison_review_status', 'edit_comparison_cell')
    comment = _function_block(MAIN, 'edit_rmu_manual_review_comment', 'set_comparison_review_status')
    assert 'self.refresh_all()' not in status
    assert 'self.refresh_all()' not in comment
    assert '_refresh_comparison_resolution_row' in status
    assert '_refresh_comparison_resolution_row' in comment
    assert '_commit=False' in status
    assert 'self.store.db.commit()' in status


def test_others_comment_does_not_rebuild_preview_each_keystroke():
    assert 'other_comment.textChanged.connect(refresh_preview)' not in MAIN


def test_version_bumped():
    assert '__version__ = "0.8.120"' in VERSION
