import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
README_PATH = ROOT_DIR / "README.md"
AGENTS_PATH = ROOT_DIR / "AGENTS.md"
MAKEFILE_PATH = ROOT_DIR / "Makefile"
SRC_TEST_DIR = ROOT_DIR / "src" / "test"

REQUIRED_DOCS = (
    "src/docs/設定ファイルの各種パラメータ.md",
    "src/docs/CSVスキーマ仕様.md",
    "src/docs/実験結果ファイルの見方.md",
    "src/docs/テスト方針.md",
    "src/docs/開発タスク.md",
    "src/docs/ユーティリティ利用方法.md",
)

AUTO_TEST_FILES = (
    "src/test/test_docs_consistency.py",
    "src/test/test_csv_daytime_override.py",
    "src/test/test_two_csv_combine.py",
)

README_AND_AGENTS_COMMANDS = (
    "make test",
    "make pcap-to-log",
    "make log-to-csv",
    "make run",
)


class DocsConsistencyTests(unittest.TestCase):
    def read_text(self, path):
        return path.read_text(encoding="utf-8")

    def test_required_docs_exist(self):
        for relative_path in REQUIRED_DOCS:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT_DIR / relative_path).exists(), f"Missing required doc: {relative_path}")

    def test_readme_and_agents_share_core_commands(self):
        readme_text = self.read_text(README_PATH)
        agents_text = self.read_text(AGENTS_PATH)
        for command in README_AND_AGENTS_COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, readme_text)
                self.assertIn(command, agents_text)

    def test_agents_and_makefile_expose_docs_check(self):
        agents_text = self.read_text(AGENTS_PATH)
        makefile_text = self.read_text(MAKEFILE_PATH)
        self.assertIn("make docs-check", agents_text)
        self.assertIn("docs-check:", makefile_text)

    def test_agents_lists_existing_auto_tests(self):
        agents_text = self.read_text(AGENTS_PATH)
        for relative_path in AUTO_TEST_FILES:
            with self.subTest(path=relative_path):
                self.assertTrue((ROOT_DIR / relative_path).exists(), f"Missing test file: {relative_path}")
                self.assertIn(f"- `{relative_path}`", agents_text)

    def test_makefile_points_docs_check_to_real_test_file(self):
        makefile_text = self.read_text(MAKEFILE_PATH)
        self.assertIn('src/test', makefile_text)
        self.assertIn("test_docs_consistency.py", makefile_text)
        self.assertTrue((SRC_TEST_DIR / "test_docs_consistency.py").exists())

    def test_src_test_top_level_is_reserved_for_auto_tests(self):
        allowed_directories = {"manual", "__pycache__"}
        for entry in SRC_TEST_DIR.iterdir():
            with self.subTest(entry=entry.name):
                if entry.is_dir():
                    self.assertIn(entry.name, allowed_directories)
                    continue
                self.assertEqual(entry.suffix, ".py")
                self.assertTrue(
                    entry.name.startswith("test_"),
                    f"Non-automated file should not live at src/test top level: {entry.name}",
                )


if __name__ == "__main__":
    unittest.main()
