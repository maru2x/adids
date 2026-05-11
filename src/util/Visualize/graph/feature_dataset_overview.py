#!/usr/bin/env python3
"""Create overview plots and summary tables for a Zeek conn CSV leaf directory."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from .zeek_conn_leaf_common import (
        coerce_numeric_series,
        discover_csv_files,
        downsample_array,
        resolve_features,
        safe_name,
    )
except ImportError:
    from zeek_conn_leaf_common import coerce_numeric_series, discover_csv_files, downsample_array, resolve_features, safe_name


@dataclass
class FeatureStats:
    observed_count: int = 0
    missing_count: int = 0
    value_sum: float = 0.0
    value_sum_sq: float = 0.0
    min_value: float | None = None
    max_value: float | None = None

    def update(self, values: np.ndarray, row_count: int) -> None:
        valid_count = int(values.size)
        self.observed_count += valid_count
        self.missing_count += row_count - valid_count
        if valid_count == 0:
            return
        self.value_sum += float(values.sum())
        self.value_sum_sq += float(np.square(values).sum())
        current_min = float(values.min())
        current_max = float(values.max())
        self.min_value = current_min if self.min_value is None else min(self.min_value, current_min)
        self.max_value = current_max if self.max_value is None else max(self.max_value, current_max)

    def to_row(self, feature: str) -> dict[str, object]:
        total = self.observed_count + self.missing_count
        mean_value = self.value_sum / self.observed_count if self.observed_count else np.nan
        variance = (self.value_sum_sq / self.observed_count) - (mean_value ** 2) if self.observed_count else np.nan
        std_value = float(np.sqrt(max(variance, 0.0))) if self.observed_count else np.nan
        return {
            "feature": feature,
            "observed_count": self.observed_count,
            "missing_count": self.missing_count,
            "missing_rate": self.missing_count / total if total else np.nan,
            "min": self.min_value,
            "max": self.max_value,
            "mean": mean_value,
            "std": std_value,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a Zeek conn CSV leaf directory and save plots plus summary tables."
    )
    parser.add_argument("input_dir", help="Leaf CSV directory such as data/csv/zeek/conn/2201AusEast")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to exp/<leaf_name>_feature_overview next to the repo root.",
    )
    parser.add_argument(
        "--features",
        nargs="+",
        default=None,
        help="Numeric features to summarize. Defaults to current Zeek conn runtime vector features.",
    )
    parser.add_argument("--chunk-size", type=int, default=20000, help="CSV rows per chunk when streaming files.")
    parser.add_argument(
        "--max-samples-per-feature",
        type=int,
        default=20000,
        help="Maximum sampled values to keep per feature for histogram plots.",
    )
    parser.add_argument(
        "--time-bucket",
        default="1H",
        help="Pandas resample alias for traffic count plots, e.g. 1H or 30min.",
    )
    return parser.parse_args()


def resolve_output_dir(input_dir: Path, output_dir: str | None) -> Path:
    if output_dir:
        return Path(output_dir)
    return Path("exp") / f"{safe_name(input_dir.name)}_feature_overview"


def plot_hourly_counts(hourly_counter: Counter[pd.Timestamp], output_path: Path) -> None:
    if not hourly_counter:
        return
    hourly_series = pd.Series(hourly_counter).sort_index()
    plt.figure(figsize=(14, 6))
    plt.plot(hourly_series.index, hourly_series.values, linewidth=1.5)
    plt.xlabel("daytime")
    plt.ylabel("flow_count")
    plt.title("Flow Count Over Time")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_label_counts(label_counter: Counter[str], output_path: Path) -> None:
    if not label_counter:
        return
    labels = sorted(label_counter.keys())
    values = [label_counter[label] for label in labels]
    plt.figure(figsize=(8, 5))
    plt.bar(labels, values)
    plt.xlabel("label")
    plt.ylabel("count")
    plt.title("Label Distribution")
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def plot_histograms(feature_samples: dict[str, np.ndarray], histogram_dir: Path) -> None:
    histogram_dir.mkdir(parents=True, exist_ok=True)
    for feature, values in feature_samples.items():
        if values.size == 0:
            continue
        plt.figure(figsize=(8, 5))
        plt.hist(values, bins=50, edgecolor="black", alpha=0.8)
        plt.xlabel(feature)
        plt.ylabel("sample_count")
        plt.title(f"{feature} Distribution")
        plt.tight_layout()
        plt.savefig(histogram_dir / f"{safe_name(feature)}.png", dpi=200)
        plt.close()


def main() -> None:
    args = parse_args()
    csv_files = discover_csv_files(args.input_dir)
    features = resolve_features(csv_files, args.features)
    input_dir = Path(args.input_dir)
    output_dir = resolve_output_dir(input_dir, args.output_dir)
    plots_dir = output_dir / "plots"
    histogram_dir = plots_dir / "histograms"
    output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    feature_stats = {feature: FeatureStats() for feature in features}
    feature_samples = {feature: np.array([], dtype=float) for feature in features}
    hourly_counter: Counter[pd.Timestamp] = Counter()
    label_counter: Counter[str] = Counter()
    file_summaries: list[dict[str, object]] = []
    total_rows = 0
    invalid_daytime_rows = 0
    global_first_daytime: pd.Timestamp | None = None
    global_last_daytime: pd.Timestamp | None = None
    rng = np.random.default_rng(0)

    usecols = ["daytime", "label", *features]
    for csv_file in csv_files:
        file_rows = 0
        file_first_daytime: pd.Timestamp | None = None
        file_last_daytime: pd.Timestamp | None = None
        for chunk in pd.read_csv(csv_file, usecols=lambda column: column in usecols, chunksize=args.chunk_size):
            row_count = len(chunk.index)
            total_rows += row_count
            file_rows += row_count

            chunk_daytime = pd.to_datetime(chunk["daytime"], errors="coerce")
            valid_daytime = chunk_daytime.dropna()
            invalid_daytime_rows += row_count - len(valid_daytime.index)
            if not valid_daytime.empty:
                chunk_first = valid_daytime.min()
                chunk_last = valid_daytime.max()
                file_first_daytime = chunk_first if file_first_daytime is None else min(file_first_daytime, chunk_first)
                file_last_daytime = chunk_last if file_last_daytime is None else max(file_last_daytime, chunk_last)
                global_first_daytime = chunk_first if global_first_daytime is None else min(global_first_daytime, chunk_first)
                global_last_daytime = chunk_last if global_last_daytime is None else max(global_last_daytime, chunk_last)
                bucket_counts = valid_daytime.dt.floor(args.time_bucket).value_counts()
                for bucket, count in bucket_counts.items():
                    hourly_counter[bucket] += int(count)

            if "label" in chunk.columns:
                chunk_labels = chunk["label"].dropna().astype(str)
                for label, count in chunk_labels.value_counts().items():
                    label_counter[label] += int(count)

            for feature in features:
                numeric_series = coerce_numeric_series(chunk[feature]) if feature in chunk.columns else pd.Series(np.nan, index=chunk.index)
                values = numeric_series.dropna().to_numpy(dtype=float)
                feature_stats[feature].update(values, row_count)
                feature_samples[feature] = downsample_array(
                    feature_samples[feature],
                    values,
                    args.max_samples_per_feature,
                    rng,
                )

        file_summaries.append(
            {
                "file_name": csv_file.name,
                "row_count": file_rows,
                "first_daytime": file_first_daytime.isoformat() if file_first_daytime is not None else "",
                "last_daytime": file_last_daytime.isoformat() if file_last_daytime is not None else "",
            }
        )

    feature_summary_df = pd.DataFrame([feature_stats[feature].to_row(feature) for feature in features])
    feature_summary_df.to_csv(output_dir / "feature_summary.csv", index=False)
    pd.DataFrame(file_summaries).to_csv(output_dir / "file_summary.csv", index=False)

    label_count_df = pd.DataFrame(
        [{"label": label, "count": count} for label, count in sorted(label_counter.items())]
    )
    label_count_df.to_csv(output_dir / "label_counts.csv", index=False)

    hourly_count_df = pd.DataFrame(
        [{"bucket_start": bucket.isoformat(), "flow_count": count} for bucket, count in sorted(hourly_counter.items())]
    )
    hourly_count_df.to_csv(output_dir / "time_bucket_counts.csv", index=False)

    overall_summary = {
        "input_dir": str(input_dir),
        "file_count": len(csv_files),
        "total_rows": total_rows,
        "invalid_daytime_rows": invalid_daytime_rows,
        "first_daytime": global_first_daytime.isoformat() if global_first_daytime is not None else "",
        "last_daytime": global_last_daytime.isoformat() if global_last_daytime is not None else "",
        "features": features,
    }
    (output_dir / "overall_summary.json").write_text(
        json.dumps(overall_summary, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    plot_hourly_counts(hourly_counter, plots_dir / "flow_count_over_time.png")
    plot_label_counts(label_counter, plots_dir / "label_distribution.png")
    plot_histograms(feature_samples, histogram_dir)

    print(output_dir)


if __name__ == "__main__":
    main()
