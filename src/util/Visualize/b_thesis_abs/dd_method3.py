from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
import numpy as np
import os
import japanize_matplotlib

# プロットするデータ
current_points = [
    (1.4, 1.32, 1.85), #1
    (1.75, 1.42, 1.25), #2
    (0.25, 1.54, 0) #3
]

past_points = [
    (0.65, 1.22, -0.10), #1
    (-0.1, 0.1, 1), #2
    (0.50, -0.30, 0.83), #3
    (-0.6, 2.1, 0.1), #4
    (0.95, 1.01, 1.08) #5
]

past_delete_points = (0.62, 0.4, -0.02)

# 保存先
output_path = '/mnt/nas0/g005/murasemaru/exp/other'
file_name = 'dd_method3.png'
if not os.path.exists(output_path):
    os.makedirs(output_path)

# グラフの描画
fig = plt.figure(figsize=(10, 8))
ax = fig.add_subplot(111, projection='3d')

for i, (x, y, z) in enumerate(past_points):
    ax.scatter(x, y, z, color='red', alpha=0.7, s=300)

# 現在データをプロット
for i, (x, y, z) in enumerate(current_points):
    ax.scatter(x, y, z, color='green', alpha=0.7, s=300)

ax.scatter(past_delete_points[0], past_delete_points[1], past_delete_points[2], facecolors='none', edgecolors='red', linewidths=2, linestyle='--', alpha=0.7, s=300)

# 軸範囲を設定（データ範囲に基づいて適切な範囲を選択）
ax.set_xlim(-1, 2)
ax.set_ylim(-1, 2)
ax.set_zlim(-1, 2)

# 軸目盛りを一定間隔で設定
ax.set_xticks(np.arange(-1, 2.5, 0.5))
ax.set_yticks(np.arange(-1, 2.5, 0.5))
ax.set_zticks(np.arange(-1, 2.5, 0.5))

ax.set_xticklabels([])
ax.set_yticklabels([])
ax.set_zticklabels([])

# レイアウトを調整
plt.tight_layout()

# 保存（白い余白を最小化）
plt.savefig(os.path.join(output_path, file_name), dpi=800, format='png', bbox_inches='tight')
plt.show()
