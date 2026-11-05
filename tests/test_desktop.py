import json
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMessageBox
from erlead import APP_NAME
from erlead.storage import model_location, read_json
from erlead.ui import MainWindow
from erlead.desktopcheck import settle

ROOT = Path(__file__).resolve().parents[1]
ESTRADIOL = "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O"


@pytest.fixture
def window(app, tmp_path):
    w = MainWindow(tmp_path)
    if (ROOT / "models" / "current.json").exists():
        w.set_bundle(model_location(ROOT))
    yield w
    w.close()
    w.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_desktop_name_and_fixed_target(window):
    assert window.windowTitle() == APP_NAME
    assert any("ERα / ESR1 固定靶点" in w.text() for w in window.findChildren(QLabel))
    assert window.pages.count() == 6
    assert window.report_tabs.count() == 2
    assert window.sample_table.isHidden() and window.audit_details.isHidden()
    assert window.prediction_content.isHidden() and window.pred_report_body.isHidden()
    assert window.progress.isHidden()
    assert window.parameters["activity_threshold"].minimum() == 6
    assert not window.windowIcon().isNull()
    assert (ROOT / "assets" / "logo.png").exists()
    assert any(child.objectName() == "logo" for child in window.findChildren(QLabel))


def test_real_prediction_dynamic_rules_and_export(window, app, tmp_path, monkeypatch):
    if window.bundle is None:
        pytest.skip("运行真实prepare/train后执行桌面模型集成测试")
    window.navigate("分子预测")
    window.resize(1320, 1200)
    window.show()
    window.smiles.setText(ESTRADIOL)
    window.predict_button.click()
    settle(window, app)
    app.processEvents()
    assert window.last_result is not None
    assert not window.prediction_content.isHidden()
    assert not window.pred_report_body.isHidden()
    assert window.prediction_table.rowCount() == 4
    assert not window.molecule_image.pixmap().isNull()
    assert window.last_result["screening"]["adjusted_score"] is None
    assert window.funnel_table.rowCount() == 3
    window.navigate("结果与导出")
    assert window.report_stage_table.rowCount() == 3
    assert window.report_prediction_table.rowCount() == 4
    assert f"{window.last_result['ensemble_pIC50']:.3f}" in window.screening_summary.text()
    for kind in ("html", "json", "csv"):
        output = tmp_path / ("prediction." + kind)
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, p=output: (str(p), ""))
        window.export_prediction(kind)
        assert output.exists() and output.stat().st_size > 100
    exported = read_json(tmp_path / "prediction.json")
    assert exported["model_version"] == window.bundle[1]["run_id"]
    assert not exported["screening"]["demo"]
    window.use_demo.setChecked(True)
    assert window.last_result is None
    assert not window.export_csv_button.isEnabled()
    window.run_prediction()
    settle(window, app)
    assert window.last_result["screening"]["demo"]
    assert "演示" in window.conclusion.text()
    window.parameters["s1"].setValue(.5)
    assert window.last_result is None and not window.export_json_button.isEnabled()
    window.restore_defaults()
    assert window.last_result is None
    window.run_prediction()
    settle(window, app)
    assert window.last_result is not None
    assert window.activity_label.text() != "—"
    assert not window.molecule_image.pixmap().isNull()
    window.demo_fields["hepatotoxic"].setChecked(True)
    assert window.last_result is None
    assert not window.export_csv_button.isEnabled()
    window.run_prediction()
    settle(window, app)
    assert "ADMET关键风险" in window.conclusion.text()
    window.demo_fields["hepatotoxic"].setChecked(False)
    window.clear_stages()
    window.run_prediction()
    settle(window, app)
    assert window.last_result["screening"]["adjusted_score"] is None
    window.save_rules()
    assert (tmp_path / "config" / "rules.json").exists()
    window.external_stages = {"evidence": "test stale input"}
    window.smiles.setText("CCO")
    assert window.external_stages is None and window.last_result is None
    assert window.report_stage_table.rowCount() == 0
    assert window.prediction_report_raw.toPlainText() == ""
    assert window.prediction_content.isHidden() and window.pred_report_body.isHidden()
    assert not any(b.isEnabled() for b in window.pred_export_buttons)
    window.smiles.setText("INVALID SMILES")
    window.predict_button.click()
    settle(window, app)
    assert "预测失败" in window.conclusion.text()
    assert "Traceback" not in window.statusBar().currentMessage()
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
    html = (folder / "训练报告.html").read_text(encoding="utf-8")
    assert "模型训练报告" in html and window.bundle[1]["run_id"] in html
    assert (folder / "模型指标.csv").exists()


def test_background_failure_restores_controls_and_logs(window, app, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    def failed_operation(log):
        raise ValueError("controlled failure for recovery test")
    window.start_job(failed_operation, lambda _: pytest.fail("失败任务不应触发成功回调"))
    assert not window.train_button.isEnabled()
    assert not window.load_model_button.isEnabled()
    assert not window.progress.isHidden()
    assert window.worker.wait(3000)
    app.processEvents()
    assert not window.train_button.isEnabled()
    assert window.load_model_button.isEnabled()
    assert window.progress.isHidden()
    assert "controlled failure" in window.data_notice.text()
    assert "controlled failure" in read_json(tmp_path / "reports/last-error.json")["error"]


def test_file_errors_keep_the_previous_model_and_prediction(window, app, tmp_path, monkeypatch):
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
    settle(window, app)
    previous = window.last_result
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(tmp_path / "missing-folder/prediction.csv"), ""))
    window.export_prediction("csv")
    assert len(messages) == 1
    assert "导出失败" in window.export_feedback["prediction"].text()
    assert window.last_result == previous and window.export_csv_button.isEnabled()


@pytest.mark.parametrize("size", [(1050, 720), (1360, 920)])
def test_report_reflow_has_no_overlapping_painted_controls(window, app, size):
    from PySide6.QtCore import QObject, QEvent
    if window.bundle is None:
        pytest.skip("需要已训练模型")
    collisions = []
    class Observer(QObject):
        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Paint and watched.isVisible():
                collisions.append(window.report_prediction_table.geometry().intersects(watched.geometry()))
            return False
    observer = Observer()
    window.export_format_title.installEventFilter(observer)
    window.resize(*size)
    window.show()
    for page, tab, caption in [(1, 0, "分子预测"), (2, 0, "结果与导出"), (0, 1, "模型训练"), (1, 0, "分子预测")]:
        window.navigate(caption)
        app.processEvents()
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    settle(window, app)
    app.processEvents()
    window.navigate("结果与导出")
    for expanded in (False, True, False):
        window.prediction_raw_details.set_expanded(expanded)
        window.pages.widget(5).ensureWidgetVisible(window.export_format_title)
        for _ in range(3):
            app.processEvents()
        assert window.report_prediction_table.geometry().bottom() < window.export_format_title.y()
        assert window.pages.widget(5).horizontalScrollBar().maximum() == 0
    assert collisions and not any(collisions)


def test_six_navigation_entries_have_distinct_pages_and_matching_titles(window, app):
    window.show()
    seen = []
    for index, b in enumerate(window.nav_buttons):
        b.click()
        app.processEvents()
        page = window.pages.currentWidget()
        seen.append(page)
        assert window.pages.currentIndex() == index
        assert any(x.objectName() == "title" and x.text() == b.text() for x in page.findChildren(QLabel))
        assert sum(x.isChecked() for x in window.nav_buttons) == 1
    assert len(set(seen)) == 6


def test_prediction_survives_navigation_and_funnel_rules_update_report(window, app):
    if window.bundle is None:
        pytest.skip("需要已训练模型")
    window.show()
    window.navigate("分子预测")
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    settle(window, app)
    original = window.last_result["ensemble_pIC50"]
    for name in window.page_names:
        window.navigate(name)
        app.processEvents()
        assert window.last_result["ensemble_pIC50"] == original
    window.navigate("三级漏斗筛选")
    window.parameters["activity_threshold"].setValue(min(12, original + 1))
    assert window.last_result is None
    assert "已失效" in window.funnel_context.text()
    assert not window.export_csv_button.isEnabled()
    window.run_prediction()
    settle(window, app)
    assert "淘汰" in window.funnel_context.text()
    assert "淘汰" in window.conclusion.text()
    assert "淘汰" in window.screening_summary.text()
    window.navigate("分子预测")
    window.smiles.setText("CCO")
    assert window.last_result is None
    assert "未开始" in window.screen_stage_views[0][0].text()
    assert all("未评估" in status.text() for status, _, _ in window.screen_stage_views[1:])
    assert window.pred_report_body.isHidden()


def test_selective_exports_and_history_survive_restart(window, app, tmp_path, monkeypatch):
    if window.bundle is None:
        pytest.skip("需要已训练模型")
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    settle(window, app)
    for key, selected in (("prediction", "molecule"), ("training", "weights")):
        for section, checkbox in window.export_sections[key].items():
            checkbox.setChecked(section == selected)
        for kind in ("html", "csv", "json"):
            destination = tmp_path / (key + "." + kind)
            monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args, p=destination: (str(p), ""))
            window.export_formats[key][kind].setChecked(True)
            window.export_selected(key)
            assert destination.is_file() and destination.stat().st_size > 50
    molecular = read_json(tmp_path / "prediction.json")
    assert "predictions" not in molecular and "stages" not in molecular["screening"]
    training = read_json(tmp_path / "training.json")
    assert "weights" in training and "test_metrics" not in training and "model_parameters" not in training
    assert len(window.export_history) == 6
    assert window.export_history_table.rowCount() == 6
    restarted = MainWindow(tmp_path)
    assert len(restarted.export_history) == 6
    assert restarted.export_history[0]["path"] == str((tmp_path / "training.json").resolve())
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[-1]))
    restarted.open_export(tmp_path / "moved-report.html")
    assert messages and "不存在" in messages[0]
    restarted.close()


def test_preconditions_history_and_next_seed_are_separate(window, app):
    assert not window.train_button.isEnabled() and not window.next_training_button.isEnabled()
    assert "请先" in window.train_button.toolTip()
    assert not window.predict_button.isEnabled() and not window.view_report_button.isEnabled()
    assert window.bundle is not None
    before = [[window.model_table.item(r, c).text() for c in range(4)] for r in range(4)]
    window.training_seed.setValue(123)
    assert "123" in window.training_settings_note.text()
    assert [[window.model_table.item(r, c).text() for c in range(4)] for r in range(4)] == before
    assert "历史" in window.training_count.text()
    assert "尚未导入" in window.pending_count.text()
    assert "分子图" not in window.export_notes["training"].text()
    window.export_sections["training"]["models"].setChecked(False)
    window.export_formats["training"]["csv"].setChecked(True)
    assert "一行" in window.export_notes["training"].text()


def test_prediction_worker_blocks_duplicate_submission_and_keeps_current_run(window, app, monkeypatch):
    import threading
    from erlead import ui as ui_module
    real_predict = ui_module.predict
    entered, release = threading.Event(), threading.Event()
    calls = []
    def delayed_predict(smiles, bundle):
        calls.append(smiles)
        entered.set()
        if not release.wait(5):
            raise RuntimeError("test release timed out")
        return real_predict(smiles, bundle)
    monkeypatch.setattr(ui_module, "predict", delayed_predict)
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    try:
        assert entered.wait(3)
        assert window.busy and window.predicting
        assert not window.predict_button.isEnabled()
        assert not window.load_model_button.isEnabled()
        assert "正在预测" in window.predict_button.text()
        window.run_prediction()
        assert len(calls) == 1
    finally:
        release.set()
        settle(window, app)
    assert window.last_result is not None
    assert window.view_report_button.isEnabled()
    assert window.last_result["input_smiles"] == ESTRADIOL
    window.smiles.setText("CCO")
    assert "已失效" in window.conclusion.text()
    assert window.last_result is None and not window.report_export_button.isEnabled()


def test_template_and_real_csv_preparation_report_progress(window, app, tmp_path, monkeypatch):
    import csv
    from erlead.data import prepare
    template = tmp_path / "template.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(template), ""))
    window.download_csv_template()
    with template.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.reader(stream)) == [["SMILES", "IC50", "units", "relation"]]
    source = tmp_path / "fixture.csv"
    source.write_text("SMILES,IC50,units,relation\nCCO,100,nM,=\nc1ccccc1O,20,nM,=\nCCN,-1,nM,=\n", encoding="utf-8")
    window.begin_data_task(lambda log: prepare(window.root, log, source, "测试夹具，非客户科研数据"), "导入测试夹具")
    settle(window, app)
    assert window.sample_table.rowCount() == 2
    assert "有效 2" in window.data_label.text()
    assert "排除记录 1" in window.data_audit_summary.text()
    assert all("完成" in step.text() for step in window.cleaning_steps)
    assert "fixture.csv" in window.import_context.toPlainText()
    assert not window.train_button.isEnabled()  # two compounds cannot satisfy the actual trainer's precondition
    assert window.bundle is not None


def test_failed_data_job_can_retry_without_replacing_loaded_model(window, app):
    version = window.bundle[1]["run_id"]
    attempts = []
    def fail(log):
        attempts.append("failed")
        raise ConnectionError("controlled network failure")
    def retry():
        window.begin_data_task(lambda log: attempts.append("retried"), "重试测试")
    window.retry_data = retry
    window.begin_data_task(fail, "网络失败测试")
    settle(window, app)
    assert "失败" in window.data_notice.text() and not window.retry_data_button.isHidden()
    assert not window.train_button.isEnabled() and "未就绪" in window.pending_count.text()
    assert all("未开始" in step.text() for step in window.cleaning_steps)
    window.retry_last_data()
    settle(window, app)
    assert attempts == ["failed", "retried"]
    assert window.bundle[1]["run_id"] == version


def test_external_evidence_validation_and_report_are_for_current_molecule(window, app, tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    settle(window, app)
    source = tmp_path / "stage-fixture.json"
    source.write_text(json.dumps({"canonical_smiles": "CCO", "evidence": "UI test fixture"}), encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    window.load_stage_evidence()
    assert messages and window.external_stages is None
    evidence = {
        "canonical_smiles": window.last_result["canonical_smiles"],
        "evidence": "自动化验收夹具，非实验测量",
        "admet": dict(logS=-2, F_percent=50, PPB_percent=90, hepatotoxic=False, CYP3A4_inhibitor=False),
        "structure": [True] * 67,
        "constraint_definitions": [f"test_constraint_{i}" for i in range(67)],
    }
    source.write_text(json.dumps(evidence), encoding="utf-8")
    window.load_stage_evidence()
    assert window.last_result is None and not window.export_csv_button.isEnabled()
    window.run_prediction()
    settle(window, app)
    assert window.last_result["screening"]["adjusted_score"] is not None
    assert "自动化验收夹具" in window.last_result["stage_evidence"]["evidence"]
    window.clear_stages()
    window.run_prediction()
    settle(window, app)
    assert window.last_result["screening"]["adjusted_score"] is None
    assert all("未评估" in window.report_stage_table.item(row, 1).text() for row in (1, 2))


def test_run_copy_and_history_folder_use_current_version(window, app, tmp_path, monkeypatch):
    from PySide6.QtGui import QDesktopServices
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True)
    report = window.bundle[1]
    window.copy_run_info("run_id")
    assert app.clipboard().text() == report["run_id"]
    window.copy_run_info("data_sha256")
    assert app.clipboard().text() == report["data_sha256"]
    target = tmp_path / "moved-file.html"
    window.open_export_folder(target)
    assert Path(opened[-1]) == tmp_path
    assert "MSE" in window.fusion_table.item(0, 5).toolTip()
    assert "遗传算法" in window.fusion_table.item(0, 0).toolTip()


@pytest.mark.parametrize("size", [(880, 460), (1366, 768), (1480, 940), (1920, 1080)])
def test_every_page_top_bottom_and_footer_are_visible(window, app, size):
    from PySide6.QtCore import QPoint
    window.resize(*size)
    window.show()
    for name in window.page_names:
        window.navigate(name)
        for _ in range(3):
            app.processEvents()
        page = window.pages.currentWidget()
        title = next(widget for widget in page.findChildren(QLabel) if widget.objectName() == "title")
        assert title.mapTo(page.viewport(), QPoint()).y() >= 0, (name, size)
        assert page.horizontalScrollBar().maximum() == 0, (name, size)
        if page.footer is not None:
            assert page.footer.y() >= page.viewport().geometry().bottom(), (name, size)
            assert page.footer.geometry().bottom() <= page.height(), (name, size)
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        for _ in range(3):
            app.processEvents()
        visible_labels = [widget for widget in page.widget().findChildren(QLabel) if widget.isVisible()]
        if visible_labels:
            lowest = max(widget.mapTo(page.viewport(), QPoint(0, widget.height())).y() for widget in visible_labels)
            assert lowest <= page.viewport().height() + 3, (name, size, lowest, page.viewport().height())
    window.smiles.setText(ESTRADIOL)
    window.run_prediction()
    settle(window, app)
    for name in ("分子预测", "三级漏斗筛选", "结果与导出"):
        window.navigate(name)
        for _ in range(3):
            app.processEvents()
        assert window.pages.currentWidget().horizontalScrollBar().maximum() == 0, (name, size, "after_prediction")


def test_demo_edits_invalidate_and_history_buttons_fit(window, app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QPushButton
    window.resize(1366, 768)
    window.show()
    window.smiles.setText(ESTRADIOL)
    window.use_demo.setChecked(True)
    window.run_prediction()
    settle(window, app)
    edits = (
        lambda: window.demo_count.setValue(55),
        lambda: window.demo_fields["hepatotoxic"].setChecked(True),
        lambda: window.demo_fields["CYP3A4_inhibitor"].setChecked(True),
        lambda: window.demo_fields["logS"].setValue(-1.5),
        lambda: window.demo_fields["F_percent"].setValue(45),
        lambda: window.demo_fields["PPB_percent"].setValue(85),
        lambda: window.use_demo.setChecked(False),
    )
    for change in edits:
        change()
        assert window.last_result is None and "已失效" in window.conclusion.text()
        assert not any(button.isEnabled() for button in window.pred_export_buttons)
        window.run_prediction()
        settle(window, app)
        assert window.last_result is not None and window.export_csv_button.isEnabled()
    destination = tmp_path / "history.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), ""))
    window.export_prediction("csv")
    window.navigate("结果与导出")
    for _ in range(3):
        app.processEvents()
    cell = window.export_history_table.cellWidget(0, 4)
    for _ in range(3):
        window.export_history_table.fit_content()
        app.processEvents()
        for button in cell.findChildren(QPushButton):
            assert button.geometry().top() >= 0
            assert button.geometry().bottom() < cell.height()
            assert button.height() >= button.minimumSizeHint().height()