import json

import numpy as np

from cbsc_zdc.eval.metrics import distribution_metrics, wasserstein_1d


def test_empty_wasserstein_is_json_safe_none():
    assert wasserstein_1d(np.array([]), np.array([1.0])) is None


def test_distribution_metrics_are_strict_json_serializable_when_generated_is_empty():
    truth = np.array([[1.0, 0.0], [2.0, 0.0]], dtype=np.float32)
    generated = np.zeros_like(truth)
    layer_index = np.array([0, 1], dtype=np.int64)
    positions = np.zeros((2, 3), dtype=np.float32)
    report = distribution_metrics(truth, generated, layer_index, positions)
    json.dumps(report, allow_nan=False)
    assert report["positive_cell_energy_gev"]["wasserstein"] is None
