import csv
import tempfile
from pathlib import Path

from migration_report_tool.infrastructure.parsers.legacy import feeder_matches_site
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.storage import ProjectStore


def _write_csv(path: Path, fieldnames, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def test_number_prefixed_repository_site_matches_real_station_token():
    assert feeder_matches_site('JED-NTH-ABH-03', '1-ABH') is True
    assert feeder_matches_site('JED-NTH-ABN2-03', '1-ABH') is False


def test_wrong_zenon_sld_feeder_is_not_filtered_out_before_validation():
    """Regression for site 1-ABH / RMU 34802 supplied by the user.

    FEEDER is the value under validation.  A wrong ZENON feeder must be shown as
    a mismatch, never converted into a blank/missing ZENON SLD row.
    """
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        adb = root / 'ADMS-DB.csv'
        zsld = root / 'ZENON-SLD.csv'
        _write_csv(adb, ['RMU_NAME', 'ADMS_GSS-FID', 'TYPE'], [
            {'RMU_NAME': '34802', 'ADMS_GSS-FID': 'JED-NTH-ABH-AH314', 'TYPE': '2L1T'},
        ])
        _write_csv(zsld, ['No.', 'XMLFile', 'CabinetType', 'Feeder', 'RMU', 'LinkName', 'SubstituteDestination', 'DuplicateCount', 'Warning'], [
            {'No.': '302', 'XMLFile': 'JEDDAH-ABH.XML', 'CabinetType': '2L1T',
             'Feeder': 'JED-NTH-FRDS-44', 'RMU': '34802', 'LinkName': '01_VERT_SRMU_2L1T_02',
             'SubstituteDestination': 'JED-NTH-FRDS-44-34802', 'DuplicateCount': '1', 'Warning': ''},
        ])
        store = ProjectStore(root / 'project')
        try:
            store.config['site_name'] = '1-ABH'
            store.config['repository_site'] = '1-ABH'
            store.save_config()
            store.set_source('adms_db', adb)
            store.set_source('zenon_sld', zsld)
            rows, _ = build_comparison(store)
            row = next(r for r in rows if r['rmu'] == '34802')
            assert row['zsld_rmu'] == '34802'
            assert row['zsld_type'] == '2L1T'
            assert row['zsld_feeder'] == 'JED-NTH-FRDS-44'
            assert row['analysis_feeder'] == 'FALSE'
            assert 'Missing: ZENON SLD' not in row['remarks']
            assert 'Analysis mismatch: FEEDER' in row['remarks']
        finally:
            store.db.close()






def test_declared_zenon_duplicate_count_remains_an_issue_when_csv_is_consolidated():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        adb = root / 'ADMS-DB.csv'
        zsld = root / 'ZENON-SLD.csv'
        _write_csv(adb, ['RMU_NAME', 'ADMS_GSS-FID', 'TYPE'], [
            {'RMU_NAME': '21453', 'ADMS_GSS-FID': 'JED-NTH-ABH-07', 'TYPE': '2L1T'},
        ])
        _write_csv(zsld, ['RMU', 'Feeder', 'CabinetType', 'DuplicateCount', 'Warning'], [
            {'RMU': '21453', 'Feeder': 'JED-NTH-ABH-07', 'CabinetType': '2L1T',
             'DuplicateCount': '2', 'Warning': '同一逻辑环网柜出现2个图元'},
        ])
        store = ProjectStore(root / 'project')
        try:
            store.config['site_name'] = '1-ABH'
            store.config['repository_site'] = '1-ABH'
            store.save_config()
            store.set_source('adms_db', adb)
            store.set_source('zenon_sld', zsld)
            rows, _ = build_comparison(store)
            row = next(r for r in rows if r['rmu'] == '21453')
            assert 'Duplicate: ZENON SLD' in row['remarks']
            assert row['status'] == 'FAILED'
        finally:
            store.db.close()
