import pytest

from src.util.DataModified.align_mix import align_and_mix_directories
from src.util.DataModified.csv_daytime_override import override_daytime
from src.util.DataModified.two_csv_combine import combine_csv_directories
from tests.e2e.data_modified._golden_helpers import (
    copy_fixture_case,
    assert_output_dir_matches_expected,
)


# Input:
# - A/B それぞれ複数 CSV を含む leaf ディレクトリ
# - expected/ には時系列 merge 後の chunk 分割済み CSV を置く
# Expectation:
# - daytime 順 merge と chunk 分割結果が golden fixture と一致する
# - 入力 fixture 側の CSV は変更されない
# Target script:
# - two_csv_combine.py
# Overview:
# - DataModified の実導線に近い形で combine 処理の最終出力レイアウトを固定する。
@pytest.mark.e2e
def test_two_csv_combine_matches_golden_output(tmp_path):
    case_root = copy_fixture_case(tmp_path, "combine_case")
    input_dir_a = case_root / "input_a"
    input_dir_b = case_root / "input_b"
    output_dir = case_root / "actual_output"
    expected_dir = case_root / "expected_output"

    original_a = (input_dir_a / "00000_202201010900.csv").read_text(encoding="utf-8")
    original_b = (input_dir_b / "00000_202201010900.csv").read_text(encoding="utf-8")

    combine_csv_directories(
        str(input_dir_a),
        str(input_dir_b),
        str(output_dir),
        chunk_size=3,
    )

    assert_output_dir_matches_expected(output_dir, expected_dir)
    assert (input_dir_a / "00000_202201010900.csv").read_text(encoding="utf-8") == original_a
    assert (input_dir_b / "00000_202201010900.csv").read_text(encoding="utf-8") == original_b


# Input:
# - 1 つの leaf CSV ディレクトリ
# - expected/ には baseline 平行移動後の CSV 群を置く
# Expectation:
# - daytime の平行移動結果と出力ファイル名が golden fixture と一致する
# - 入力 fixture 側の CSV は変更されない
# Target script:
# - csv_daytime_override.py
# Overview:
# - DataModified の実導線に近い形で daytime override の最終出力レイアウトを固定する。
@pytest.mark.e2e
def test_csv_daytime_override_matches_golden_output(tmp_path):
    case_root = copy_fixture_case(tmp_path, "daytime_override_case")
    input_dir = case_root / "input"
    output_dir = case_root / "actual_output"
    expected_dir = case_root / "expected_output"

    original_input = (input_dir / "00000_202201010900.csv").read_text(encoding="utf-8")

    override_daytime(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        baseline="2022-02-01 09:03:59",
    )

    assert_output_dir_matches_expected(output_dir, expected_dir)
    assert (input_dir / "00000_202201010900.csv").read_text(encoding="utf-8") == original_input


# Input:
# - 基準側 A と、別日収集の B を含む 2 つの leaf CSV ディレクトリ
# - expected/ には B を A の先頭時刻へ寄せてから merge した CSV 群を置く
# Expectation:
# - align_to=A に基づく shift と combine が 1 回の実行で完結し、golden fixture と一致する
# - 入力 fixture 側の CSV は変更されない
# Target script:
# - align_mix.py
# Overview:
# - よく使う「片側へ合わせてから混ぜる」運用を 1 コマンドで固定する。
@pytest.mark.e2e
def test_align_mix_matches_golden_output(tmp_path):
    case_root = copy_fixture_case(tmp_path, "align_mix_case")
    input_dir_a = case_root / "input_a"
    input_dir_b = case_root / "input_b"
    shifted_dir = case_root / "actual_shifted"
    output_dir = case_root / "actual_output"
    expected_dir = case_root / "expected_output"

    original_a = (input_dir_a / "00000_202201010900.csv").read_text(encoding="utf-8")
    original_b = (input_dir_b / "00000_202201021200.csv").read_text(encoding="utf-8")

    align_and_mix_directories(
        str(input_dir_a),
        str(input_dir_b),
        "A",
        str(shifted_dir),
        str(output_dir),
        chunk_size=3,
    )

    assert_output_dir_matches_expected(output_dir, expected_dir)
    assert (input_dir_a / "00000_202201010900.csv").read_text(encoding="utf-8") == original_a
    assert (input_dir_b / "00000_202201021200.csv").read_text(encoding="utf-8") == original_b
