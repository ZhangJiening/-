"""Executable business smoke check of the native Qt window, also usable when frozen."""
import sys
from PySide6.QtCore import QTimer, QEventLoop, QPoint
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel
from . import __version__
from .storage import utc_now, write_json
from .ui import MainWindow


def settle(window, app, timeout=30000):
    """Wait for queued GUI completion without blocking the worker or GUI events."""
    app.processEvents()
    if not window.busy:
        if window.worker and window.worker.isRunning():
            window.worker.wait(timeout)
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    worker = window.worker
    worker.finished.connect(loop.quit)
    timer.start(timeout)
    # A fast worker can finish before this observer is connected. Process its
    # already-queued completion before deciding whether to enter the loop.
    app.processEvents()
    if window.busy:
        loop.exec()
    timer.stop()
    worker.finished.disconnect(loop.quit)
    app.processEvents()
    if window.busy:
        raise TimeoutError("界面后台任务未在限定时间内完成")
    if worker.isRunning() and not worker.wait(timeout):
        raise TimeoutError("后台线程清理未完成")


def verify_layout(window, app, size):
    window.resize(*size)
    cases = []
    for name in window.page_names:
        window.navigate(name)
        for _ in range(3):
            app.processEvents()
        page = window.pages.currentWidget()
        title = next(widget for widget in page.findChildren(QLabel) if widget.objectName() == "title")
        top = title.mapTo(page.viewport(), QPoint()).y()
        assert top >= 0, (name, size, "title", top)
        assert page.horizontalScrollBar().maximum() == 0, (name, size, "horizontal_overflow")
        if page.footer is not None:
            assert page.footer.y() >= page.viewport().geometry().bottom(), (name, size, "footer_overlap")
        page.verticalScrollBar().setValue(page.verticalScrollBar().maximum())
        for _ in range(3):
            app.processEvents()
        labels = [widget for widget in page.widget().findChildren(QLabel) if widget.isVisible()]
        lowest = max((widget.mapTo(page.viewport(), QPoint(0, widget.height())).y() for widget in labels), default=0)
        assert lowest <= page.viewport().height() + 3, (name, size, "last_line", lowest, page.viewport().height())
        cases.append({"page": name, "title_top": top, "bottom_visible": True})
    return {"requested_size": size, "actual_size": [window.width(), window.height()], "pages": cases}


def run_check(root):
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(root)
    capture_size = (1480, 940) if app.platformName() == "offscreen" else (
        min(1480, app.primaryScreen().availableGeometry().width() - 16),
        min(940, app.primaryScreen().availableGeometry().height() - 40))
    window.resize(*capture_size)
    window.show()
    output = root / "reports" / ("desktop-check-" + __version__ + "-" + utc_now().replace(":", "-"))
    output.mkdir(parents=True, exist_ok=True)
    result = {}

    def check():
        try:
            window.restore_defaults()
            window.clear_stages()
            window.navigate("数据导入与清洗")
            for _ in range(3):
                app.processEvents()
            assert window.progress.isHidden()
            if window.sample_table.rowCount() == 0:
                assert window.sample_table.isHidden()
                assert not window.data_empty_hint.isHidden()
            window.grab().save(str(output / "data.png"))
            window.navigate("三级漏斗筛选")
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "funnel-empty.png"))
            window.navigate("分子预测")
            for _ in range(3):
                app.processEvents()
            assert window.prediction_content.isHidden()
            window.grab().save(str(output / "prediction-empty.png"))
            window.navigate("结果与导出")
            for _ in range(3):
                app.processEvents()
            assert window.pred_report_body.isHidden()
            window.grab().save(str(output / "report-empty.png"))
            window.navigate("模型训练")
            for _ in range(3):
                app.processEvents()
            assert window.bundle is not None, window.model_label.text()
            assert not window.windowIcon().isNull()
            assert window.logo_path.exists()
            assert window.model_table.rowCount() == 4
            window.grab().save(str(output / "training.png"))
            window.navigate("融合优化")
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "fusion.png"))
            window.navigate("分子预测")
            window.smiles.setText("C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")
            window.predict_button.click()
            window.grab().save(str(output / "prediction-running.png"))
            settle(window, app)
            for _ in range(3):
                app.processEvents()
            assert window.last_result is not None, window.conclusion.text()
            assert not window.prediction_content.isHidden()
            assert window.last_result["screening"]["adjusted_score"] is None
            assert not window.molecule_image.pixmap().isNull()
            window.grab().save(str(output / "prediction.png"))
            window.navigate("三级漏斗筛选")
            scroll = window.pages.widget(4)
            scroll.verticalScrollBar().setValue(0)
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "funnel.png"))
            prediction = window.last_result
            window.navigate("结果与导出")
            for _ in range(3):
                app.processEvents()
            assert window.report_stage_table.rowCount() == 3
            assert window.report_prediction_table.rowCount() == 4
            assert window.report_prediction_table.geometry().bottom() < window.export_format_title.y()
            window.grab().save(str(output / "screening-report.png"))
            original_save = QFileDialog.getSaveFileName
            original_directory = QFileDialog.getExistingDirectory
            try:
                for kind in ("html", "csv", "json"):
                    destination = output / ("分子筛选报告." + kind)
                    QFileDialog.getSaveFileName = lambda *a, p=destination: (str(p), "")
                    window.export_prediction(kind)
                    assert destination.exists() and destination.stat().st_size > 100
                for kind in ("html", "csv", "json"):
                    destination = output / ("模型训练报告." + kind)
                    QFileDialog.getSaveFileName = lambda *a, p=destination: (str(p), "")
                    window.export_training_report(kind)
                    assert destination.exists() and destination.stat().st_size > 100
                import csv
                from .storage import read_json
                with (output / "模型训练报告.csv").open(encoding="utf-8-sig", newline="") as stream:
                    training_rows = list(csv.DictReader(stream))
                assert len(training_rows) == 5
                assert max(len(value) for row in training_rows for value in row.values()) < 32767
                assert read_json(output / "模型训练报告.json")["run_id"] == window.bundle[1]["run_id"]
                train_output = output / "training-export"
                train_output.mkdir()
                QFileDialog.getExistingDirectory = lambda *a: str(train_output)
                window.export_training()
                exported_training = next(train_output.iterdir())
                assert (exported_training / "训练报告.html").exists()
                assert (exported_training / "模型指标.csv").exists()
            finally:
                QFileDialog.getSaveFileName = original_save
                QFileDialog.getExistingDirectory = original_directory
            window.report_tabs.setCurrentIndex(1)
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "training-report.png"))
            layouts = [verify_layout(window, app, size) for size in ((1366, 768), (1480, 940), (1920, 1080), (880, 460))]
            window.resize(1050, 640)
            window.navigate("结果与导出")
            for expanded in (True, False):
                window.prediction_raw_details.set_expanded(expanded)
                for _ in range(3):
                    app.processEvents()
                assert window.report_prediction_table.geometry().bottom() < window.export_format_title.y()
                assert window.pages.widget(5).horizontalScrollBar().maximum() == 0
            window.grab().save(str(output / "report-small.png"))
            window.navigate("三级漏斗筛选")
            window.rules_details.set_expanded(True)
            window.demo_details.set_expanded(True)
            for _ in range(3):
                app.processEvents()
            assert window.pages.widget(4).horizontalScrollBar().maximum() == 0
            window.pages.widget(4).ensureWidgetVisible(window.demo_details)
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "advanced-small.png"))
            window.rules_details.set_expanded(False)
            window.demo_details.set_expanded(False)
            window.use_demo.setChecked(True)
            assert window.last_result is None
            assert not window.export_csv_button.isEnabled()
            window.run_prediction()
            settle(window, app)
            assert window.last_result["screening"]["demo"]
            window.demo_fields["hepatotoxic"].setChecked(True)
            assert window.last_result is None
            assert not window.export_csv_button.isEnabled()
            window.run_prediction()
            settle(window, app)
            assert "ADMET关键风险" in window.conclusion.text()
            window.use_demo.setChecked(False)
            window.navigate("分子预测")
            window.resize(*capture_size)
            window.smiles.setText("CCO")
            for _ in range(3):
                app.processEvents()
            assert "已失效" in window.conclusion.text()
            assert not window.view_report_button.isEnabled()
            window.grab().save(str(output / "prediction-invalidated.png"))
            window.smiles.setText("invalid_SMILES")
            window.predict_button.click()
            settle(window, app)
            assert window.last_result is None and "预测失败" in window.conclusion.text()
            assert "Traceback" not in window.statusBar().currentMessage()
            assert "SMILES" in window.statusBar().currentMessage()
            for _ in range(3):
                app.processEvents()
            window.grab().save(str(output / "prediction-error.png"))
            result.update(status="passed", time=utc_now(), platform=sys.platform,
                          qt_platform=app.platformName(), frozen=bool(getattr(sys, "frozen", False)),
                          app_version=__version__, artifact_directory=str(output), device_pixel_ratio=window.devicePixelRatioF(),
                          model_version=window.bundle[1]["run_id"], prediction=prediction, layout_cases=layouts,
                          fonts={"body": QFontInfo(window.training_data_hint.font()).family(),
                                 "mixed_caption": QFontInfo(window.pic50_caption.font()).family(),
                                 "number": QFontInfo(window.activity_label.font()).family()},
                          checks=["native_Qt_window" if app.platformName() == "windows" else "offscreen_Qt_window", "real_model_load", "button_prediction", "structure_render",
                                  "default_missing_funnel", "demo_risk_elimination", "invalid_smiles", "logo",
                                  "separate_readable_reports", "html_csv_json_export", "training_report_export",
                                  "six_distinct_navigation_pages", "compact_empty_states", "idle_progress_hidden", "report_reflow_without_overlap", "small_window_advanced_parameters", "async_prediction_busy_state",
                                  "invalidated_result_blocks_export", "all_page_title_footer_and_last_line",
                                  "1366_768_and_minimum_window", "explicit_error_and_waiting_materials"])
        except Exception:
            import traceback
            result.update(status="failed", error=traceback.format_exc())
        write_json(output / "result.json", result)
        window.close()
        app.quit()

    QTimer.singleShot(1500, check)
    app.exec()
    if result.get("status") != "passed":
        raise RuntimeError(result.get("error", "桌面检查未完成"))
    return result
