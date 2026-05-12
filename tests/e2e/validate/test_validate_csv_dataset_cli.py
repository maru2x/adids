import subprocess
import sys
import json
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT_DIR / "src" / "util" / "Validate" / "validate_csv_dataset.py"
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "validate"
VALIDATE_SETTINGS_PATH = ROOT_DIR / "src" / "util" / "Validate" / "settings.json"


@pytest.mark.e2e
def test_validate_csv_dataset_cli_reports_ok_for_valid_fixture():
    original_settings = VALIDATE_SETTINGS_PATH.read_text(encoding="utf-8")
    try:
        settings = {
            "CsvDatasetValidator": {
                "DATASET_DIR_PATH": str(FIXTURE_DIR / "valid_zeek_leaf"),
                "SCHEMA": "zeek",
                "RUNTIME_SETTINGS_PATH": str(ROOT_DIR / "src" / "main" / "settings.json"),
            }
        }
        VALIDATE_SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        VALIDATE_SETTINGS_PATH.write_text(original_settings, encoding="utf-8")

    assert result.returncode == 0
    assert "[runtime契約チェック]" in result.stdout
    assert "総合判定: 合格" in result.stdout
    assert "[データサマリ]" in result.stdout


@pytest.mark.e2e
def test_validate_csv_dataset_cli_reports_ng_for_invalid_fixture():
    original_settings = VALIDATE_SETTINGS_PATH.read_text(encoding="utf-8")
    try:
        settings = {
            "CsvDatasetValidator": {
                "DATASET_DIR_PATH": str(FIXTURE_DIR / "invalid_time_order_leaf"),
                "SCHEMA": "zeek",
                "RUNTIME_SETTINGS_PATH": str(ROOT_DIR / "src" / "main" / "settings.json"),
            }
        }
        VALIDATE_SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        VALIDATE_SETTINGS_PATH.write_text(original_settings, encoding="utf-8")

    assert result.returncode == 1
    assert "[runtime契約チェック]" in result.stdout
    assert "総合判定: 不合格" in result.stdout
    assert "CSV ファイル間で daytime が逆行しています" in result.stdout
