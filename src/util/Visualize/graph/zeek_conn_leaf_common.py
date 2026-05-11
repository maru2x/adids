from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_FEATURES = (
    "duration",
    "orig_bytes",
    "resp_bytes",
    "orig_pkts",
    "resp_pkts",
    "orig_ip_bytes",
    "resp_ip_bytes",
    "missed_bytes",
    "local_orig",
    "local_resp",
)

TRUTHY_VALUES = {"1", "true", "t", "yes", "y"}
FALSY_VALUES = {"0", "false", "f", "no", "n"}


def discover_csv_files(input_dir: str | Path) -> list[Path]:
    root = Path(input_dir)
    if not root.is_dir():
        raise SystemExit(f"CSV leaf directory not found: {root}")
    csv_files = sorted(path for path in root.iterdir() if path.is_file() and path.suffix == ".csv")
    if not csv_files:
        raise SystemExit(f"No CSV files found in leaf directory: {root}")
    return csv_files


def read_header(csv_files: list[Path]) -> list[str]:
    header = pd.read_csv(csv_files[0], nrows=0).columns.tolist()
    if not header:
        raise SystemExit(f"CSV header could not be read from: {csv_files[0]}")
    return header


def resolve_features(csv_files: list[Path], requested_features: list[str] | None) -> list[str]:
    header = read_header(csv_files)
    candidates = requested_features or list(DEFAULT_FEATURES)
    features = [feature for feature in candidates if feature in header]
    if not features:
        raise SystemExit(
            "No requested numeric features were found in the CSV header. "
            f"Requested={candidates}, header={header}"
        )
    return features


def coerce_numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(float)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    normalized = series.astype(str).str.strip().str.lower()
    truthy_mask = normalized.isin(TRUTHY_VALUES)
    falsy_mask = normalized.isin(FALSY_VALUES)

    result = pd.to_numeric(series, errors="coerce")
    result.loc[truthy_mask] = 1.0
    result.loc[falsy_mask] = 0.0
    return result


def safe_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe.strip("_") or "unknown"


def downsample_array(current: np.ndarray, additions: np.ndarray, max_size: int, rng: np.random.Generator) -> np.ndarray:
    if additions.size == 0:
        return current
    if current.size == 0:
        combined = additions
    else:
        combined = np.concatenate([current, additions])
    if combined.size <= max_size:
        return combined
    indices = rng.choice(combined.size, size=max_size, replace=False)
    return combined[indices]
