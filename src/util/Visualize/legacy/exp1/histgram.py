import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor

def plot_histograms(distributions, output_dir, dir_name):
    """分布データをヒストグラムとしてプロットし保存する"""
    os.makedirs(output_dir, exist_ok=True)
    for feature, data_list in distributions.items():
        combined_data = np.concatenate(data_list)
        plt.figure()
        plt.hist(combined_data, bins=30, alpha=0.7, edgecolor='black',color='red')
        output_path = os.path.join(output_dir, f"{feature}.png")
        plt.savefig(output_path,dpi=800)
        plt.close()
        print(f"ヒストグラムを保存しました: {output_path}")

def calculate_distributions(dir_path):
    """指定されたディレクトリ内のCSVファイルの特徴量分布を計算する"""
    distributions = {}
    for file_name in sorted(os.listdir(dir_path)):
        if file_name.endswith('.csv'):
            file_path = os.path.join(dir_path, file_name)
            data = pd.read_csv(file_path)
            for column in data.columns:
                if np.issubdtype(data[column].dtype, np.number):
                    if column not in distributions:
                        distributions[column] = []
                    distributions[column].append(data[column].dropna().values)
    return distributions

def process_directory(args):
    dir_name, all_dir_path, output_dir = args
    dir_path = f"{all_dir_path}/{dir_name}"
    dist = calculate_distributions(dir_path)
    each_output_dir = f"{output_dir}/{dir_name}"
    plot_histograms(dist, each_output_dir, dir_name)

if __name__ == "__main__":
    all_dir_path = input("分布を解析したいすべてのディレクトリが格納されたディレクトリパスを入力してください: ")
    output_dir = "/mnt/nas0/g005/murasemaru/exp/other/obs"

    # 並列処理のセットアップ
    dir_names = sorted(os.listdir(all_dir_path))
    args = [(dir_name, all_dir_path, output_dir) for dir_name in dir_names]

    with ProcessPoolExecutor() as executor:
        executor.map(process_directory, args)

    print("全てのディレクトリの処理が完了しました．")