import json
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMessageBox
from erlead import APP_NAME
from erlead.storage import model_location, read_json
from erlead.ui import MainWindow

ROOT = Path(__file__).resolve().parents[1]
ESTRADIOL = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    w = MainWindow(tmp_path)
    if (ROOT / "models" / "current.json").exists():
        w.set_bundle(model_location(ROOT))
    yield w
    w.close()


def test_desktop_name_and_fixed_target(window):
    assert window.windowTitle() == APP_NAME
    assert any("ERα / ESR1 固定靶点" in w.text() for w in window.findChildren(QLabel))
    assert window.pages.count() == 2
    assert window.tabs.count() == 3
    assert window.parameters["activity_threshold"].minimum() == 6
    assert not window.windowIcon().isNull()
    assert (ROOT / "assets" / "logo.png").exists()
    assert any(child.objectName() == "logo" for child in window.findChildren(QLabel))


def test_real_prediction_dynamic_rules_and_export(window, app, tmp_path, monkeypatch):
    if window.bundle is None:
        pytest.skip("运行真实prepare/train后执行桌面模型集成测试")
    window.pages.setCurrentIndex(1)
    window.resize(1320, 1200)
    window.show()
    window.smiles.setText(ESTRADIOL)
    window.predict_button.click()
    app.processEvents()
    assert window.last_result is not None
    assert window.prediction_table.rowCount() == 4
    assert not window.molecule_image.pixmap().isNull()
    assert window.last_result["screening"]["adjusted_score"] is None
    assert window.funnel_table.rowCount() == 3
    for kind in ("json", "csv"):
        output = tmp_path / ("prediction." + kind)
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, p=output: (str(p), ""))
        window.export_prediction(kind)
        assert output.exists() and output.stat().st_size > 100
    exported = read_json(tmp_path / "prediction.json")
    assert exported["model_version"] == window.bundle[1]["run_id"]
    assert not exported["screening"]["demo"]
    window.use_demo.setChecked(True)
    assert window.last_result["screening"]["demo"]
    assert "演示" in window.conclusion.text()
    window.parameters["s1"].setValue(.5)
    assert window.last_result is None and not window.export_json_button.isEnabled()
    window.restore_defaults()
    assert window.last_result is not None
    window.demo_fields["hepatotoxic"].setChecked(True)
    assert "ADMET关键风险" in window.conclusion.text()
    window.demo_fields["hepatotoxic"].setChecked(False)
    window.clear_stages()
    assert window.last_result["screening"]["adjusted_score"] is None
    window.save_rules()
    assert (tmp_path / "config" / "rules.json").exists()
    window.external_stages = {"evidence": "test stale input"}
    window.smiles.setText("CCO")
    assert window.external_stages is None and window.last_result is None
    window.smiles.setText("INVALID SMILES")
    window.predict_button.click()
    assert "预测失败" in window.conclusion.text()
    assert window.last_result is None and not window.export_csv_button.isEnabled()


def test_export_training_uses_model_bound_audit(window, tmp_path, monkeypatch):
    if window.bundle is None:
        pytest.skip("需要已训练模型")
    destination = tmp_path / "export"
    destination.mkdir()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(destination))
    window.export_training()
    folder = next(destination.iterdir())
    assert read_json(folder / "data-audit.json")["cleaned_sha256"] == window.bundle[1]["data_sha256"]
    assert len(list((folder / "models").glob("*.joblib"))) == 4


def test_background_failure_restores_controls_and_logs(window, app, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    def failed_operation(log):
        raise ValueError("controlled failure for recovery test")
    window.start_job(failed_operation, lambda _: pytest.fail("失败任务不应触发成功回调"))
    assert not window.train_button.isEnabled()
    assert window.worker.wait(3000)
    app.processEvents()
    assert window.train_button.isEnabled()
    assert messages and "controlled failure" in messages[0]
    assert "controlled failure" in read_json(tmp_path / "reports/last-error.json")["error"]


def test_file_errors_keep_the_previous_model_and_prediction(window, tmp_path, monkeypatch):
    if window.bundle is None:
        pytest.skip("需要已训练模型")
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    original_version = window.bundle[1]["run_id"]
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(tmp_path / "missing-model"))
    window.choose_model()
    assert messages and window.bundle[1]["run_id"] == original_version
    window.smiles.setText(ESTRADIOL)
    window.predict_button.click()
    previous = window.last_result
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(tmp_path / "missing-folder/prediction.csv"), ""))
    window.export_prediction("csv")
    assert len(messages) == 2
    assert window.last_result == previous and window.export_csv_button.isEnabled()
