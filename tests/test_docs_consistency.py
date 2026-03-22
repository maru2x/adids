import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"
DOCS_DIR = REPO_ROOT / "src" / "docs"

REQUIRED_DOCS = [
    "pcapファイルから特徴量を抽出する方法.md",
    "設定ファイルの各種パラメータ.md",
    "CSVスキーマ仕様.md",
    "実験結果ファイルの見方.md",
    "テスト方針.md",
    "開発タスク.md",
]

SHARED_COMMANDS = [
    "make pcap-to-log",
    "make log-to-csv",
    "make docs-check",
    "make test",
    "make run",
]

SHARED_INVARIANTS = [
    "DATASETS_DIR_PATH",
    "data/csv/unproc",
    "leaf",
]


class DocumentationConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README_PATH.read_text(encoding="utf-8")
        cls.agents = AGENTS_PATH.read_text(encoding="utf-8")
        cls.docs = {path.name: path.read_text(encoding="utf-8") for path in DOCS_DIR.glob("*.md")}

    def test_required_docs_exist(self):
        actual = set(self.docs.keys())
        missing = [name for name in REQUIRED_DOCS if name not in actual]
        self.assertEqual(missing, [], f"Missing required docs: {missing}")

    def test_readme_links_required_docs(self):
        for name in REQUIRED_DOCS:
            self.assertIn(f"src/docs/{name}", self.readme)

    def test_agents_lists_required_docs(self):
        for name in REQUIRED_DOCS:
            self.assertIn(f"`src/docs/{name}`", self.agents)

    def test_readme_and_agents_share_critical_commands(self):
        for command in SHARED_COMMANDS:
            self.assertIn(command, self.readme)
            self.assertIn(command, self.agents)

    def test_readme_and_agents_share_runtime_invariants(self):
        for token in SHARED_INVARIANTS:
            self.assertIn(token, self.readme)
            self.assertIn(token, self.agents)

    def test_agent_guide_defines_documentation_consistency_rule(self):
        for token in [
            "Documentation Consistency Rule",
            "Definition of Done",
            "README.md",
            "AGENTS.md",
            "src/docs/",
            "make docs-check",
        ]:
            self.assertIn(token, self.agents)


if __name__ == "__main__":
    unittest.main()
