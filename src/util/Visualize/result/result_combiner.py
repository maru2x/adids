import pandas as pd
import os
import matplotlib.pyplot as plt

# ファイルの読み込み
csv1 = "exp/exp2-Eval/2201AusEast/st/results_evaluate.csv"  # static
csv2 = "exp/exp2-Eval/2201AusEast/dy2/results_evaluate.csv"  # dynamic
common_path = os.path.commonpath([csv1, csv2])
row_col_t = "daytime"
row_col = "accuracy"  # CSV1から結合したい列
label_size = 22
ticks_size = 16
legend_size = 22

df1 = pd.read_csv(csv1)  # ファイル1をデータフレームに読み込み
df2 = pd.read_csv(csv2)  # ファイル2をデータフレームに読み込み

# 列を取得
timestamp = df1[row_col_t]
row1 = df1[row_col]  # CSV1の指定列
row2 = df2[row_col]  # CSV2の指定列

# 水平方向に結合（DataFrameとして保存）
combined_row = pd.DataFrame({
    "daytime": timestamp,
    "static_accuracy": row1,
    "dynamic_accuracy": row2
})

# 結果を確認
print(combined_row)

# 保存ディレクトリの作成
output_dir = f"{common_path}/results"
os.makedirs(output_dir, exist_ok=True)

# CSVとして保存
output_csv_path = f"{output_dir}/combined_row.csv"
combined_row.to_csv(output_csv_path, index=False)
print(f"結合結果を保存しました: {output_csv_path}")

# グラフのプロット
plt.figure(figsize=(12, 8))
plt.plot(timestamp, row1, label="Static Accuracy")
plt.plot(timestamp, row2, label="Dynamic Accuracy")
plt.xlabel("Daytime",fontsize=label_size, rotation=45)
plt.ylabel("Accuracy",fontsize=label_size)
plt.title("Static vs Dynamic Accuracy")

plt.legend(fontsize=legend_size)
plt.grid(True)

# グラフの保存
output_plot_path = f"{output_dir}/accuracy_plot.png"
plt.savefig(output_plot_path,dpi=300)
plt.show()
print(f"グラフを保存しました: {output_plot_path}")
