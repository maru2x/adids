import csv
import json
from datetime import datetime
from pathlib import Path


SETTINGS_PATH = Path(__file__).with_name("settings.json")
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def load_settings(settings_path=SETTINGS_PATH):
    with Path(settings_path).open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["DaytimeOverride"]


def list_csv_files(input_dir):
    csv_files = sorted(
        path for path in Path(input_dir).iterdir() if path.is_file() and path.suffix == ".csv"
    )
    if not csv_files:
        raise ValueError(f"No CSV files found in INPUT_DIR: {input_dir}")
    return csv_files


def parse_daytime(value, source_name):
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Invalid daytime value '{value}' in {source_name}. Expected format: {DATETIME_FORMAT}"
        ) from exc


def validate_output_dir(output_dir):
    output_path = Path(output_dir)
    if output_path.exists():
        if any(output_path.iterdir()):
            raise ValueError(f"OUTPUT_DIR must be empty before running: {output_dir}")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def collect_earliest_daytime(csv_files):
    earliest = None
    for csv_file in csv_files:
        with csv_file.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or "daytime" not in reader.fieldnames:
                raise ValueError(f"Missing 'daytime' column in {csv_file}")
            for row in reader:
                current = parse_daytime(row["daytime"], csv_file.name)
                if earliest is None or current < earliest:
                    earliest = current
    if earliest is None:
        raise ValueError(f"No data rows found in INPUT_DIR: {csv_files[0].parent}")
    return earliest


def shifted_filename(first_shifted_time, sequence):
    return f"{sequence:05d}_{first_shifted_time.strftime('%Y%m%d%H%M%S')}.csv"


def override_daytime(input_dir, output_dir, baseline):
    csv_files = list_csv_files(input_dir)
    output_path = validate_output_dir(output_dir)
    baseline_dt = datetime.strptime(baseline, DATETIME_FORMAT)
    earliest = collect_earliest_daytime(csv_files)
    shift = baseline_dt - earliest
    used_names = set()

    for sequence, csv_file in enumerate(csv_files):
        with csv_file.open("r", encoding="utf-8", newline="") as src:
            reader = csv.DictReader(src)
            rows = list(reader)
            if reader.fieldnames is None or "daytime" not in reader.fieldnames:
                raise ValueError(f"Missing 'daytime' column in {csv_file}")
        if not rows:
            continue

        first_shifted_time = None
        for row in rows:
            original = parse_daytime(row["daytime"], csv_file.name)
            shifted = original + shift
            row["daytime"] = shifted.strftime(DATETIME_FORMAT)
            if first_shifted_time is None:
                first_shifted_time = shifted

        output_name = shifted_filename(first_shifted_time, sequence)
        if output_name in used_names:
            raise ValueError(f"Duplicate output filename generated: {output_name}")
        used_names.add(output_name)

        with (output_path / output_name).open("w", encoding="utf-8", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def main():
    settings = load_settings()
    override_daytime(
        input_dir=settings["INPUT_DIR"],
        output_dir=settings["OUTPUT_DIR"],
        baseline=settings["BASELINE"],
    )
    print("daytime override complete")


if __name__ == "__main__":
    main()
