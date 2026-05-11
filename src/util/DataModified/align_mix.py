import json
from pathlib import Path

try:
    from src.util.DataModified.csv_daytime_override import (
        DATETIME_FORMAT,
        collect_earliest_daytime,
        list_csv_files,
        override_daytime,
    )
    from src.util.DataModified.two_csv_combine import combine_csv_directories
except ModuleNotFoundError:
    from csv_daytime_override import (  # type: ignore
        DATETIME_FORMAT,
        collect_earliest_daytime,
        list_csv_files,
        override_daytime,
    )
    from two_csv_combine import combine_csv_directories  # type: ignore


SETTINGS_PATH = Path(__file__).with_name("settings.json")


def load_settings(settings_path=SETTINGS_PATH):
    with Path(settings_path).open("r", encoding="utf-8") as f:
        settings = json.load(f)
    return settings["AlignMix"]


def normalize_align_to(value):
    align_to = str(value).strip().upper()
    if align_to not in {"A", "B"}:
        raise ValueError(f"ALIGN_TO must be 'A' or 'B': {value}")
    return align_to


def validate_distinct_paths(*paths):
    resolved = [Path(path).resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("AlignMix paths must all be distinct.")


def resolve_baseline(input_dir):
    csv_files = list_csv_files(input_dir)
    earliest = collect_earliest_daytime(csv_files)
    return earliest.strftime(DATETIME_FORMAT)


def align_and_mix_directories(
    input_dir_a,
    input_dir_b,
    align_to,
    shifted_output_dir,
    output_dir,
    chunk_size,
):
    align_to = normalize_align_to(align_to)
    validate_distinct_paths(input_dir_a, input_dir_b, shifted_output_dir, output_dir)

    if align_to == "A":
        baseline = resolve_baseline(input_dir_a)
        override_daytime(input_dir_b, shifted_output_dir, baseline)
        combine_csv_directories(input_dir_a, shifted_output_dir, output_dir, chunk_size)
    else:
        baseline = resolve_baseline(input_dir_b)
        override_daytime(input_dir_a, shifted_output_dir, baseline)
        combine_csv_directories(shifted_output_dir, input_dir_b, output_dir, chunk_size)


def main():
    settings = load_settings()
    align_and_mix_directories(
        input_dir_a=settings["INPUT_DIR_A"],
        input_dir_b=settings["INPUT_DIR_B"],
        align_to=settings["ALIGN_TO"],
        shifted_output_dir=settings["SHIFTED_OUTPUT_DIR"],
        output_dir=settings["OUTPUT_DIR"],
        chunk_size=settings["CHUNK_SIZE"],
    )
    print("align mix complete")


if __name__ == "__main__":
    main()
