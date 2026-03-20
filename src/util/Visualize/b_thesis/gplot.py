import numpy as np
import matplotlib.pyplot as plt

# 適当な曲線を作成（画像の形状に近づける）
x = np.linspace(-5, 5, 500)
y = np.sin(x) + 0.2 * x + 0.05 * x**2

# グラフをプロット（目盛りなし、軸を削除）
fig, ax = plt.subplots(figsize=(6, 3))

# 関数のプロット
ax.plot(x, y, color='blue', linewidth=3)

# 軸と目盛りを非表示
ax.axis('off')

# プロット全体をレイアウト調整して保存
plt.tight_layout()
plt.savefig("/mnt/nas0/g005/murasemaru/exp/other/kunekune.png")