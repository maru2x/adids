#!/usr/bin/env python3
"""Compare Zeek conn sliding-window feature distributions against a reference distribution."""

from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, wasserstein_distance

try:
    from .zeek_conn_leaf_common import coerce_numeric_series, discover_csv_files, downsample_array, resolve_features, safe_name
except ImportError:
    from zeek_conn_leaf_common import coerce_numeric_series, discover_csv_files, downsample_array, resolve_features, safe_name


@dataclass
class WindowEntry:
    ts: pd.Timestamp
    value: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure feature drift for a Zeek conn CSV leaf directory by comparing sliding windows "
            "against the whole dataset or a selected reference range."
        )
    )
    parser.add_argument("input_dir", help="Leaf CSV directory such as data/csv/zeek/conn/2201AusEast")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to exp/<leaf_name>_sliding_drift next to the repo root.",
    )
    parser.add_argument(
        "--features",
        nargs="+",
        default=None,
        help="Numeric features to compare. Defaults to current Zeek conn runtime vector features.",
    )
    parser.add_argument(
        "--reference-dir",
        default=None,
        help="Optional reference leaf CSV directory. Defaults to the input directory itself.",
    )
    parser.add_argument("--reference-start", default=None, help="Optional inclusive daytime for reference filtering.")
    parser.add_argument("--reference-end", default=None, help="Optional inclusive daytime for reference filtering.")
    parser.add_argument("--window-hours", type=float, default=4.0, help="Sliding window width in hours.")
    parser.add_argument("--step-hours", type=float, default=1.0, help="Evaluation step size in hours.")
    parser.add_argument("--min-window-rows", type=int, default=200, help="Minimum rows required before evaluating drift.")
    parser.add_argument("--chunk-size", type=int, default=20000, help="CSV rows per chunk when streaming files.")
    parser.add_argument(
        "--max-reference-samples",
        type=int,
        default=20000,
        help="Maximum sampled values to keep per feature for the reference distribution.",
    )
    return parser.parse_args()


def resolve_output_dir(input_dir: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    return Path("exp") / f"{safe_name(input_dir.name)}_sliding_drift"


def parse_optional_daytime(raw: str | None) -> pd.Timestamp | None:
    if not raw:
        return None
    return pd.Timestamp(raw)


def build_reference_samples(
    csv_files: list[Path],
    features: list[str],
    reference_start: pd.Timestamp | None,
    reference_end: pd.Timestamp | None,
    chunk_size: int,
    max_reference_samples: int,
) -> tuple[dict[str, np.ndarray], int]:
    samples = {feature: np.array([], dtype=float) for feature in features}
    total_rows = 0
    rng = np.random.default_rng(0)
    usecols = ["daytime", *features]

    for csv_file in csv_files:
        for chunk in pd.read_csv(csv_file, usecols=lambda column: column in usecols, chunksize=chunk_size):
            daytime = pd.to_datetime(chunk["daytime"], errors="coerce")
            mask = daytime.notna()
            if reference_start is not None:
                mask &= daytime >= reference_start
            if reference_end is not None:
                mask &= daytime <= reference_end

            filtered = chunk.loc[mask]
            total_rows += len(filtered.index)
            for feature in features:
                values = coerce_numeric_series(filtered[feature]).dropna().to_numpy(dtype=float)
                samples[feature] = downsample_array(samples[feature], values, max_reference_samples, rng)

    return samples, total_rows


def plot_mean_drift(drift_df: pd.DataFrame, output_dir: Path) -> None:
    if drift_df.empty:
        return
    plt.figure(figsize=(14, 6))
    plt.plot(drift_df["window_end"], drift_df["mean_wasserstein"], label="mean_wasserstein", linewidth=1.5)
    plt.plot(drift_df["window_end"], drift_df["mean_ks"], label="mean_ks", linewidth=1.5)
    plt.xlabel("window_end")
    plt.ylabel("distance")
    plt.title("Sliding Window Drift Summary")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_dir / "mean_drift.png", dpi=200)
    plt.close()


def plot_feature_panels(drift_df: pd.DataFrame, features: list[str], output_dir: Path) -> None:
    feature_dir = output_dir / "feature_plots"
    feature_dir.mkdir(parents=True, exist_ok=True)
    for feature in features:
        w_col = f"{feature}_wasserstein"
        ks_col = f"{feature}_ks"
        if w_col not in drift_df.columns or ks_col not in drift_df.columns:
            continue
        plt.figure(figsize=(14, 5))
        plt.plot(drift_df["window_end"], drift_df[w_col], label="wasserstein", linewidth=1.2)
        plt.plot(drift_df["window_end"], drift_df[ks_col], label="ks", linewidth=1.2)
        plt.xlabel("window_end")
        plt.ylabel("distance")
        plt.title(feature)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(feature_dir / f"{safe_name(feature)}.png", dpi=200)
        plt.close()


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    csv_files = discover_csv_files(input_dir)
    features = resolve_features(csv_files, args.features)
    output_dir = resolve_output_dir(input_dir, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    reference_dir = Path(args.reference_dir) if args.reference_dir else input_dir
    reference_files = discover_csv_files(reference_dir)
    reference_start = parse_optional_daytime(args.reference_start)
    reference_end = parse_optional_daytime(args.reference_end)

    reference_samples, reference_row_count = build_reference_samples(
        reference_files,
        features,
        reference_start,
        reference_end,
        args.chunk_size,
        args.max_reference_samples,
    )
    if reference_row_count == 0:
        raise SystemExit("Reference distribution did not contain any rows in the selected range.")

    window_values = {feature: deque() for feature in features}
    window_rows: deque[pd.Timestamp] = deque()
    drift_rows: list[dict[str, object]] = []
    first_ts: pd.Timestamp | None = None
    next_eval: pd.Timestamp | None = None
    usecols = ["daytime", *features]

    for csv_file in csv_files:
        for chunk in pd.read_csv(csv_file, usecols=lambda column: column in usecols, chunksize=args.chunk_size):
            daytime = pd.to_datetime(chunk["daytime"], errors="coerce")
            numeric_columns = {
                feature: coerce_numeric_series(chunk[feature]) for feature in features if feature in chunk.columns
            }

            for row_index, ts in daytime.items():
                if pd.isna(ts):
                    continue
                if first_ts is None:
                    first_ts = ts
                    next_eval = ts + timedelta(hours=args.step_hours)

                window_rows.append(ts)
                for feature in features:
                    value = numeric_columns[feature].at[row_index]
                    if pd.notna(value):
                        window_values[feature].append(WindowEntry(ts=ts, value=float(value)))

                if next_eval is None:
                    continue

                while ts >= next_eval:
                    window_start = next_eval - timedelta(hours=args.window_hours)
                    while window_rows and window_rows[0] < window_start:
                        window_rows.popleft()
                    for feature in features:
                        feature_queue = window_values[feature]
                        while feature_queue and feature_queue[0].ts < window_start:
                            feature_queue.popleft()

                    drift_row: dict[str, object] = {
                        "window_end": next_eval,
                        "window_row_count": len(window_rows),
                    }

                    wasserstein_scores: list[float] = []
                    ks_scores: list[float] = []
                    if len(window_rows) >= args.min_window_rows:
                        for feature in features:
                            current_values = np.array([entry.value for entry in window_values[feature]], dtype=float)
                            reference_values = reference_samples[feature]
                            if current_values.size == 0 or reference_values.size == 0:
                                drift_row[f"{feature}_wasserstein"] = np.nan
                                drift_row[f"{feature}_ks"] = np.nan
                                continue

                            wasserstein_score = float(wasserstein_distance(current_values, reference_values))
                            ks_score = float(ks_2samp(current_values, reference_values).statistic)
                            drift_row[f"{feature}_wasserstein"] = wasserstein_score
                            drift_row[f"{feature}_ks"] = ks_score
                            wasserstein_scores.append(wasserstein_score)
                            ks_scores.append(ks_score)
                    else:
                        for feature in features:
                            drift_row[f"{feature}_wasserstein"] = np.nan
                            drift_row[f"{feature}_ks"] = np.nan

                    drift_row["mean_wasserstein"] = float(np.mean(wasserstein_scores)) if wasserstein_scores else np.nan
                    drift_row["mean_ks"] = float(np.mean(ks_scores)) if ks_scores else np.nan
                    drift_rows.append(drift_row)
                    next_eval += timedelta(hours=args.step_hours)

    drift_df = pd.DataFrame(drift_rows)
    drift_df.to_csv(output_dir / "sliding_window_drift.csv", index=False)
    plot_mean_drift(drift_df, output_dir)
    plot_feature_panels(drift_df, features, output_dir)

    summary = {
        "input_dir": str(input_dir),
        "reference_dir": str(reference_dir),
        "reference_start": reference_start.isoformat() if reference_start is not None else "",
        "reference_end": reference_end.isoformat() if reference_end is not None else "",
        "reference_row_count": reference_row_count,
        "window_hours": args.window_hours,
        "step_hours": args.step_hours,
        "min_window_rows": args.min_window_rows,
        "features": features,
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")

    print(output_dir)


if __name__ == "__main__":
    main()
