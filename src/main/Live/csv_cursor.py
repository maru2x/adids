from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class CsvCursorState:
    initialized: bool = False
    file_row_counts: dict[str, int] = field(default_factory=dict)


class LiveCsvCursor:
    def __init__(self, output_dir: Path, state_path: Path, *, initial_position: str = "end"):
        self.output_dir = output_dir
        self.state_path = state_path
        self.initial_position = initial_position

    def collect_new_rows(self) -> list[dict[str, str]]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = self._load_state()
        csv_paths = sorted(self.output_dir.glob("*.csv"))

        if not state.initialized and self.initial_position == "end":
            state.file_row_counts = {
                path.name: self._count_rows(path)
                for path in csv_paths
            }
            state.initialized = True
            self._save_state(state)
            return []

        new_rows: list[dict[str, str]] = []
        new_counts: dict[str, int] = {}
        for path in csv_paths:
            processed_rows = state.file_row_counts.get(path.name, 0)
            row_count = 0
            with path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    if row_count >= processed_rows:
                        new_rows.append(row)
                    row_count += 1
            new_counts[path.name] = row_count

        state.file_row_counts = new_counts
        state.initialized = True
        self._save_state(state)
        return new_rows

    def _count_rows(self, path: Path) -> int:
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            return sum(1 for _row in reader)

    def _load_state(self) -> CsvCursorState:
        if not self.state_path.exists():
            return CsvCursorState()
        with self.state_path.open("r", encoding="utf-8") as fh:
            return CsvCursorState(**json.load(fh))

    def _save_state(self, state: CsvCursorState) -> None:
        with self.state_path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, ensure_ascii=True, indent=2)
