import csv
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT_DIR / "tests" / "fixtures" / "data_modified"


def read_csv_content(path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return reader.fieldnames or [], rows


def copy_tree(source, destination):
    shutil.copytree(source, destination)
    return destination


def copy_fixture_case(tmp_path, case_name):
    source = FIXTURE_DIR / case_name
    case_root = Path(tmp_path) / case_name
    return copy_tree(source, case_root)


def assert_csv_file_matches_expected(actual_path, expected_path):
    actual_header, actual_rows = read_csv_content(actual_path)
    expected_header, expected_rows = read_csv_content(expected_path)
    assert actual_header == expected_header
    assert actual_rows == expected_rows


def assert_output_dir_matches_expected(actual_dir, expected_dir):
    actual_files = sorted(path.name for path in Path(actual_dir).glob("*.csv"))
    expected_files = sorted(path.name for path in Path(expected_dir).glob("*.csv"))
    assert actual_files == expected_files
    for file_name in expected_files:
        assert_csv_file_matches_expected(
            Path(actual_dir) / file_name,
            Path(expected_dir) / file_name,
        )
