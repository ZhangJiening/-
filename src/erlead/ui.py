from __future__ import annotations
import csv
import io
import json
import shutil
import sys
import traceback
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QRectF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
from rdkit.Chem import Draw, rdMolDescriptors
from . import APP_NAME, MODEL_NAMES, __version__
from .chemistry import properties, standardize
from .data import prepare
from .screening import Rules, screen
from .storage import asset_location, model_location, read_json, utc_now, write_json
from .training import load_bundle, predict, train

STYLE = """
QMainWindow,QScrollArea,QWidget#base {background:#f1f6fc;color:#18304f;}
QWidget {font-family:'Microsoft YaHei UI';font-size:13px;color:#18304f;}
QFrame#header {background:white;border-bottom:1px solid #dfE8f4;}
QLabel#brand {font-size:20px;font-weight:700;color:#122f58;}
QLabel#title {font-size:25px;font-weight:700;margin-bottom:8px;}
QLabel#muted {color:#637b97;}
QGroupBox {background:white;border:1px solid #dce8f5;border-radius:10px;margin-top:14px;padding:18px 12px 10px;font-weight:600;}
QGroupBox::title {subcontrol-origin:margin;left:14px;padding:0 6px;color:#173b6d;}
QPushButton {background:white;border:1px solid #b3cef4;border-radius:6px;padding:9px 15px;color:#176bd3;}
QPushButton:hover {background:#eaf3ff;}
QPushButton:disabled {color:#9aa7b7;background:#f4f6fa;border-color:#dce2e8;}
QPushButton#primary {background:#1977ed;color:white;border:0;font-weight:600;}
QPushButton#nav {text-align:left;border:0;background:transparent;padding:14px 16px;font-size:15px;}
QPushButton#nav:checked {background:#deecff;color:#126de1;font-weight:700;}
QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox {background:white;border:1px solid #bfd2eb;border-radius:5px;padding:6px;min-height:23px;}
QTableWidget {background:white;border:1px solid #e3ebf5;gridline-color:#e8eef6;alternate-background-color:#f5f9fe;}
QHeaderView::section {background:#eaf1fa;padding:8px;border:0;font-weight:600;}
QPlainTextEdit {background:#fafcff;border:1px solid #dfe8f4;border-radius:5px;font-family:'Microsoft YaHei UI';}
QTabWidget::pane {border:0;}
QTabBar::tab {padding:10px 20px;background:#e9f0f9;border:0;}
QTabBar::tab:selected {background:white;color:#166dd7;}
QProgressBar {border:0;background:#e4edf8;min-height:6px;max-height:8px;border-radius:3px;}
QProgressBar::chunk {background:#2e86f3;}
"""
COLORS = ["#2988f8", "#22b8a5", "#ffa348", "#9280ed"]


def label(text, role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    if role:
        widget.setObjectName(role)
    return widget


def button(text, callback, primary=False):
    widget = QPushButton(text)
    widget.clicked.connect(callback)
    if primary:
        widget.setObjectName("primary")
    return widget


def table(headers, height=180):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    widget.verticalHeader().setVisible(False)
    widget.setAlternatingRowColors(True)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.setMinimumHeight(height)
    return widget


def populate(widget, rows):
    widget.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(str(value))
            widget.setItem(row, col, item)
    widget.resizeRowsToContents()


def group(title):
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    return box, layout


def scrollable():
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    content.setObjectName("base")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 12, 18, 20)
    scroll.setWidget(content)
    return scroll, layout


class Worker(QThread):
    message = Signal(str)
    completed = Signal(object)
    failed = Signal(str)
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
    def run(self):
        try:
            result = self.operation(self.message.emit)
            self.completed.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class Chart(QWidget):
    def __init__(self, mode):
        super().__init__()
        self.mode, self.values = mode, None
        self.setMinimumSize(300, 185)
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        if self.values is None:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "训练完成后展示真实结果")
            return
        if self.mode == "weights":
            weights = self.values
            size = min(self.height() - 25, self.width() * 0.48)
            rect = QRectF(8, 12, size, size)
            angle = 90 * 16
            p.setPen(Qt.PenStyle.NoPen)
            for i, w in enumerate(weights):
                p.setBrush(QColor(COLORS[i]))
                p.drawPie(rect, angle, -round(w * 360 * 16))
                angle -= round(w * 360 * 16)
            p.setBrush(QColor("white"))
            p.drawEllipse(rect.adjusted(size * .27, size * .27, -size * .27, -size * .27))
            p.setPen(QColor("#23466c"))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "模型融合\n权重")
            for i, (name, w) in enumerate(zip(MODEL_NAMES, weights)):
                p.setPen(QColor(COLORS[i]))
                p.drawText(int(size + 28), 35 + i * 38, f"{name}   {w:.1%}")
        else:
            for axis, metric, color in ((0, "R2", COLORS[0]), (1, "RMSE", COLORS[1])):
                offset = 15 + axis * self.width() / 2
                width = self.width() / 2 - 30
                p.setPen(QColor("#48617e"))
                p.drawText(int(offset), 18, "验证集 " + ("R²" if metric == "R2" else "RMSE"))
                maximum = max(1e-8, max(abs(self.values[name][metric]) for name in MODEL_NAMES))
                for i, name in enumerate(MODEL_NAMES):
                    value = self.values[name][metric]
                    y = 35 + i * 38
                    p.setPen(QColor("#48617e"))
                    p.drawText(int(offset), y + 10, name)
                    available = max(10, width - 130)
                    zero = offset + 65 + (available / 2 if metric == "R2" else 0)
                    length = available * value / maximum * (0.5 if metric == "R2" else 1)
                    p.fillRect(QRectF(min(zero, zero + length), y, max(1, abs(length)), 13), QColor("#d26c63" if value < 0 else color))
                    p.setPen(QColor("#c2cfdf"))
                    p.drawLine(int(zero), y - 2, int(zero), y + 16)
                    p.setPen(QColor("#48617e"))
                    p.drawText(int(offset + width - 58), y + 11, f"{value:.3f}")


class MainWindow(QMainWindow):
    def __init__(self, root: Path):
        super().__init__()
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.worker = None
        self.bundle = None
        self.last_prediction = None
        self.last_result = None
        self.external_stages = None
        self.setWindowTitle(APP_NAME)
        self.logo_path = asset_location("logo.png")
        self.setWindowIcon(QIcon(str(self.logo_path)))
        self.resize(1320, 940)
        self.setMinimumSize(1050, 720)
        self.setStyleSheet(STYLE)
        base = QWidget()
        base.setObjectName("base")
        self.setCentralWidget(base)
        outer = QVBoxLayout(base)
        outer.setContentsMargins(0, 0, 0, 0)
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(25, 17, 25, 17)
        logo = QLabel()
        logo.setObjectName("logo")
        logo.setToolTip(APP_NAME + " · ERα / ESR1")
        logo.setPixmap(QPixmap(str(self.logo_path)).scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(44, 44)
        header_layout.addWidget(logo)
        brand = label("筛选先锋  |  " + APP_NAME, "brand")
        brand.setWordWrap(False)
        header_layout.addWidget(brand, 1)
        target_label = label("ERα / ESR1 固定靶点  ·  v" + __version__, "muted")
        target_label.setWordWrap(False)
        header_layout.addWidget(target_label)
        outer.addWidget(header)
        body = QHBoxLayout()
        outer.addLayout(body)
        nav = QVBoxLayout()
        nav.setContentsMargins(10, 15, 5, 15)
        self.nav_buttons = []
        entries = [("数据导入与清洗", 0, 0), ("模型训练", 0, 1), ("融合优化", 0, 1),
                   ("分子预测", 1, 0), ("三级漏斗筛选", 1, 0), ("结果与导出", 0, 2)]
        for text, page, tab in entries:
            b = button(text, lambda checked=False, p=page, t=tab, text=text: self.navigate(p, t, text))
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setMinimumWidth(180)
            nav.addWidget(b)
            self.nav_buttons.append(b)
        nav.addStretch()
        nav.addWidget(label("真实活性回归\n后续阶段缺测时显示未评估\n仅用于科研初筛", "muted"))
        body.addLayout(nav)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.pages.addWidget(self.training_page())
        self.pages.addWidget(self.prediction_page())
        self.smiles.textChanged.connect(self.invalidate_input)
        self.statusBar().showMessage("准备就绪")
        self.refresh_data()
        try:
            self.set_bundle(model_location(root))
        except Exception as error:
            self.model_label.setText(str(error))
            self.append_log("当前模型未加载：" + str(error))
        self.navigate(0, 0, entries[0][0])
        self.restore_rules(initial=True)

    def navigate(self, page, tab, text):
        self.pages.setCurrentIndex(page)
        if page == 0:
            self.tabs.setCurrentIndex(tab)
        for b in self.nav_buttons:
            b.setChecked(b.text() == text)

    def training_page(self):
        page, layout = scrollable()
        layout.addWidget(label("模型训练与多算法融合", "title"))
        layout.addWidget(label("ERα活性回归 · 真实实验IC50 → pIC50 · 四模型训练 → 三算法融合权重优化", "muted"))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        row = QHBoxLayout()
        self.download_button = button("获取并清洗ChEMBL数据", self.download_data, True)
        self.import_button = button("导入ERα实验CSV", self.import_data)
        self.refresh_button = button("重新下载新快照", lambda: self.download_data(refresh=True))
        row.addWidget(self.download_button)
        row.addWidget(self.import_button)
        row.addWidget(self.refresh_button)
        row.addStretch()
        data_layout.addLayout(row)
        self.data_label = label("尚未准备数据", "muted")
        data_layout.addWidget(self.data_label)
        self.sample_table = table(["标准化SMILES", "pIC50", "测定条数", "原始化合物ID"], 260)
        data_layout.addWidget(self.sample_table)
        self.audit_view = QPlainTextEdit()
        self.audit_view.setReadOnly(True)
        self.audit_view.setMaximumHeight(200)
        data_layout.addWidget(self.audit_view)
        data_layout.addWidget(label("仅精确正值IC50用于回归。默认筛选直接结合测定；清洗与排除原因、来源和许可均保留。", "muted"))
        self.tabs.addTab(data_tab, "数据与清洗")
        model_tab = QWidget()
        grid = QGridLayout(model_tab)
        self.model_label = label("尚无模型", "muted")
        grid.addWidget(self.model_label, 0, 0, 1, 2)
        model_box, mb = group("基础模型真实训练 · 同一验证集")
        self.model_table = table(["回归器", "状态", "验证R²", "验证RMSE", "验证MAE"])
        populate(self.model_table, [[n, "未训练", "—", "—", "—"] for n in MODEL_NAMES])
        mb.addWidget(self.model_table)
        grid.addWidget(model_box, 1, 0)
        chart_box, cb = group("模型性能比较")
        self.metric_chart = Chart("metrics")
        cb.addWidget(self.metric_chart)
        grid.addWidget(chart_box, 1, 1)
        fusion_box, fb = group("融合优化 · 四模型权重非负且和为1")
        self.fusion_table = table(["优化器", "ANN / RF / XGB / LR", "验证RMSE"])
        populate(self.fusion_table, [[m, "未运行", "—"] for m in ("GA", "SA", "TS")])
        fb.addWidget(self.fusion_table)
        grid.addWidget(fusion_box, 2, 0)
        final_box, final_layout = group("冻结方案的独立测试结果")
        self.test_label = label("先在验证集选择方案，再进行一次独立测试。")
        final_layout.addWidget(self.test_label)
        final_layout.addWidget(label("融合不保证优于每个单模型；按真实指标报告。", "muted"))
        grid.addWidget(final_box, 2, 1)
        controls = QHBoxLayout()
        self.train_button = button("开始真实训练与融合", self.start_training, True)
        controls.addWidget(self.train_button)
        controls.addWidget(button("加载模型目录", self.choose_model))
        controls.addWidget(button("导出训练资料", self.export_training))
        grid.addLayout(controls, 3, 0, 1, 2)
        self.tabs.addTab(model_tab, "训练与融合")
        report_tab = QWidget()
        report_layout = QVBoxLayout(report_tab)
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        report_layout.addWidget(label("训练来源、拆分、指标与参数"))
        report_layout.addWidget(self.report_view)
        report_layout.addWidget(button("导出模型、来源与评估资料", self.export_training))
        self.tabs.addTab(report_tab, "结果与导出")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(145)
        self.log_view.setPlaceholderText("下载、清洗、训练与异常记录")
        layout.addWidget(self.log_view)
        layout.addStretch()
        return page

    def prediction_page(self):
        page, layout = scrollable()
        layout.addWidget(label("分子预测与三级漏斗", "title"))
        box, form = group("分子输入 · 固定ERα / ESR1")
        self.smiles = QLineEdit()
        self.smiles.setObjectName("smilesInput")
        self.smiles.setPlaceholderText("输入小分子的SMILES；分子结构与预测值均实时计算")
        form.addWidget(self.smiles)
        controls = QHBoxLayout()
        self.predict_button = button("开始真实预测", self.run_prediction, True)
        controls.addWidget(self.predict_button)
        controls.addWidget(button("载入结构示例", lambda: self.smiles.setText("C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")))
        controls.addWidget(button("清空", self.clear_prediction))
        controls.addStretch()
        form.addLayout(controls)
        layout.addWidget(box)
        row = QHBoxLayout()
        molecule_box, ml = group("RDKit二维分子结构")
        self.molecule_image = QLabel("等待输入")
        self.molecule_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.molecule_image.setMinimumSize(340, 200)
        ml.addWidget(self.molecule_image)
        self.properties_label = label("分子式 / MW / LogP / TPSA：—", "muted")
        ml.addWidget(self.properties_label)
        row.addWidget(molecule_box)
        activity_box, al = group("真实活性预测")
        self.activity_label = label("pIC50  —")
        self.activity_label.setStyleSheet("font-size:32px;color:#1476ee;font-weight:700;")
        al.addWidget(self.activity_label)
        self.activity_status = label("阶段1尚未评估", "muted")
        al.addWidget(self.activity_status)
        self.prediction_table = table(["模型", "pIC50", "融合权重"], 170)
        al.addWidget(self.prediction_table)
        row.addWidget(activity_box)
        weights_box, wl = group("模型融合权重")
        self.weights_chart = Chart("weights")
        wl.addWidget(self.weights_chart)
        row.addWidget(weights_box)
        layout.addLayout(row)
        config_box, cl = group("筛选参数 · 阶段权重与模型权重分别设置")
        parameters = QHBoxLayout()
        self.parameters = {}
        for key, caption, value, low, high in (("activity_threshold", "活性门槛", 6, 6, 12),
                ("s1", "活性权重", .4, 0, 1), ("s2", "ADMET权重", .35, 0, 1), ("s3", "结构权重", .25, 0, 1),
                ("reward", "奖励系数", 0, 0, 1), ("penalty", "惩罚系数", 0, 0, 1)):
            column = QVBoxLayout()
            column.addWidget(label(caption))
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setSingleStep(.05)
            spin.setDecimals(2)
            spin.setValue(value)
            spin.valueChanged.connect(self.recalculate)
            self.parameters[key] = spin
            column.addWidget(spin)
            parameters.addLayout(column)
        cl.addLayout(parameters)
        thresholds = QHBoxLayout()
        for key, caption, value, low, high in (("logs_min", "logS下限", -4, -20, 10), ("logs_max", "logS上限", 0, -20, 10),
                ("f_min", "F最低%", 30, 0, 100), ("ppb_max", "PPB最高%", 95, 0, 100)):
            thresholds.addWidget(label(caption))
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setValue(value)
            spin.valueChanged.connect(self.recalculate)
            self.parameters[key] = spin
            thresholds.addWidget(spin)
        cl.addLayout(thresholds)
        cfg_buttons = QHBoxLayout()
        cfg_buttons.addWidget(button("保存参数快照", self.save_rules))
        cfg_buttons.addWidget(button("恢复默认参数", self.restore_defaults))
        cfg_buttons.addWidget(button("导入真实阶段证据JSON", self.load_stage_evidence))
        cfg_buttons.addWidget(button("清除阶段2/3输入", self.clear_stages))
        cl.addLayout(cfg_buttons)
        layout.addWidget(config_box)
        demo_box, dl = group("阶段2 / 3流程输入")
        self.use_demo = QCheckBox("启用明确标注的流程演示数据（非真实ADMET/结构预测）")
        self.use_demo.toggled.connect(self.demo_changed)
        dl.addWidget(self.use_demo)
        demo_row = QHBoxLayout()
        self.demo_fields = {}
        for key, caption, value, low, high in (("logS", "logS", -2, -20, 10), ("F_percent", "F%", 50, 0, 100),
                ("PPB_percent", "PPB%", 90, 0, 100)):
            demo_row.addWidget(label(caption))
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setValue(value)
            spin.setEnabled(False)
            spin.valueChanged.connect(self.recalculate)
            self.demo_fields[key] = spin
            demo_row.addWidget(spin)
        for key, caption in (("hepatotoxic", "肝毒性风险"), ("CYP3A4_inhibitor", "CYP3A4高抑制风险")):
            check = QCheckBox(caption)
            check.setEnabled(False)
            check.toggled.connect(self.recalculate)
            self.demo_fields[key] = check
            demo_row.addWidget(check)
        demo_row.addWidget(label("演示满足数/67"))
        self.demo_count = QSpinBox()
        self.demo_count.setRange(0, 67)
        self.demo_count.setValue(56)
        self.demo_count.setEnabled(False)
        self.demo_count.valueChanged.connect(self.recalculate)
        demo_row.addWidget(self.demo_count)
        dl.addLayout(demo_row)
        dl.addWidget(label("本期未训练5项ADMET及67输出模型。原文未给齐67项定义，演示计数只展示流转规则。", "muted"))
        layout.addWidget(demo_box)
        funnel_box, fl = group("三级漏斗 · 输入 → 判定 → 输出 → 流转")
        self.funnel_table = table(["阶段", "输入/来源", "判定条件", "阶段状态", "输出", "流转"], 155)
        fl.addWidget(self.funnel_table)
        self.conclusion = label("等待真实模型预测")
        self.conclusion.setStyleSheet("font-size:17px;font-weight:700;color:#1766bc;padding:8px;")
        fl.addWidget(self.conclusion)
        self.score_label = label("完整综合分：未计算", "muted")
        fl.addWidget(self.score_label)
        fl.addWidget(label("科研初筛结果，需后续实验验证。缺测不折算为0或满分；硬性淘汰优先于奖励及总分。", "muted"))
        layout.addWidget(funnel_box)
        exports = QHBoxLayout()
        self.export_json_button = button("导出预测JSON", lambda: self.export_prediction("json"))
        self.export_csv_button = button("导出预测CSV", lambda: self.export_prediction("csv"))
        self.export_json_button.setEnabled(False)
        self.export_csv_button.setEnabled(False)
        exports.addStretch()
        exports.addWidget(self.export_csv_button)
        exports.addWidget(self.export_json_button)
        layout.addLayout(exports)
        layout.addStretch()
        return page

    def append_log(self, message):
        self.log_view.appendPlainText(message)
        self.statusBar().showMessage(message[:150])

    def start_job(self, operation, on_complete):
        if self.worker and self.worker.isRunning():
            return
        for b in (self.download_button, self.import_button, self.refresh_button, self.train_button):
            b.setEnabled(False)
        self.progress.setRange(0, 0)
        self.worker = Worker(operation)
        self.worker.message.connect(self.append_log)
        self.worker.completed.connect(on_complete)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(self.job_finished)
        self.worker.start()

    def job_finished(self):
        for b in (self.download_button, self.import_button, self.refresh_button, self.train_button):
            b.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)

    def job_failed(self, error):
        self.append_log(error)
        path = self.root / "reports" / "last-error.json"
        write_json(path, {"time": utc_now(), "error": error})
        QMessageBox.warning(self, "操作未完成", error.splitlines()[-1] + "\n完整原因已保留到运行记录。")

    def download_data(self, refresh=False):
        self.start_job(lambda log: prepare(self.root, log, refresh=refresh), lambda _: self.refresh_data())

    def import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择真实ERα结合测定CSV", "", "CSV (*.csv)")
        if not path:
            return
        source, ok = QInputDialog.getText(self, "数据来源", "请填写人类ERα/ESR1结合IC50实验的数据来源及许可说明：")
        if ok and source.strip():
            self.start_job(lambda log: prepare(self.root, log, Path(path), source), lambda _: self.refresh_data())

    def refresh_data(self):
        audit_path = self.root / "data" / "processed" / "audit.json"
        if not audit_path.exists():
            return
        audit = read_json(audit_path)
        self.data_label.setText(f"原始 {audit['raw_count']} 条  →  清洗后 {audit['unique_compounds']} 个化合物  |  pIC50范围 {audit['pIC50_range'][0]:.2f}–{audit['pIC50_range'][1]:.2f}")
        self.audit_view.setPlainText(json.dumps({k: v for k, v in audit.items() if k != "source"}, ensure_ascii=False, indent=2))
        import pandas as pd
        frame = pd.read_csv(audit_path.parent / "cleaned.csv").head(10)
        populate(self.sample_table, [[r.canonical_smiles, f"{r.pIC50:.3f}", r.record_count, r.molecule_ids] for r in frame.itertuples()])
        self.append_log("数据就绪，可开始真实训练")

    def start_training(self):
        self.tabs.setCurrentIndex(1)
        self.start_job(lambda log: train(self.root, log=log), self.set_bundle)

    def set_bundle(self, folder):
        self.bundle = load_bundle(Path(folder))
        self.model_folder = Path(folder)
        report = self.bundle[1]
        counts = report["split_counts"]
        self.model_label.setText(f"版本 {report['run_id']}  |  训练 {counts['train']} / 验证 {counts['validation']} / 独立测试 {counts['test']}  |  固定种子 {report['seed']}")
        populate(self.model_table, [[n, "已真实训练", *[f"{report['validation_metrics'][n][m]:.4f}" for m in ("R2", "RMSE", "MAE")]] for n in MODEL_NAMES])
        populate(self.fusion_table, [[m + (" ★" if m == report["selected"] else ""),
            " / ".join(f"{w:.3f}" for w in report["optimizers"][m]["weights"]),
            f"{report['validation_metrics'][m]['RMSE']:.4f}"] for m in ("GA", "SA", "TS")])
        m = report["test_metrics"]["ensemble"]
        self.test_label.setText(f"融合方法：{report['selected']}\n\n独立测试 R²：{m['R2']:.4f}\nRMSE：{m['RMSE']:.4f}  |  MAE：{m['MAE']:.4f}\n\n方案在验证集冻结；独立测试评估1次。")
        self.test_label.setText(self.test_label.text() + "\n\n单模型独立测试R²：\n" + "  /  ".join(f"{n} {report['test_metrics'][n]['R2']:.4f}" for n in MODEL_NAMES))
        self.metric_chart.values = report["validation_metrics"]
        self.metric_chart.update()
        self.weights_chart.values = report["weights"]
        self.weights_chart.update()
        summary = {k: v for k, v in report.items() if k not in ("optimizers", "model_parameters")}
        self.report_view.setPlainText(json.dumps(summary, ensure_ascii=False, indent=2))
        self.clear_prediction()
        self.append_log("已加载并校验4个真实模型：" + report["run_id"])

    def choose_model(self):
        folder = QFileDialog.getExistingDirectory(self, "选择本项目可信训练的模型版本目录")
        if folder:
            try:
                self.set_bundle(Path(folder))
            except Exception as error:
                QMessageBox.warning(self, "模型加载失败", str(error))

    def clear_prediction(self):
        self.last_prediction = self.last_result = None
        self.smiles.clear()
        self.prediction_table.setRowCount(0)
        self.funnel_table.setRowCount(0)
        self.molecule_image.clear()
        self.molecule_image.setText("等待输入")
        self.properties_label.setText("分子式 / MW / LogP / TPSA：—")
        self.activity_label.setText("pIC50  —")
        self.activity_status.setText("阶段1尚未评估")
        self.conclusion.setText("等待真实模型预测")
        self.score_label.setText("完整综合分：未计算")
        self.enable_export(False)

    def invalidate_input(self):
        self.last_prediction = self.last_result = None
        self.external_stages = None
        self.enable_export(False)
        self.prediction_table.setRowCount(0)
        self.funnel_table.setRowCount(0)
        self.activity_label.setText("pIC50  —")
        self.activity_status.setText("阶段1尚未评估")
        self.molecule_image.clear()
        self.properties_label.setText("等待对当前输入进行预测")
        self.conclusion.setText("等待真实模型预测")
        self.score_label.setText("完整综合分：未计算")

    def enable_export(self, enabled):
        self.export_json_button.setEnabled(enabled)
        self.export_csv_button.setEnabled(enabled)

    def run_prediction(self):
        self.last_prediction = self.last_result = None
        self.enable_export(False)
        try:
            if self.bundle is None:
                raise ValueError("请先训练或加载模型")
            smiles = self.smiles.text().strip()
            mol, canonical = standardize(smiles)
            result = predict(smiles, self.bundle)
            result["canonical_smiles"] = canonical
            result["properties"] = properties(mol)
            buffer = io.BytesIO()
            Draw.MolToImage(mol, size=(420, 230)).save(buffer, format="PNG")
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            self.molecule_image.setPixmap(pixmap.scaled(max(250, self.molecule_image.width() - 8), 220, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            props = result["properties"]
            self.properties_label.setText(f"{rdMolDescriptors.CalcMolFormula(mol)}  |  MW {props['MW']:.2f}  |  LogP {props['LogP']:.2f}  |  TPSA {props['TPSA']:.2f}")
            self.activity_label.setText(f"pIC50  {result['ensemble_pIC50']:.3f}")
            populate(self.prediction_table, [[name, f"{result['predictions'][name]:.3f}", f"{w:.3f}"] for name, w in zip(MODEL_NAMES, result["weights"])])
            self.last_prediction = result
            self.recalculate()
        except Exception as error:
            self.prediction_table.setRowCount(0)
            self.funnel_table.setRowCount(0)
            self.activity_label.setText("pIC50  —")
            self.activity_status.setText("阶段1尚未评估")
            self.molecule_image.clear()
            self.properties_label.setText("分子输入无效，未生成结果")
            self.conclusion.setText("预测失败：" + str(error))
            self.score_label.setText("完整综合分：未计算")

    def current_rules(self):
        values = {k: s.value() for k, s in self.parameters.items()}
        values["stage_weights"] = tuple(values.pop(k) for k in ("s1", "s2", "s3"))
        rules = Rules(**values)
        rules.validate()
        return rules

    def recalculate(self, *_):
        if self.last_prediction is None:
            return
        self.last_result = None
        self.enable_export(False)
        try:
            rules = self.current_rules()
            admet = structure = evidence = None
            demo = self.use_demo.isChecked()
            if demo:
                admet = {k: w.isChecked() if isinstance(w, QCheckBox) else w.value() for k, w in self.demo_fields.items()}
                structure = [True] * self.demo_count.value() + [False] * (67 - self.demo_count.value())
            elif self.external_stages:
                admet = self.external_stages.get("admet")
                structure = self.external_stages.get("structure")
                evidence = self.external_stages["evidence"]
            screening = screen(self.last_prediction["ensemble_pIC50"], rules, admet, structure, demo, evidence)
            self.activity_status.setText(f"阶段1：{screening['stages'][0]['status']}  |  门槛 {rules.activity_threshold:.2f}")
            self.last_result = {**self.last_prediction, "screening": screening, "stage_evidence": None if demo else self.external_stages}
            rows = []
            for s in screening["stages"]:
                output = f"S={s['score']:.3f}" if s["score"] is not None else "未评估"
                if s.get("passed_count") is not None:
                    output += f"  ({s['passed_count']}/{'5' if s['stage'] == 2 else '67'})"
                inputs = (f"pIC50 = {s['input']['pIC50']:.3f}" if s["stage"] == 1 else
                          "无输入" if s["input"] is None else
                          json.dumps(s["input"], ensure_ascii=False) if s["stage"] == 2 else f"{s.get('passed_count')}/67项判定")
                rows.append([f"阶段{s['stage']} {s['name']}", str(s["source"]) + "\n" + inputs, s["criterion"],
                             ("演示·" if demo and s["stage"] > 1 else "") + s["status"], output, s["flow"]])
            populate(self.funnel_table, rows)
            self.conclusion.setText(screening["conclusion"])
            if screening["adjusted_score"] is None:
                self.score_label.setText("完整综合分：未计算（阶段2/3缺少有效数据）")
            else:
                self.score_label.setText(f"{screening['score_label']}：{screening['adjusted_score']:.4f}  |  基础分 {screening['base_score']:.4f}  |  规则：基础分 + 奖励×基础分 − 惩罚×(1−基础分)，限制至0–1")
            self.enable_export(True)
        except Exception as error:
            self.funnel_table.setRowCount(0)
            self.activity_status.setText("规则参数无效，判定未生成")
            self.conclusion.setText("参数或阶段输入无效：" + str(error))
            self.score_label.setText("完整综合分：未计算")

    def demo_changed(self, enabled):
        for w in [*self.demo_fields.values(), self.demo_count]:
            w.setEnabled(enabled)
        self.recalculate()

    def clear_stages(self):
        self.external_stages = None
        self.use_demo.setChecked(False)
        self.recalculate()

    def save_rules(self):
        try:
            from dataclasses import asdict
            rules = self.current_rules()
            snapshot = {"saved_at": utc_now(), "rules": asdict(rules)}
            write_json(self.root / "config" / "rules.json", snapshot)
            write_json(self.root / "reports" / "config_snapshots" / (utc_now().replace(":", "-") + ".json"), snapshot)
            self.statusBar().showMessage("参数与带时间的快照已保存")
        except Exception as error:
            QMessageBox.warning(self, "参数保存失败", str(error))

    def apply_rules(self, rules):
        rules.validate()
        from dataclasses import asdict
        values = asdict(rules)
        for k, v in zip(("s1", "s2", "s3"), values.pop("stage_weights")):
            self.parameters[k].setValue(v)
        for k, v in values.items():
            self.parameters[k].setValue(v)
        self.recalculate()

    def restore_defaults(self):
        self.apply_rules(Rules())

    def restore_rules(self, initial=False):
        path = self.root / "config" / "rules.json"
        try:
            if path.exists():
                self.apply_rules(Rules(**read_json(path)["rules"]))
        except Exception as error:
            self.append_log("参数文件无效，使用默认参数：" + str(error))
            self.restore_defaults()

    def load_stage_evidence(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入外部测量/模型证据JSON", "", "JSON (*.json)")
        if not path:
            return
        try:
            obj = read_json(Path(path))
            if not isinstance(obj.get("evidence"), str) or not obj["evidence"].strip():
                raise ValueError("需要evidence字段，说明测量/模型版本和数据来源")
            if obj.get("canonical_smiles") != standardize(self.smiles.text())[1]:
                raise ValueError("阶段证据必须包含与当前分子一致的canonical_smiles")
            if obj.get("structure") is not None:
                definitions = obj.get("constraint_definitions", [])
                if len(definitions) != 67 or len(set(definitions)) != 67 or not all(isinstance(x, str) and x.strip() for x in definitions):
                    raise ValueError("真实结构输入需要67项不同的约束定义，缺少时应保持未评估")
            screen(8, self.current_rules(), obj.get("admet"), obj.get("structure"), evidence=obj["evidence"])
            self.external_stages = obj
            self.use_demo.setChecked(False)
            self.recalculate()
        except Exception as error:
            QMessageBox.warning(self, "阶段数据未导入", str(error))

    def export_prediction(self, kind):
        if self.last_result is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "保存可追溯预测结果", "prediction." + kind, kind.upper() + " (*." + kind + ")")
        if not path:
            return
        try:
            if kind == "json":
                write_json(Path(path), self.last_result)
            else:
                result = self.last_result
                row = {"smiles": result["canonical_smiles"], "model_version": result["model_version"],
                       "predicted_at": result["predicted_at"], "data_sha256": result["data_sha256"], **result["predictions"],
                       "ensemble_pIC50": result["ensemble_pIC50"], "conclusion": result["screening"]["conclusion"],
                       "demo": result["screening"]["demo"], "score": result["screening"]["adjusted_score"],
                       "provenance_and_rules_json": json.dumps(result, ensure_ascii=False)}
                with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(row))
                    writer.writeheader()
                    writer.writerow(row)
            self.statusBar().showMessage("预测结果已导出：" + str(path))
        except Exception as error:
            QMessageBox.warning(self, "导出失败", str(error))

    def export_training(self):
        if self.bundle is None:
            QMessageBox.information(self, "尚无训练资料", "请先完成真实训练或加载模型")
            return
        destination = QFileDialog.getExistingDirectory(self, "选择训练资料导出位置")
        if not destination:
            return
        try:
            folder = Path(destination) / ("ERLead-" + self.bundle[1]["run_id"])
            folder.mkdir(exist_ok=False)
            shutil.copytree(self.model_folder, folder / "models")
            report_dir = self.root / "reports" / self.bundle[1]["run_id"]
            if report_dir.exists():
                shutil.copytree(report_dir, folder / "reports")
            write_json(folder / "data-audit.json", self.bundle[1]["cleaning"])
            self.statusBar().showMessage("已导出至：" + str(folder))
        except Exception as error:
            QMessageBox.warning(self, "导出失败", str(error))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "任务运行中", "请等待当前下载/训练完成后关闭，避免留下不完整产物。异常中断后可查看运行日志。")
            event.ignore()
        else:
            event.accept()


def launch(root):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow(root)
    window.show()
    return app.exec()
