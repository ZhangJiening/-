from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from rdkit import DataStructs
from erlead.chemistry import SIMILARITY_GENERATOR, standardize
from erlead.storage import model_location, read_json
from erlead.training import metrics

ROOT = Path(__file__).resolve().parents[1]


def test_real_split_and_saved_test_report():
    if not (ROOT / "models" / "current.json").exists():
        pytest.skip("真实数据集成证据需要先prepare/train")
    folder = model_location(ROOT)
    report = read_json(folder / "report.json")
    assert report["independent_test_evaluations"] == 1
    reports = ROOT / "reports" / report["run_id"]
    frame = pd.read_csv(reports / "split.csv")
    parts = {k: frame[frame.split == k] for k in ("train", "validation", "test")}
    fingerprints = {key: [SIMILARITY_GENERATOR.GetFingerprint(standardize(s)[0]) for s in part.canonical_smiles]
                    for key, part in parts.items()}
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert not set(parts[a].structure_group) & set(parts[b].structure_group)
        assert not set(parts[a].canonical_smiles) & set(parts[b].canonical_smiles)
        maximum = max(max(DataStructs.BulkTanimotoSimilarity(fp, fingerprints[b])) for fp in fingerprints[a])
        assert maximum < .85
    cached = pd.read_csv(reports / "test_predictions.csv")
    # Verify arithmetic from the sealed prediction file; never refit on held-out labels.
    recomputed = metrics(cached.truth.to_numpy(), cached.ensemble.to_numpy())
    for k in ("R2", "RMSE", "MAE"):
        assert recomputed[k] == pytest.approx(report["test_metrics"]["ensemble"][k])
