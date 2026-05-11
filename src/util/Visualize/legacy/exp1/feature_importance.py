import os
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

# ディレクトリのパス
all_dir_path = "/mnt/nas0/g005/murasemaru/exp/1_DataAnalytics/drift/unproc"
output_dir = f"{all_dir_path}/res_img"  # 出力先のディレクトリを指定

# 相関係数を保存する辞書
corrs = {}
for dir_name in os.listdir(all_dir_path):
    if not dir_name == 'res_img':
        dir_path = os.path.join(all_dir_path, dir_name)
        if dir_name not in corrs:
            corrs[dir_name] = {}
        if os.path.isdir(dir_path):  # ディレクトリであることを確認
            for file in os.listdir(dir_path):
                if file.endswith('.csv'):
                    file_path = os.path.join(dir_path, file)
                    df = pd.read_csv(file_path)
                    if file not in corrs:
                        corrs[dir_name][file] = {}
                    # 各列の相関を計算
                    for column in df.columns:
                        if (
                            column not in ["mean_dis", "w_mean_dis", "ks_mean_dis","w_label","ks_label"]
                            and pd.api.types.is_numeric_dtype(df[column])
                        ):
                            
                            corrs[dir_name][file][column] = df[column].corr(df["mean_dis"])
                    
                    print(f"Processing: {file_path}")

x_keys = list(corrs.keys())
y_keys = list(corrs[x_keys[0]].keys())
z_keys = list(corrs[x_keys[0]][y_keys[0]].keys())

print(x_keys) # region
print(y_keys) # pop
print(z_keys) # feature

# 辞書を三次元配列に変換
three_d_array = np.array([
    [
        [corrs[x][y][z] for z in z_keys]
        for y in y_keys
    ]
    for x in x_keys
])

print(f"axis0(region): {np.shape(three_d_array)[0]}")
print(f"axis1(window_size): {np.shape(three_d_array)[1]}")
print(f"axis2(features): {np.shape(three_d_array)[2]}")

# reg次元を圧縮した pop - feature の mean_dis相関行列
pop_corr = np.mean(three_d_array,axis=0)
# pop次元を圧縮した reg - feature の mean_dis相関行列
reg_corr = np.mean(three_d_array, axis=1)
# pop次元，reg次元を圧縮した feature の mean_dis相関行列
res_corr = np.mean(np.mean(three_d_array, axis=0), axis=0)


print(f'pop: {np.shape(pop_corr)}')
print(pop_corr)
print(f'reg: {np.shape(reg_corr)}')
print(reg_corr)
print(f'res: {np.shape(res_corr)}')
print(res_corr)

print("compress w-ks")
mean_reg_corr = []
mean_pop_corr = []
mean_res_corr = []
columns = []

for i,z_key in enumerate(z_keys):
    p = z_key.split('_',1)
    if p[0] != 'w' and p[0] != 'ks':
        print(f"{z_key} : pass")
        columns.append("row_ct")
        mean_pop_corr.append(pop_corr[:,0])
        mean_reg_corr.append(reg_corr[:,0])
        mean_res_corr.append(res_corr[0])
    elif p[0] == 'w':
        columns.append(p[1])
        w_index = i
        target_key = f"ks_{p[1]}"
        ks_index = z_keys.index(target_key)
        print(target_key)
        print(f"w-index: {w_index}")
        print(f"ks-index: {ks_index}")
        pop_target_column = pop_corr[: , [w_index,ks_index]]
        reg_target_column = reg_corr[: , [w_index,ks_index]]
        mean_pop_corr.append(np.mean(pop_target_column, axis=1))
        mean_reg_corr.append(np.mean(reg_target_column, axis=1))
        mean_res_corr.append(np.mean([res_corr[w_index],res_corr[ks_index]]))
        print('... append')
    else:pass

mean_pop_corr = np.array(mean_pop_corr)
mean_reg_corr = np.array(mean_reg_corr)
mean_res_corr = np.array(mean_res_corr)
print(f'mean pop: {np.shape(mean_pop_corr)}')
print(f'mean reg: {np.shape(mean_reg_corr)}')
print(f'mean res: {np.shape(mean_res_corr)}')
print(mean_pop_corr)
print(mean_reg_corr)
print(mean_res_corr)
m_pop_df = pd.DataFrame(data=mean_pop_corr, columns=y_keys, index=columns)
m_reg_df = pd.DataFrame(data=mean_reg_corr, columns=x_keys, index=columns)
m_res_df = pd.Series(data=mean_res_corr, index=columns)

os.makedirs(output_dir, exist_ok=True)  # ディレクトリが存在しない場合は作成

# mean_reg_corrのヒートマップを保存
plt.figure(figsize=(10, 8))
sns.heatmap(m_reg_df, annot=True, cmap='coolwarm', fmt=".2f")
plt.title("mean reg corr")
plt.xticks(rotation=30, ha='right')  # 横軸ラベルを45度傾ける
plt.savefig(os.path.join(output_dir, "mean_reg_corr.png"))
plt.close()  # 描画を閉じる

# mean_pop_corrのヒートマップを保存
plt.figure(figsize=(10, 8))
sns.heatmap(m_pop_df, annot=True, cmap='coolwarm', fmt=".2f")
plt.title("mean pop corr")
plt.xticks(rotation=30, ha='right')  # 横軸ラベルを45度傾ける
plt.savefig(os.path.join(output_dir, "mean_pop_corr.png"))
plt.close()  # 描画を閉じる

# 棒グラフ
plt.figure(figsize=(10, 6))
plt.bar(m_res_df.index, m_res_df.values, color='orange', edgecolor='black')  # インデックスと値を指定
plt.title("Bar Plot of Data", fontsize=14)
plt.xlabel("Index", fontsize=12)
plt.ylabel("Value", fontsize=12)
plt.axhline(y=0, color='gray', linestyle='--', linewidth=0.8)  # y=0 の補助線
plt.xticks(rotation=30, ha='right')  # 横軸ラベルを回転
plt.savefig(os.path.join(output_dir, "mean_corr.png"))
plt.close()  # 描画を閉じる
