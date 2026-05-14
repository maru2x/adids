from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np


def ensure_demo_model(model_path: Path, *, model_code: int, input_dim: int) -> Path:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.exists():
        return model_path

    x_train, y_train = _build_demo_training_matrix()
    model = _create_demo_model(model_code, input_dim)
    model.fit(x_train, y_train, epochs=_resolve_epoch_count(model_code), batch_size=4, verbose=0)
    _apply_demo_fallback_if_needed(model, model_code, input_dim, x_train, y_train)
    _assert_demo_predictions(model, x_train, y_train)

    with model_path.open("wb") as fh:
        pickle.dump(model.get_weights(), fh)
    return model_path


def _create_demo_model(model_code: int, input_dim: int):
    import tensorflow as tf
    try:
        from Simulation.model_factory import dnn, logistic_regression
    except ModuleNotFoundError:
        from src.main.Simulation.model_factory import dnn, logistic_regression

    if model_code == 4:
        return logistic_regression(tf, input_dim)
    if model_code == 0:
        return dnn(tf, input_dim)
    raise ValueError("Live demo model auto-generation supports MODEL_CODE 0 and 4 only.")


def _resolve_epoch_count(model_code: int) -> int:
    return 80 if model_code == 0 else 200


def _build_demo_training_matrix() -> tuple[np.ndarray, np.ndarray]:
    malicious_rows = np.array(
        [
            [0.00, 0, 0, 0, 0, 0, 0, 0, 1, 1],
            [0.02, 0, 0, 1, 0, 40, 0, 0, 1, 1],
            [0.05, 8, 0, 1, 0, 68, 0, 0, 1, 1],
            [0.08, 16, 0, 1, 0, 84, 0, 0, 1, 1],
            [0.12, 24, 8, 2, 1, 108, 76, 0, 1, 1],
            [0.20, 32, 12, 2, 1, 116, 80, 0, 1, 1],
        ],
        dtype=np.float32,
    )
    benign_rows = np.array(
        [
            [0.30, 90, 120, 4, 3, 190, 220, 0, 1, 0],
            [0.80, 180, 320, 6, 5, 310, 450, 0, 1, 0],
            [1.50, 320, 700, 8, 7, 500, 900, 0, 1, 0],
            [2.50, 640, 1400, 12, 10, 860, 1660, 0, 1, 0],
            [4.00, 900, 2400, 14, 12, 1180, 2700, 0, 1, 0],
            [7.00, 1800, 4800, 20, 18, 2200, 5200, 0, 1, 0],
        ],
        dtype=np.float32,
    )
    x_train = np.vstack([malicious_rows, benign_rows])
    y_train = np.array([1] * len(malicious_rows) + [0] * len(benign_rows), dtype=np.float32)
    return x_train, y_train


def _assert_demo_predictions(model, x_train: np.ndarray, y_train: np.ndarray) -> None:
    predictions = model.predict(x_train, verbose=0).reshape(-1)
    malicious_scores = predictions[y_train == 1]
    benign_scores = predictions[y_train == 0]
    if malicious_scores.min() < 0.55 or benign_scores.max() > 0.45:
        raise ValueError(
            "Auto-generated live demo model did not separate demo classes cleanly enough. "
            f"malicious_min={malicious_scores.min():.4f}, benign_max={benign_scores.max():.4f}"
        )


def _apply_demo_fallback_if_needed(
    model,
    model_code: int,
    input_dim: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
) -> None:
    predictions = model.predict(x_train, verbose=0).reshape(-1)
    malicious_scores = predictions[y_train == 1]
    benign_scores = predictions[y_train == 0]
    if malicious_scores.min() >= 0.55 and benign_scores.max() <= 0.45:
        return
    if model_code != 4:
        return

    kernel = np.array(
        [
            [-2.0],
            [-0.015],
            [-0.008],
            [-1.0],
            [-1.0],
            [-0.005],
            [-0.003],
            [-0.5],
            [0.3],
            [0.3],
        ],
        dtype=np.float32,
    )
    if kernel.shape[0] != input_dim:
        raise ValueError(
            "Live demo fallback weights do not match the configured input dimension: "
            f"{kernel.shape[0]} != {input_dim}"
        )
    bias = np.array([4.5], dtype=np.float32)
    model.set_weights([kernel, bias])
