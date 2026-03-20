import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

# CSVファイルを読み込む
file_path = input("heatmap出力ツール: 対象CSVファイルのパスを入力してください: ")

# 入力ファイルの存在を確認
if not os.path.exists(file_path):
    print(f"エラー: 指定されたファイルが存在しません -> {file_path}")
    exit()

# 保存先のパスを設定
output_path = f'{os.path.dirname(file_path)}/{os.path.basename(file_path)}_heatmap.png'

# CSVファイルをデータフレームに読み込む
try:
    df = pd.read_csv(file_path, index_col=0)
except Exception as e:
    print(f"エラー: CSVファイルの読み込みに失敗しました -> {e}")
    exit()

# ヒートマップの作成
plt.figure(figsize=(12, 8))
sns.heatmap(
    df,
    cmap='coolwarm',
    annot=True,  # 数値を表示
    fmt='.2f',  # 小数点以下2桁まで表示
    cbar=True,
    annot_kws={"size": 14, "weight": "bold"}  # 数値を大きく太字に設定
)

# グラフのタイトル
plt.title(f'Heatmap of {os.path.basename(os.path.dirname(file_path))}/{os.path.basename(file_path)}', fontsize=18)

# 軸ラベルの回転とフォントサイズを設定
plt.xticks(rotation=45, ha='right', fontsize=14)  # 横軸ラベルを45度傾ける
plt.yticks(rotation=45, ha='right', fontsize=14)  # 縦軸ラベルも45度傾ける

# グラフの保存
plt.tight_layout()
plt.savefig(output_path, dpi=300)  # DPIを指定して高解像度で保存
plt.close()  # メモリを解放

print(f"ヒートマップを {output_path} に保存しました．")