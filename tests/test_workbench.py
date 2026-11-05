import math
from pathlib import Path
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pandas as pd
import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from erlead.data import map_import_columns, prepare, read_import_csv
from erlead.storage import digest, read_json
from erlead.workbench import CsvDropZone, CsvImportDialog


def test_mapped_csv_keeps_units_filters_and_original_source(tmp_path):
    source = tmp_path / "实验记录.csv"
    frame = pd.DataFrame({
        "分子结构": ["CCO", "c1ccccc1O", "CCN", "CO"],
        "测定值": [1, 20, 10, 30],
        "测定单位": ["uM", "nM", "nM", "nM"],
        "target_chembl_id": ["CHEMBL206", "CHEMBL206", "WRONG", "CHEMBL206"],
        "relation": ["=", "=", "=", "<"],
    })
    frame.to_csv(source, index=False, encoding="gb18030")
    before = digest(source)
    mapping = {"smiles": "分子结构", "ic50": "测定值", "unit": "测定单位"}
    runtime = tmp_path / "runtime"
    prepare(runtime, lambda _: None, source, "单元测试夹具，非客户科研数据", column_mapping=mapping)
    audit = read_json(runtime / "data/processed/audit.json")
    cleaned = pd.read_csv(runtime / "data/processed/cleaned.csv").set_index("canonical_smiles")
    assert audit["unique_compounds"] == 2 and audit["rejected_records"] == 2
    assert audit["reasons"]["wrong_target"] == 1 and audit["reasons"]["non_exact_relation"] == 1
    assert cleaned.loc["CCO", "pIC50"] == pytest.approx(6.0)
    assert cleaned.loc["Oc1ccccc1", "pIC50"] == pytest.approx(9 - math.log10(20))
    assert audit["source"]["column_mapping"] == mapping
    assert digest(source) == before
    assert digest(runtime / "data/raw" / audit["source"]["raw_snapshot"]) == before


def test_mapping_requires_explicit_units_and_distinct_columns():
    frame = pd.DataFrame({"structure": ["CCO"], "value": [1]})
    original = frame.copy()
    mapping = {"smiles": "structure", "ic50": "value", "unit": ""}
    with pytest.raises(ValueError, match="单位"):
        map_import_columns(frame, mapping)
    mapped = map_import_columns(frame, mapping, "µM")
    assert mapped.loc[0, "standard_units"] == "µM"
    with pytest.raises(ValueError, match="重复"):
        map_import_columns(frame, {"smiles": "value", "ic50": "value"}, "nM")
    pd.testing.assert_frame_equal(frame, original)


def test_csv_drop_accepts_only_one_local_csv(app, tmp_path):
    csv_path = tmp_path / "a.csv"
    csv_path.write_text("SMILES,IC50_nM\nCCO,100\n", encoding="utf-8")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(csv_path))])
    assert CsvDropZone.csv_path(mime) == csv_path
    mime.setUrls([QUrl("https://example.invalid/a.csv")])
    assert CsvDropZone.csv_path(mime) is None
    mime.setUrls([QUrl.fromLocalFile(str(csv_path)), QUrl.fromLocalFile(str(csv_path))])
    assert CsvDropZone.csv_path(mime) is None


def test_csv_dialog_requires_source_before_accepting(app, tmp_path, monkeypatch):
    source = tmp_path / "records.csv"
    source.write_text("SMILES,IC50_nM\nCCO,100\n", encoding="utf-8")
    dialog = CsvImportDialog(source)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    dialog.accept()
    assert "来源" in dialog.error_label.text() and dialog.result() != QDialog.DialogCode.Accepted
    dialog.source.setPlainText("单元测试夹具，非实验来源声明")
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.mapping["smiles"] == "SMILES" and dialog.mapping["ic50"] == "IC50_nM"
    assert dialog.default_unit == "nM"
    dialog.close()
