"""Small controlled fixtures test rules; training uses only fetched real assay data."""
import numpy as np
import pytest
from erlead.chemistry import featurize, standardize, structural_groups
from erlead.data import clean_records, ic50_to_pic50
from erlead.optimization import optimize, validate_weights
from erlead.screening import Rules, screen


@pytest.mark.parametrize("value,unit,expected", [(1000, "nM", 6), (1, "uM", 6), (1e-6, "M", 6), (1000, "pM", 9)])
def test_units(value, unit, expected):
    assert ic50_to_pic50(value, unit) == pytest.approx(expected)


@pytest.mark.parametrize("value,unit", [(0, "nM"), (-1, "nM"), (float("nan"), "nM"), (float("inf"), "nM"), (5, "mg/L")])
def test_bad_labels(value, unit):
    with pytest.raises(ValueError):
        ic50_to_pic50(value, unit)


def test_cleaning_censored_duplicate_and_conflict():
    records = [{"canonical_smiles": s, "standard_value": value, "standard_relation": relation, "activity_id": i}
               for i, (s, value, relation) in enumerate([("CCO", 1000, "="), ("OCC", 100, "="),
                   ("CCC", 20, ">"), ("CCN", 1, "="), ("NCC", 1000, "="), ("bad", 1, "=")])]
    result, audit, rejected = clean_records(records)
    assert len(result) == 1 and result.iloc[0].pIC50 == pytest.approx(6.5)
    assert audit["replicate_conflict_records"] == 2
    assert audit["rejected_records"] == 4
    assert len(rejected) == 4


def test_standardization_and_feature_consistency():
    assert standardize("CC[NH3+].[Cl-]")[1] == standardize("CCN")[1]
    np.testing.assert_array_equal(featurize(["OCC"]), featurize(["CCO"]))
    with pytest.raises(ValueError):
        featurize(["not a molecule"])


def test_close_analogues_grouped():
    groups, _ = structural_groups(["Cc1ccccc1", "Oc1ccccc1", "C1CCCCC1", "CCO", "CCC"])
    assert groups[0] == groups[1]
    assert groups[3] == groups[4]
    assert groups[0] != groups[2]


@pytest.mark.parametrize("method", ["GA", "SA", "TS"])
def test_optimizers_reproducible_and_better_than_equal(method):
    y = np.arange(10, dtype=float)
    predictions = np.column_stack([y, y + 2, y - 4, y * 0])
    a = optimize(predictions, y, method, seed=7, iterations=30)
    b = optimize(predictions, y, method, seed=7, iterations=30)
    validate_weights(a["weights"])
    assert a == b
    assert a["validation_mse"] <= np.mean((predictions.mean(axis=1) - y) ** 2)


@pytest.mark.parametrize("weights", [[0, 0, 0, 0], [-1, 1, 1, 0], [float("nan"), 0, 0, 1], [1, 0]])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        validate_weights(weights)


GOOD = {"logS": -2.0, "F_percent": 50.0, "PPB_percent": 90.0, "hepatotoxic": False, "CYP3A4_inhibitor": False}


def test_hard_threshold_cannot_be_rewarded_away():
    result = screen(5.99, Rules(reward=1), GOOD, [True] * 67, demo=True)
    assert "淘汰" in result["conclusion"]
    assert "演示" in result["conclusion"]
    assert result["stages"][2]["flow"] == "未放行"
    assert screen(6.0)["stages"][0]["status"] == "通过"
    with pytest.raises(ValueError):
        screen(5.8, Rules(activity_threshold=5.5))


def test_admet_fatal_risk_overrides_total():
    result = screen(8, Rules(reward=1), {**GOOD, "hepatotoxic": True}, [True] * 67, demo=True)
    assert "ADMET关键风险" in result["conclusion"]


def test_missing_and_demo_never_masquerade_as_real():
    assert screen(8)["adjusted_score"] is None
    assert not screen(8)["complete"]
    with pytest.raises(ValueError):
        screen(8, admet=GOOD, structure=[True] * 67)
    with pytest.raises(ValueError):
        screen(8, admet=GOOD, structure=[True] * 66, demo=True)
    with pytest.raises(ValueError):
        screen(8, admet={"logS": -2}, demo=True)
    result = screen(8, admet=GOOD, structure=[True] * 67, demo=True)
    assert result["base_score"] == pytest.approx(1)
    assert result["score_label"].startswith("演示")


def test_dynamic_rules_and_snapshot():
    structure = [True] * 50 + [False] * 17
    base = screen(7, admet=GOOD, structure=structure, demo=True)
    changed = screen(7, Rules(penalty=0.5), GOOD, structure, demo=True)
    assert changed["adjusted_score"] < base["adjusted_score"]
    assert changed["rules"]["penalty"] == 0.5
    assert "淘汰" in screen(7, Rules(activity_threshold=7.1))["conclusion"]


def test_empty_and_non_ic50_data_rejected():
    with pytest.raises(ValueError, match="没有有效化合物"):
        clean_records([])
    with pytest.raises(ValueError, match="没有有效化合物"):
        clean_records([{"canonical_smiles": "CCO", "standard_value": 1, "standard_type": "EC50"}])


def test_import_without_units_rejected(tmp_path):
    from erlead.data import prepare
    path = tmp_path / "ambiguous.csv"
    path.write_text("SMILES,IC50\nCCO,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="未声明IC50单位"):
        prepare(tmp_path, csv_path=path, source_note="Controlled test fixture")


def test_corrupt_raw_cache_blocks_training_input(tmp_path):
    from erlead.data import download
    from erlead.storage import write_json
    write_json(tmp_path / "data/raw/source.json", {"files": {"activities.json": "invalid"}})
    with pytest.raises(ValueError, match="校验失败"):
        download(tmp_path)
