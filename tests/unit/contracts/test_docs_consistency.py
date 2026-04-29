from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
README_PATH = ROOT_DIR / "README.md"
AGENTS_PATH = ROOT_DIR / "AGENTS.md"
MAKEFILE_PATH = ROOT_DIR / "Makefile"
UNIT_TEST_DIR = ROOT_DIR / "tests" / "unit"
MANUAL_TEST_DIR = ROOT_DIR / "tests" / "manual"

REQUIRED_DOCS = (
    "docs/設定ファイルの各種パラメータ.md",
    "docs/CSVスキーマ仕様.md",
    "docs/実験結果ファイルの見方.md",
    "docs/テスト方針.md",
    "docs/開発タスク.md",
    "docs/ユーティリティ利用方法.md",
)

AUTO_TEST_FILES = (
    "tests/unit/contracts/test_docs_consistency.py",
    "tests/unit/data_modified/test_csv_daytime_override.py",
    "tests/unit/data_modified/test_two_csv_combine.py",
    "tests/unit/feature_extract/test_pcap_to_log_extractor.py",
    "tests/unit/feature_extract/test_zeek_log_to_csv_extractor.py",
    "tests/e2e/feature_extract/test_zeek_pcap_to_csv.py",
    "tests/e2e/runtime/test_run_smoke.py",
)

README_AND_AGENTS_COMMANDS = (
    "make test",
    "make pcap-to-log",
    "make log-to-csv",
    "make run",
)


def read_text(path):
    return path.read_text(encoding="utf-8")


def test_required_docs_exist():
    for relative_path in REQUIRED_DOCS:
        assert (ROOT_DIR / relative_path).exists(), f"Missing required doc: {relative_path}"


def test_readme_and_agents_share_core_commands():
    readme_text = read_text(README_PATH)
    agents_text = read_text(AGENTS_PATH)
    for command in README_AND_AGENTS_COMMANDS:
        assert command in readme_text
        assert command in agents_text


def test_agents_and_makefile_expose_docs_check():
    agents_text = read_text(AGENTS_PATH)
    makefile_text = read_text(MAKEFILE_PATH)
    assert "make docs-check" in agents_text
    assert "docs-check:" in makefile_text


def test_agents_lists_existing_auto_tests():
    agents_text = read_text(AGENTS_PATH)
    for relative_path in AUTO_TEST_FILES:
        assert (ROOT_DIR / relative_path).exists(), f"Missing test file: {relative_path}"
        assert f"- `{relative_path}`" in agents_text


def test_makefile_points_docs_check_to_real_test_file():
    makefile_text = read_text(MAKEFILE_PATH)
    assert "pytest" in makefile_text
    assert "test_docs_consistency.py" in makefile_text
    assert (UNIT_TEST_DIR / "contracts" / "test_docs_consistency.py").exists()


def test_tests_layout_separates_unit_and_manual():
    assert UNIT_TEST_DIR.is_dir()
    assert MANUAL_TEST_DIR.is_dir()
    allowed_directories = {"__pycache__", "contracts", "data_modified", "feature_extract"}
    for entry in UNIT_TEST_DIR.iterdir():
        if entry.is_dir():
            assert entry.name in allowed_directories
            continue
        raise AssertionError(f"tests/unit top level should contain directories only: {entry.name}")
