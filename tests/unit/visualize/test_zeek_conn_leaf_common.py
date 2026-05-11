from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.util.Visualize.graph import zeek_conn_leaf_common as common


def test_discover_csv_files_returns_sorted_leaf_csvs(tmp_path):
    root = Path(tmp_path)
    (root / "b.csv").write_text("daytime\n", encoding="utf-8")
    (root / "a.csv").write_text("daytime\n", encoding="utf-8")
    (root / "note.txt").write_text("ignore\n", encoding="utf-8")

    csv_files = common.discover_csv_files(root)

    assert [path.name for path in csv_files] == ["a.csv", "b.csv"]


def test_resolve_features_uses_existing_default_features(tmp_path):
    root = Path(tmp_path)
    (root / "sample.csv").write_text(
        "daytime,duration,orig_bytes,label\n2022-01-01 00:00:00,1.0,10,0\n",
        encoding="utf-8",
    )

    features = common.resolve_features(common.discover_csv_files(root), None)

    assert features == ["duration", "orig_bytes"]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (pd.Series(["true", "false", "1", "0", "x"]), [1.0, 0.0, 1.0, 0.0, np.nan]),
        (pd.Series([True, False]), [1.0, 0.0]),
    ],
)
def test_coerce_numeric_series_handles_boolean_like_values(values, expected):
    result = common.coerce_numeric_series(values).tolist()

    for actual, exp in zip(result, expected):
        if np.isnan(exp):
            assert np.isnan(actual)
        else:
            assert actual == exp
