import numpy as np
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, f1_score


def evaluate(y_true, y_pred, tf):
    # TensorFlowのテンソルに変換
    y_true = tf.convert_to_tensor(y_true, dtype=tf.float32)
    y_pred = tf.convert_to_tensor(y_pred, dtype=tf.float32)

    # 二値化
    y_pred_bin = tf.cast(y_pred >= 0.5, tf.float32)

    # 混同行列の計算
    tp = tf.reduce_sum(tf.cast((y_true == 1) & (y_pred_bin == 1), tf.float32))
    tn = tf.reduce_sum(tf.cast((y_true == 0) & (y_pred_bin == 0), tf.float32))
    fp = tf.reduce_sum(tf.cast((y_true == 0) & (y_pred_bin == 1), tf.float32))
    fn = tf.reduce_sum(tf.cast((y_true == 1) & (y_pred_bin == 0), tf.float32))

    print(f"TN: {tn}, FP: {fp}, FN: {fn}, TP: {tp}")
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0  # 真陽性率
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0  # 偽陽性率
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0  # 偽陰性率
    tnr = tn / (tn + fp) if (tn + fp) > 0 else 0  # 真陰性率

    accuracy = accuracy_score(y_true, y_pred_bin)
    precision = precision_score(y_true, y_pred_bin)
    f1 = f1_score(y_true, y_pred_bin)

    bce = tf.keras.losses.BinaryCrossentropy(from_logits=False)
    eval_loss = bce(np.array(y_true), np.array(y_pred)).numpy()

    flow_num = tn + fp + fn + tp
    benign_count = tn + fp
    benign_rate = benign_count / flow_num if flow_num > 0 else 0

    return [
        float(tp), float(fn), float(fp), float(tn), float(flow_num),
        float(tpr), float(fnr), float(fpr), float(tnr),
        float(accuracy), float(precision), float(f1), float(eval_loss), float(benign_rate)
    ]