import time
import pickle
import numpy as np
import pandas as pd


def train(model, rtr_list, output_dir_path, epochs, batch_size, rtr_date, i=1):
    df = pd.DataFrame(rtr_list).dropna()
    features = df.iloc[:, :-1]
    targets = df.iloc[:, -1]

    start_time = time.time()
    history = model.fit(features, targets, epochs=epochs, batch_size=batch_size)
    training_time = time.time() - start_time

    accuracy = history.history["accuracy"][-1]
    loss = history.history["loss"][-1]
    str_rtr_date = rtr_date.strftime("%Y-%m-%dT%H:%M:%S")

    with open(f"{output_dir_path}/m{i}_weights/{str_rtr_date}.pickle", 'wb') as f:
        pickle.dump(model.get_weights(), f)

    # データの統計情報
    benign_count = np.sum(targets == 0)
    malicious_count = np.sum(targets == 1)
    flow_num = len(targets)
    return model, [rtr_date, accuracy, loss, training_time, benign_count, malicious_count, flow_num]

