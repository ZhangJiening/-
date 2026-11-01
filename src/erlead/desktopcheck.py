"""Executable business smoke check of the native Qt window, also usable when frozen."""
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .storage import utc_now, write_json
from .ui import MainWindow


def run_check(root):
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(root)
    window.show()
    output = root / "reports" / "desktop-check"
    output.mkdir(parents=True, exist_ok=True)
    result = {}

    def check():
        try:
            window.navigate(0, 1, "模型训练")
            app.processEvents()
            assert window.bundle is not None, window.model_label.text()
            assert not window.windowIcon().isNull()
            assert window.logo_path.exists()
            assert window.model_table.rowCount() == 4
            window.grab().save(str(output / "training.png"))
            window.navigate(1, 0, "分子预测")
            window.smiles.setText("C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")
            window.predict_button.click()
            app.processEvents()
            assert window.last_result is not None, window.conclusion.text()
            assert window.last_result["screening"]["adjusted_score"] is None
            assert not window.molecule_image.pixmap().isNull()
            window.grab().save(str(output / "prediction.png"))
            scroll = window.pages.widget(1)
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            app.processEvents()
            window.grab().save(str(output / "funnel.png"))
            prediction = window.last_result
            window.use_demo.setChecked(True)
            assert window.last_result["screening"]["demo"]
            window.demo_fields["hepatotoxic"].setChecked(True)
            assert "ADMET关键风险" in window.conclusion.text()
            window.smiles.setText("invalid_SMILES")
            window.predict_button.click()
            assert window.last_result is None and "预测失败" in window.conclusion.text()
            result.update(status="passed", time=utc_now(), platform=sys.platform,
                          qt_platform=app.platformName(), frozen=bool(getattr(sys, "frozen", False)),
                          model_version=window.bundle[1]["run_id"], prediction=prediction,
                          checks=["native_Qt_window", "real_model_load", "button_prediction", "structure_render",
                                  "default_missing_funnel", "demo_risk_elimination", "invalid_smiles", "logo"])
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
