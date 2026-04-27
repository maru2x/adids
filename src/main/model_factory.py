import os
import pickle
import pandas as pd

import tensorflow as tf

class ModelFactory:

    def __init__(self, model_code, user_dir_path, foundation_model_path, input_dim):
        self.m_dict = {
            0: dnn, 1: rnn, 2: autoencoder, 3: svm,
            4: logistic_regression, 5: lstm,
            6: random_forest, 7: gradient_boosting
        }
        self.user_dir_path = user_dir_path
        self.foundation_model_path = foundation_model_path
        self.full_path = os.path.join(self.user_dir_path, self.foundation_model_path)
        self.input_dim = input_dim
        self.model_code = model_code
        self.foundation_model = self._create_model(model_code)


    def _create_model(self, model_code):
        creator = self.m_dict[model_code]
        if creator is None:
            raise ValueError(f"Invalid model_code: {model_code}")

        model = creator(tf, self.input_dim)
        if self._has_saved_weights():
            with open(self.full_path, 'rb') as f:
                model.set_weights(pickle.load(f))
        return model

    def create_model(self):
        return self._create_model(self.model_code)

    def _has_saved_weights(self):
        return bool(self.foundation_model_path) and os.path.exists(self.full_path)

def dnn(tf, input_dim):
    # Deep Neural Network
    tf.keras.utils.set_random_seed(1)
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,), dtype=tf.float32),
        tf.keras.layers.Dense(100, activation='relu'),
        tf.keras.layers.Dense(50, activation='relu'),
        tf.keras.layers.Dense(25, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy"]
    )
    return model

def rnn(tf, input_dim):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim, 1)),  # 時系列データの入力
        tf.keras.layers.SimpleRNN(50, activation='relu', return_sequences=True),
        tf.keras.layers.SimpleRNN(25, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')  # 出力層
    ])
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    return model

def autoencoder(tf, input_dim):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),  # 入力層
        tf.keras.layers.Dense(64, activation='relu'),  # エンコーダ層1
        tf.keras.layers.Dense(32, activation='relu'),  # エンコーダ層2 (ボトルネック)
        tf.keras.layers.Dense(64, activation='relu'),  # デコーダ層1
        tf.keras.layers.Dense(input_dim, activation='sigmoid')  # デコーダ層2 (再構築層)
    ])
    model.compile(
        optimizer='adam',
        loss='mse',  # 再構築誤差を損失関数に
        metrics=['mae']  # 平均絶対誤差を評価指標に
    )
    return model

def svm(tf, input_dim):
    def hinge_loss(y_true, y_pred):
        return tf.reduce_mean(tf.maximum(0., 1. - y_true * y_pred))

    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(1, activation='linear')  # 線形活性化
    ])
    model.compile(
        optimizer='adam',
        loss=hinge_loss,
        metrics=['accuracy']
    )
    return model

def logistic_regression(tf, input_dim):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.Dense(1, activation='sigmoid')  # 出力層はSigmoid活性化
    ])
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    return model

def lstm(tf, input_dim):
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(input_dim,)),
        tf.keras.layers.LSTM(50, return_sequences=True),
        tf.keras.layers.LSTM(25),
        tf.keras.layers.Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model

def random_forest(tf, input_dim=None):
    raise ValueError("random_forest requires tensorflow_decision_forests, which is not installed.")

def gradient_boosting(tf, input_dim=None):
    raise ValueError("gradient_boosting requires tensorflow_decision_forests, which is not installed.")
