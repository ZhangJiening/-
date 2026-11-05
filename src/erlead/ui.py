from __future__ import annotations
import csv
import io
import math
import re
import json
import shutil
import sys
import traceback
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QRectF, QSize, QUrl, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QPen, QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QSizePolicy,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget, QRadioButton, QButtonGroup, QDialog, QMenu, QBoxLayout)
from rdkit.Chem import Draw, rdMolDescriptors
from . import APP_NAME, MODEL_NAMES, __version__
from .chemistry import properties, standardize
from .data import prepare
from .workbench import ActionScrollArea, CsvDropZone, CsvImportDialog, icon_button, line_icon, set_tone, workbench_font
from .screening import Rules, screen
from .storage import asset_location, digest, model_location, read_json, utc_now, write_json
from .training import load_bundle, predict, train
from .reporting import (SCOPE_TEXT, MODEL_HEADERS, STAGE_HEADERS, stage_rows, stage_reason,
                        score_text, training_rows, training_html, write_csv, export_prediction_file, display_time,
                        export_training_file)

STYLE = """
QMainWindow,QScrollArea,QWidget#base {background:#f5f7fb;color:#1c2b3e;}
QWidget {font-family:'Microsoft YaHei UI','Microsoft YaHei','Noto Sans CJK SC','Segoe UI','Segoe UI Symbol';font-size:14px;color:#303844;}
QFrame#header {background:#ffffff;border-bottom:1px solid #e4e8ef;}
QLabel#brand {font-size:18px;font-weight:700;color:#172b45;}
QLabel#title {font-size:24px;font-weight:600;color:#26313f;margin:0;}
QLabel#muted {color:#667281;font-size:13px;}
QLabel#number {font-family:'Segoe UI';font-size:47px;font-weight:600;color:#183b68;}
QLabel#metric {font-family:'Microsoft YaHei UI','Microsoft YaHei','Segoe UI';font-size:14px;font-weight:400;color:#596573;}
QLabel#stat {font-family:'Segoe UI','Microsoft YaHei UI';font-size:22px;font-weight:500;color:#303844;}
QLabel#section {font-size:15px;font-weight:600;}
QLabel#sectionTitle {font-size:15px;font-weight:600;color:#21354e;padding:0 0 10px;}
QFrame#sectionPanel {background:white;border:1px solid #e2e7ef;border-radius:8px;}
QFrame#navigation {background:white;border-bottom:1px solid #e0e6ef;}
QFrame#pageFooter {background:white;border-top:1px solid #e1e7f0;}
QFrame#stageRow {background:white;border:0;border-bottom:1px solid #edf0f5;}
QLabel#stageNumber {background:#eaf2fd;color:#1977ed;border-radius:15px;font-size:13px;font-weight:700;}
QLabel#notice {background:#eaf3ff;color:#265b99;border:1px solid #dce9fb;border-radius:6px;padding:12px 15px;font-weight:600;}
QLabel#notice[tone="good"] {background:#eef8f3;color:#2c7856;border-color:#daeee2;}
QLabel#notice[tone="bad"] {background:#fff0f0;color:#ae3c3c;border-color:#f4dadd;}
QLabel#notice[tone="warning"] {background:#fff7e8;color:#91631b;border-color:#f5e7ca;}
QLabel#statusTag {background:#edf0f5;color:#6d7b8e;border:0;border-radius:12px;padding:5px 12px;font-weight:600;}
QLabel#statusTag[tone="good"] {background:#eaf5ef;color:#287650;}
QLabel#statusTag[tone="bad"] {background:#fbecee;color:#b03c4a;}
QLabel#statusTag[tone="warning"] {background:#fff4df;color:#986818;}
QFrame#dropZone {background:#fafbfd;border:1px dashed #cdd7e5;border-radius:6px;}
QGroupBox {background:white;border:1px solid #e2e7ef;border-radius:7px;margin-top:10px;padding:12px;}
QGroupBox::title {subcontrol-origin:margin;left:12px;padding:0 5px;color:#536479;}
QPushButton {background:white;border:1px solid #ced7e3;border-radius:5px;padding:7px 12px;color:#384656;min-height:22px;}
QPushButton:hover {background:#f0f6ff;border-color:#9ebce5;}
QPushButton:focus {border-color:#1977ed;}
QPushButton:disabled {color:#9aa5b3;background:#edf0f4;border-color:#e2e6ec;}
QPushButton#primary {background:#1977ed;color:white;border:1px solid #1977ed;font-weight:600;}
QPushButton#primary:hover {background:#126ad9;}
QPushButton#primary:disabled {background:#e1e6ee;border-color:#e1e6ee;color:#96a2b2;}
QPushButton#nav {border:0;border-bottom:3px solid transparent;border-radius:0;background:transparent;padding:14px 5px 12px;font-size:13px;color:#46546a;}
QPushButton#nav:hover {background:#f6f9ff;}
QPushButton#nav:checked {background:#f3f7fe;border-bottom-color:#1977ed;color:#176bd3;font-weight:700;}
QPushButton#disclosure {text-align:left;border:1px solid #e0e6ef;border-radius:5px;background:#fafbfd;padding:10px 13px;color:#42556e;font-weight:600;}
QLineEdit,QDoubleSpinBox,QSpinBox,QComboBox {background:white;border:1px solid #cfd8e5;border-radius:5px;padding:7px;min-height:22px;selection-background-color:#1977ed;}
QLineEdit:focus,QDoubleSpinBox:focus,QSpinBox:focus,QComboBox:focus {border-color:#1977ed;}
QLineEdit#smilesInput {font-family:'Segoe UI','Microsoft YaHei UI';font-size:15px;min-height:22px;}
QCheckBox,QRadioButton {spacing:8px;min-height:23px;}
QTableWidget {background:white;color:#303844;border:0;gridline-color:#e9edf3;alternate-background-color:#fbfcfe;selection-background-color:#eaf3ff;selection-color:#18304f;}
QHeaderView::section {background:#f3f6fa;color:#536479;padding:7px 7px;border:0;border-bottom:1px solid #e6ebf2;font-weight:600;}
QPlainTextEdit {background:#fafbfd;border:1px solid #e0e6ee;border-radius:5px;font-family:'Consolas','Microsoft YaHei UI';font-size:12px;padding:7px;}
QTabWidget::pane {border:0;background:transparent;}
QTabBar::tab {padding:10px 20px;background:transparent;border:0;border-bottom:2px solid #e3e8f0;color:#748297;}
QTabBar::tab:selected {border-bottom-color:#1977ed;color:#1977ed;font-weight:600;}
QProgressBar {border:0;background:#e8edf4;min-height:5px;max-height:5px;border-radius:2px;}
QProgressBar::chunk {background:#1977ed;}
QLabel#error {color:#ad3535;font-size:13px;}
QLabel#step {background:#f0f2f5;color:#657180;border-radius:5px;padding:8px;font-size:13px;}
QLabel#step[tone="good"] {background:#edf6f0;color:#327351;}
QLabel#step[tone="info"] {background:#edf4ff;color:#2763a1;}
QLabel#step[tone="bad"] {background:#fff0f0;color:#ad3535;}
QLabel#emptyCaption {font-size:14px;color:#667281;}
QScrollArea {border:0;}
QScrollBar:vertical {background:#f3f5f8;width:9px;margin:0;}
QScrollBar::handle:vertical {background:#cbd4e0;border-radius:4px;min-height:25px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QStatusBar {background:#ffffff;border-top:1px solid #e5e9f0;color:#718096;}
"""
COLORS = ["#83abe6", "#548bdd", "#1977ed", "#a3bde7"]



def label(text, role=None):
    widget = QLabel(text)
    widget.setFont(workbench_font())
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


class ResultTable(QTableWidget):
    """Report a preferred row height; let the layout position sibling controls."""
    def __init__(self, columns, height_limit):
        super().__init__(0, columns)
        self.height_limit = max(1400, height_limit)
        self._fitting = False
        self._content_height = 0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.hide()

    def sizeHint(self):
        size = super().sizeHint()
        return QSize(size.width(), getattr(self, "_content_height", 0))

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        one_row = self.horizontalHeader().sizeHint().height() + (self.rowHeight(0) if self.rowCount() else 0) + 4
        return QSize(size.width(), getattr(self, "_content_height", 0))

    def setRowCount(self, count):
        super().setRowCount(count)
        self.setVisible(count > 0)
        if count == 0:
            self._content_height = 0
            self.setMaximumHeight(0)
            self.updateGeometry()

    def fit_content(self):
        if self._fitting or not self.rowCount():
            return
        self._fitting = True
        try:
            self.ensurePolished()
            if self.wordWrap():
                self.resizeRowsToContents()
            else:
                for row in range(self.rowCount()):
                    controls = [self.cellWidget(row, col) for col in range(self.columnCount())]
                    needed = max((max(w.minimumSizeHint().height(), w.sizeHint().height()) for w in controls if w is not None), default=0)
                    self.setRowHeight(row, max(32, needed + 4 if needed else 0))
            height = self.horizontalHeader().sizeHint().height() + sum(self.rowHeight(i) for i in range(self.rowCount())) + 4
            if self.horizontalScrollBar().maximum() > 0:
                height += self.horizontalScrollBar().sizeHint().height()
            wanted = min(self.height_limit, height)
            if self._content_height != wanted:
                self._content_height = wanted
                self.setMaximumHeight(wanted)
                self.updateGeometry()
        finally:
            self._fitting = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_content()

    def showEvent(self, event):
        super().showEvent(event)
        self.fit_content()


class ContentTabs(QTabWidget):
    """The current page determines the height, including expanded details."""
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.currentChanged.connect(lambda _: self.updateGeometry())
        stack = self.findChild(QStackedWidget)
        stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        stack.setMinimumHeight(0)

    def sizeHint(self):
        current = self.currentWidget()
        if current is None:
            return super().sizeHint()
        size = current.sizeHint()
        return QSize(size.width(), size.height() + self.tabBar().sizeHint().height() + 8)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        current = self.currentWidget()
        if current is None:
            return super().heightForWidth(width)
        layout = current.layout()
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else layout.sizeHint().height()
        return height + self.tabBar().sizeHint().height() + 8

    def minimumSizeHint(self):
        current = self.currentWidget()
        if current is None:
            return super().minimumSizeHint()
        size = current.minimumSizeHint()
        return QSize(size.width(), size.height() + self.tabBar().sizeHint().height() + 8)


def table(headers, height=180, wrap=False):
    widget = ResultTable(len(headers), height)
    widget.setHorizontalHeaderLabels(headers)
    widget.setWordWrap(wrap)
    for col, title in enumerate(headers):
        widget.horizontalHeaderItem(col).setFont(workbench_font(bold=True))
        numeric = any(word in title for word in ("R²", "RMSE", "MAE", "pIC50", "权重", "记录数"))
        widget.horizontalHeaderItem(col).setTextAlignment(
            (Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    widget.verticalHeader().setVisible(False)
    widget.verticalHeader().setMinimumSectionSize(28)
    widget.verticalHeader().setDefaultSectionSize(30)
    widget.setAlternatingRowColors(True)
    widget.setShowGrid(False)
    widget.setTextElideMode(Qt.TextElideMode.ElideMiddle)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    return widget


def populate(widget, rows):
    widget.setRowCount(len(rows))
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            try:
                float(str(value).strip().rstrip("%"))
                numeric = True
            except ValueError:
                numeric = False
            item.setTextAlignment((Qt.AlignmentFlag.AlignRight if numeric else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter)
            item.setFont(workbench_font(numeric=numeric))
            item.setToolTip(str(value))
            widget.setItem(row, col, item)
    widget.fit_content()


def group(title):
    box = QFrame()
    box.setObjectName("sectionPanel")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(8)
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    heading = label(title, "sectionTitle")
    heading.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout.addWidget(heading)
    return box, layout

def scrollable():
    scroll = ActionScrollArea()
    scroll.setWidgetResizable(True)
    content = QWidget()
    content.setObjectName("base")
    layout = QVBoxLayout(content)
    layout.setContentsMargins(24, 20, 24, 22)
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


class Disclosure(QFrame):
    """A compact, keyboard-accessible section that starts collapsed."""
    def __init__(self, title):
        super().__init__()
        self.title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.toggle = QPushButton()
        self.toggle.setObjectName("disclosure")
        self.toggle.setCheckable(True)
        self.toggle.setAccessibleName(title)
        layout.addWidget(self.toggle)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 8, 0, 8)
        layout.addWidget(self.content)
        self.toggle.toggled.connect(self.set_expanded)
        self.set_expanded(False)

    def set_expanded(self, expanded):
        self.toggle.setChecked(expanded)
        self.toggle.setText(("▾  " if expanded else "▸  ") + self.title)
        self.content.setVisible(expanded)


class MoleculeView(QLabel):
    def __init__(self):
        super().__init__("输入SMILES后显示二维分子结构")
        self.original = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, 185)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

    def show_structure(self, pixmap):
        self.original = pixmap
        self.fit_image()

    def fit_image(self):
        if self.original is not None:
            self.setPixmap(self.original.scaled(self.width() - 8, self.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image()

    def clear(self):
        self.original = None
        super().clear()


class Chart(QWidget):
    """Charts use only the loaded report or current prediction."""
    def __init__(self, mode):
        super().__init__()
        self.mode, self.values = mode, None
        self.threshold = 6.0
        self.setMinimumSize(280 if mode == "prediction" else 220, 225 if mode == "prediction" else 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        p.setFont(QFont("Microsoft YaHei UI", 9))
        if self.values is None:
            p.setPen(QColor("#83909d"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "预测后显示模型结果" if self.mode == "prediction" else "加载模型后显示")
            return
        if self.mode == "prediction":
            self.paint_prediction(p)
            return
        if self.mode == "weights":
            left, right = 68, self.width() - 63
            available = max(30, right - left)
            for i, (name, value) in enumerate(zip(MODEL_NAMES, self.values)):
                y = 28 + i * 31
                p.setPen(QColor("#667481"))
                p.drawText(0, y + 4, name)
                p.fillRect(QRectF(left, y - 9, available, 12), QColor("#f0f3f5"))
                p.fillRect(QRectF(left, y - 9, max(1, value * available), 12), QColor(COLORS[i]))
                p.setPen(QColor("#344756"))
                p.drawText(right + 9, y + 4, f"{value:.1%}")
            return
        self.paint_metrics(p)

    def paint_metrics(self, p):
        values = [self.values[name]["R2"] for name in MODEL_NAMES]
        low = min(-.5, math.floor(min(values) * 2) / 2)
        high = max(1., math.ceil(max(values) * 2) / 2)
        left, right, top, bottom = 45., self.width() - 15., 30., self.height() - 32.
        y_of = lambda value: bottom - (value - low) / (high - low) * (bottom - top)
        p.setFont(QFont("Segoe UI", 9))
        for i in range(round((high - low) / .5) + 1):
            value = low + .5 * i
            y = y_of(value)
            p.setPen(QPen(QColor("#e8edf4"), 1))
            p.drawLine(int(left), int(y), int(right), int(y))
            p.setPen(QColor("#7e8b9c"))
            p.drawText(QRectF(0, y - 9, left - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{value:.1f}")
        stride = (right - left) / 4
        zero = y_of(0)
        best = max(range(4), key=lambda i: values[i])
        for i, (name, value) in enumerate(zip(MODEL_NAMES, values)):
            center = left + stride * (i + .5)
            y = y_of(value)
            width = min(95., stride * .55)
            p.fillRect(QRectF(center - width / 2, min(y, zero), width, max(2, abs(zero - y))),
                       QColor("#1977ed" if i == best else "#8aaee6"))
            p.setPen(QColor("#30465f"))
            label_y = y - 22 if value >= 0 else y + 2
            p.drawText(QRectF(center - stride / 2, label_y, stride, 21), Qt.AlignmentFlag.AlignCenter, f"{value:.4f}")
            p.drawText(QRectF(center - stride / 2, bottom + 7, stride, 24), Qt.AlignmentFlag.AlignCenter, name)
        p.setPen(QPen(QColor("#a7b4c6"), 1))
        p.drawLine(int(left), int(zero), int(right), int(zero))

    def paint_prediction(self, p):
        values = [self.values[name] for name in MODEL_NAMES]
        span = max(10.0, self.threshold, *values) - min(0.0, *values)
        rough = span / 5
        unit = 10 ** math.floor(math.log10(rough))
        step = next(x * unit for x in (1, 2, 5, 10) if x * unit >= rough)
        low = math.floor(min(0.0, *values) / step) * step
        high = math.ceil(max(10.0, self.threshold, *values) / step) * step
        left, right, top, bottom = 42.0, self.width() - 14.0, 48.0, self.height() - 34.0
        width, height = right - left, bottom - top
        y_of = lambda v: bottom - (v - low) / (high - low) * height
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.setPen(QColor("#536574"))
        p.drawText(2, 16, "四模型活性预测")
        p.drawText(QRectF(165, 0, self.width() - 170, 22), Qt.AlignmentFlag.AlignRight,
                   f"虚线：筛选门槛 {self.threshold:.2f}")
        p.setFont(QFont("Consolas", 10))
        p.drawText(2, 38, "pIC50")
        for i in range(round((high - low) / step) + 1):
            value = low + step * i
            y = y_of(value)
            p.setPen(QPen(QColor("#e8edf4"), 1))
            p.drawLine(int(left), int(y), int(right), int(y))
            p.setPen(QColor("#75869b"))
            p.drawText(QRectF(0, y - 9, left - 8, 18), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{value:g}")
        stride = width / len(MODEL_NAMES)
        bar_width = min(45.0, stride * .42)
        zero_y = y_of(0)
        for i, (name, value) in enumerate(zip(MODEL_NAMES, values)):
            x = left + stride * (i + .5)
            y = y_of(value)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(COLORS[i]))
            p.drawRoundedRect(QRectF(x - bar_width / 2, min(y, zero_y), bar_width, max(2, abs(zero_y - y))), 4, 4)
            p.setPen(QColor("#18304f"))
            p.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            value_y = max(top - 25, min(y - 25 if value >= 0 else y + 3, bottom - 24))
            if value < 0:
                p.fillRect(QRectF(x - 34, value_y, 68, 22), QColor("#ffffff"))
            p.drawText(QRectF(x - stride / 2, value_y, stride, 22), Qt.AlignmentFlag.AlignCenter, f"{value:.3f}")
            p.setFont(QFont("Microsoft YaHei UI", 10))
            p.drawText(QRectF(x - stride / 2, bottom + 9, stride, 22), Qt.AlignmentFlag.AlignCenter, name)
        p.setPen(QPen(QColor("#1977ed"), 1.5, Qt.PenStyle.DashLine))
        p.drawLine(int(left), int(y_of(self.threshold)), int(right), int(y_of(self.threshold)))


class MainWindow(QMainWindow):
    def __init__(self, root: Path):
        super().__init__()
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.worker = None
        self.job_kind = None
        self.busy = False
        self.predicting = False
        self.last_import_options = {}
        self.retry_data = None
        self.training_data = None
        self.data_preparation_failed = False
        self.export_feedback = {}
        self.bundle = None
        self.last_prediction = None
        self.last_result = None
        self.external_stages = None
        self.export_history = []
        self.export_sections = {}
        self.export_formats = {}
        self.export_notes = {}
        self.setWindowTitle(APP_NAME)
        self.logo_path = asset_location("logo.png")
        self.setWindowIcon(QIcon(str(self.logo_path)))
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1480, available.width() - 16), min(940, available.height() - 40))
        self.setMinimumSize(880, 460)
        self.pred_export_buttons = []
        self.setFont(workbench_font())
        self.setStyleSheet(STYLE)
        base = QWidget()
        base.setObjectName("base")
        self.setCentralWidget(base)
        outer = QVBoxLayout(base)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 9, 24, 9)
        logo = QLabel()
        logo.setObjectName("logo")
        logo.setToolTip(APP_NAME)
        logo.setPixmap(QPixmap(str(self.logo_path)).scaled(29, 29, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header_layout.addWidget(logo)
        brand = label(APP_NAME, "brand")
        brand.setWordWrap(False)
        header_layout.addWidget(brand)
        target_label = label("  |  ERα / ESR1 固定靶点", "muted")
        target_label.setWordWrap(False)
        header_layout.addWidget(target_label)
        header_layout.addStretch()
        header_layout.addWidget(label("v" + __version__, "muted"))
        outer.addWidget(header)
        navigation = QFrame()
        navigation.setObjectName("navigation")
        nav = QHBoxLayout(navigation)
        nav.setContentsMargins(16, 0, 16, 0)
        nav.setSpacing(0)
        self.nav_buttons = []
        self.page_names = ("数据导入与清洗", "模型训练", "融合优化", "分子预测", "三级漏斗筛选", "结果与导出")
        for text, icon in zip(self.page_names, ("data", "train", "fusion", "molecule", "filter", "report")):
            b = icon_button(button(text, lambda checked=False, name=text: self.navigate(name)), icon)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            nav.addWidget(b, 1)
            self.nav_buttons.append(b)
        outer.addWidget(navigation)
        self.pages = QStackedWidget()
        outer.addWidget(self.pages, 1)
        for factory in (self.data_page, self.training_page, self.fusion_page, self.prediction_page, self.screening_page, self.results_page):
            self.pages.addWidget(factory())
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        self.progress.hide()
        outer.addWidget(self.progress)
        self.smiles.textChanged.connect(self.invalidate_input)
        self.statusBar().showMessage("准备就绪 · 科研初筛，预测结果需实验验证")
        self.refresh_data()
        try:
            self.set_bundle(model_location(root))
        except Exception as error:
            self.model_label.setText(str(error))
            self.append_log("当前模型未加载：" + str(error))
        self.load_export_history()
        self.navigate("数据导入与清洗")
        self.restore_rules(initial=True)
        self.refresh_actions()
        self.adapt_prediction_layout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.adapt_prediction_layout()

    def adapt_prediction_layout(self):
        if hasattr(self, "activity_summary_layout"):
            direction = QBoxLayout.Direction.LeftToRight if self.width() >= 1100 else QBoxLayout.Direction.TopToBottom
            if self.activity_summary_layout.direction() != direction:
                self.activity_summary_layout.setDirection(direction)

    def navigate(self, name, report_tab=0):
        index = self.page_names.index(name)
        self.pages.setCurrentIndex(index)
        if name == "结果与导出":
            self.report_tabs.setCurrentIndex(report_tab)
        target = self.pages.widget(index)
        target.verticalScrollBar().setValue(0)
        QTimer.singleShot(0, lambda: target.verticalScrollBar().setValue(0) if self.pages.currentWidget() is target else None)
        for b in self.nav_buttons:
            b.setChecked(b.text() == name)

    def page_heading(self, layout, number, title, description):
        layout.setSpacing(14)
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(description, "muted"))

    def metric_strip(self, layout, captions):
        row = QHBoxLayout()
        row.setSpacing(24)
        values = []
        for caption in captions:
            column = QVBoxLayout()
            column.setSpacing(3)
            column.addWidget(label(caption, "muted"))
            value = label("—", "stat")
            column.addWidget(value)
            row.addLayout(column, 1)
            values.append(value)
        layout.addLayout(row)
        return values

    def data_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 1, "数据导入与清洗", "准备人类 ERα / ESR1 结合活性数据，统一测定单位与化合物结构。")
        self.data_notice = label("请选择数据来源；已有模型可直接用于分子预测。", "notice")
        layout.addWidget(self.data_notice)
        self.retry_data_button = button("重试上次数据操作", self.retry_last_data)
        self.retry_data_button.hide()
        layout.addWidget(self.retry_data_button)
        sources = QHBoxLayout()
        sources.setSpacing(16)
        csv_box, csv_layout = group("导入实验 CSV")
        self.csv_drop = CsvDropZone()
        self.import_button = self.csv_drop.findChildren(QPushButton)[0]
        self.csv_drop.chooseRequested.connect(self.import_data)
        self.csv_drop.fileDropped.connect(self.import_data)
        csv_layout.addWidget(self.csv_drop)
        csv_layout.addWidget(label("必填字段：SMILES、IC50、单位。选择文件后可映射列名，并填写数据来源。", "muted"))
        template_row = QHBoxLayout()
        self.template_button = icon_button(button("下载 CSV 模板", self.download_csv_template), "download")
        self.template_button.setToolTip("模板只含表头；请填写真实的 SMILES、IC50、单位和精确关系。来源在导入时填写。")
        template_row.addWidget(self.template_button)
        template_row.addStretch()
        csv_layout.addLayout(template_row)
        sources.addWidget(csv_box, 1)
        chembl_box, chembl_layout = group("获取 ChEMBL 数据")
        chembl_layout.addWidget(label("获取固定靶点 CHEMBL206 的人类结合活性记录。", "section"))
        chembl_layout.addWidget(label("“获取”优先复用已有快照；“更新”先备份原始快照，再获取新记录并替换待训练数据。已加载模型保留，当前分子报告失效。", "muted"))
        chembl_layout.addStretch()
        actions = QHBoxLayout()
        self.download_button = icon_button(button("获取 ChEMBL 数据", self.download_data, True), "download", True)
        self.refresh_button = icon_button(button("更新数据快照", lambda: self.download_data(refresh=True)), "refresh")
        actions.addWidget(self.download_button)
        actions.addWidget(self.refresh_button)
        chembl_layout.addLayout(actions)
        chembl_layout.addStretch()
        sources.addWidget(chembl_box, 1)
        layout.addLayout(sources)
        self.import_info_details = Disclosure("已选文件、字段映射与来源")
        self.import_context = QPlainTextEdit()
        self.import_context.setReadOnly(True)
        self.import_context.setMaximumHeight(115)
        self.import_info_details.content_layout.addWidget(self.import_context)
        self.import_info_details.hide()
        layout.addWidget(self.import_info_details)
        process_box, process_layout = group("清洗流程")
        steps = QHBoxLayout()
        self.cleaning_steps = []
        self.cleaning_step_names = ("精确正值 IC50", "单位换算", "结构标准化", "去重", "冲突排除")
        for i, text in enumerate(self.cleaning_step_names, 1):
            step = label(f"{i:02d} {text}\n未开始", "step")
            self.cleaning_steps.append(step)
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            steps.addWidget(step, 1)
            if i < 5:
                steps.addWidget(label("→", "muted"))
        process_layout.addLayout(steps)
        layout.addWidget(process_box)
        preview_box, preview = group("数据预览")
        self.data_label = label("尚未导入训练数据", "section")
        preview.addWidget(self.data_label)
        self.data_empty_hint = label("导入后在这里查看清洗摘要、数据预览与排除原因。", "muted")
        preview.addWidget(self.data_empty_hint)
        self.data_summary_tabs = ContentTabs()
        cleaned = QWidget()
        cleaned_layout = QVBoxLayout(cleaned)
        cleaned_layout.setContentsMargins(0, 10, 0, 0)
        self.data_audit_summary = label("", "muted")
        cleaned_layout.addWidget(self.data_audit_summary)
        self.sample_table = table(["标准化 SMILES", "pIC50", "测定条数", "化合物 ID"], 260)
        self.sample_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col, width in ((1, 90), (2, 90), (3, 185)):
            self.sample_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.sample_table.setColumnWidth(col, width)
        cleaned_layout.addWidget(self.sample_table)
        self.data_summary_tabs.addTab(cleaned, "清洗摘要")
        rejected = QWidget()
        rejected_layout = QVBoxLayout(rejected)
        rejected_layout.setContentsMargins(0, 10, 0, 0)
        self.rejection_table = table(["排除原因", "记录数"], 260)
        rejected_layout.addWidget(self.rejection_table)
        self.rejection_hint = label("无排除记录。", "muted")
        rejected_layout.addWidget(self.rejection_hint)
        self.data_summary_tabs.addTab(rejected, "排除原因")
        preview.addWidget(self.data_summary_tabs)
        self.data_summary_tabs.hide()
        self.audit_details = Disclosure("高级详情 · 清洗记录与数据来源")
        self.audit_view = QPlainTextEdit()
        self.audit_view.setReadOnly(True)
        self.audit_view.setMaximumHeight(210)
        self.audit_details.content_layout.addWidget(self.audit_view)
        self.audit_details.hide()
        preview.addWidget(self.audit_details)
        layout.addWidget(preview_box)
        footer = QHBoxLayout()
        self.data_predict_link = icon_button(button("使用内置模型进行预测", lambda: self.navigate("分子预测")), "molecule")
        footer.addWidget(self.data_predict_link)
        self.data_next_hint = label("请先获取或导入可训练数据。", "muted")
        footer.addWidget(self.data_next_hint, 1)
        self.next_training_button = icon_button(button("下一步：模型训练", lambda: self.navigate("模型训练"), True), "next", True)
        self.next_training_button.setEnabled(False)
        footer.addWidget(self.next_training_button)
        page.set_footer(footer)
        layout.addStretch(1)
        return page

    def training_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 2, "模型训练", "左侧设置下一次训练，右侧查看当前已加载模型的历史记录。")
        columns = QHBoxLayout()
        columns.setSpacing(16)
        setup_box, setup = group("本次待训练数据与设置")
        setup_box.setMinimumWidth(260)
        setup_box.setMaximumWidth(330)
        self.pending_count = label("尚未导入待训练数据", "section")
        setup.addWidget(self.pending_count)
        self.training_data_hint = label("请先导入训练数据；内置模型仍可直接预测。", "muted")
        setup.addWidget(self.training_data_hint)
        setup.addWidget(button("前往数据导入", lambda: self.navigate("数据导入与清洗")))
        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.addRow("下一次划分", label("结构分组划分"))
        self.training_seed = QSpinBox()
        self.training_seed.setRange(0, 2147483646)
        self.training_seed.setValue(42)
        self.training_seed.valueChanged.connect(self.training_settings_changed)
        form.addRow("下一次随机种子", self.training_seed)
        setup.addLayout(form)
        self.training_settings_note = label("修改设置不会重新计算右侧历史指标；点击“开始训练”才会运行。", "muted")
        setup.addWidget(self.training_settings_note)
        setup.addWidget(label("固定训练四个模型", "sectionTitle"))
        for name, chinese in zip(MODEL_NAMES, ("人工神经网络", "随机森林", "梯度提升树", "线性回归")):
            setup.addWidget(label(f"{name}  ·  {chinese}"))
        self.training_advanced = Disclosure("训练方法与参数")
        self.training_advanced.content_layout.addWidget(label("Morgan 半径2 / 1024位指纹 + 8项描述符；按结构分组划分。模型参数保留在运行详情中。"))
        setup.addWidget(self.training_advanced)
        train_actions = QHBoxLayout()
        self.train_button = icon_button(button("开始训练", self.start_training, True), "play", True)
        self.train_reset_button = button("重置设置", self.reset_training_controls)
        self.train_reset_button.setToolTip("只恢复下一次训练的随机种子和折叠状态，保留已有模型、历史指标及数据。")
        train_actions.addWidget(self.train_button, 2)
        train_actions.addWidget(self.train_reset_button, 1)
        setup.addLayout(train_actions)
        self.load_model_button = icon_button(button("加载已有模型", self.choose_model), "folder")
        setup.addWidget(self.load_model_button)
        setup.addStretch()
        columns.addWidget(setup_box, 1)
        right = QVBoxLayout()
        right.setSpacing(16)
        self.training_notice = label("尚无历史训练记录。可加载内置模型或完成数据准备后开始训练。", "notice")
        right.addWidget(self.training_notice)
        self.model_label = label("当前未加载模型。", "muted")
        right.addWidget(self.model_label)
        self.training_content = QWidget()
        content = QVBoxLayout(self.training_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)
        history_box, history = group("当前模型 · 历史数据划分")
        self.training_count = label("—", "muted")
        history.addWidget(self.training_count)
        self.split_labels = self.metric_strip(history, ("历史训练集", "历史验证集", "历史测试集"))
        content.addWidget(history_box)
        metrics_box, metrics = group("历史模型评估 · 独立测试集")
        self.model_table = table(["模型", "测试 R²", "RMSE", "MAE", "说明"], 250)
        metrics.addWidget(self.model_table)
        content.addWidget(metrics_box)
        chart_box, chart_layout = group("单模型历史测试 R² 对比")
        self.metric_chart = Chart("metrics")
        self.metric_chart.setMinimumHeight(170)
        self.metric_chart.setMaximumHeight(190)
        chart_layout.addWidget(self.metric_chart)
        content.addWidget(chart_box)
        content.addWidget(label("负 R² 如实展示。当前数据下的单模型比较不代表所有指标或其他数据集的最优表现。", "muted"))
        self.training_content.hide()
        right.addWidget(self.training_content)
        self.log_details = Disclosure("运行日志")
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(180)
        self.log_details.content_layout.addWidget(self.log_view)
        right.addWidget(self.log_details)
        right.addStretch()
        columns.addLayout(right, 3)
        layout.addLayout(columns)
        actions = QHBoxLayout()
        actions.addWidget(label("右侧指标对应当前已加载模型；下一次训练设置在左侧。", "muted"), 1)
        actions.addWidget(icon_button(button("查看训练报告", lambda: self.navigate("结果与导出", 1)), "report"))
        actions.addWidget(icon_button(button("前往融合优化", lambda: self.navigate("融合优化"), True), "next", True))
        page.set_footer(actions)
        layout.addStretch()
        return page

    def training_settings_changed(self, *_):
        self.training_settings_note.setText(f"下一次训练种子：{self.training_seed.value()}。右侧历史指标和已加载模型保持原记录。")

    def reset_training_controls(self):
        self.training_seed.setValue(42)
        self.training_advanced.set_expanded(False)
        self.statusBar().showMessage("训练设置已恢复；已加载的模型和历史记录保留")

    def fusion_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 3, "融合优化", "比较优化器的验证表现，查看已冻结的四模型融合权重。")
        self.fusion_version = label("尚无融合方案。请先训练或加载模型。", "muted")
        layout.addWidget(self.fusion_version)
        self.fusion_load_button = button("前往训练或加载模型", lambda: self.navigate("模型训练"))
        self.fusion_load_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.fusion_load_button)
        self.fusion_content = QWidget()
        content = QVBoxLayout(self.fusion_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(16)
        summary_box = QFrame()
        summary_box.setObjectName("sectionPanel")
        summary = QVBoxLayout(summary_box)
        summary.setContentsMargins(16, 12, 16, 12)
        self.fusion_metrics = self.metric_strip(summary, ("已选优化器", "验证集 RMSE"))
        content.addWidget(summary_box)
        comparison_box, comparison = group("优化器对比 · 同一验证集")
        self.fusion_table = table(["优化器", "ANN 权重", "RF 权重", "XGBoost 权重", "LR 权重", "验证 RMSE"], 190)
        comparison.addWidget(self.fusion_table)
        comparison.addWidget(label("按未四舍五入的验证集指标选择方案（实际比较 MSE）；完全相等时按 GA → SA → TS 顺序选择。悬浮表格可查看完整精度。", "muted"))
        content.addWidget(comparison_box)
        row = QHBoxLayout()
        row.setSpacing(18)
        box, weights = group("选定方案 · 模型权重")
        self.weights_chart = Chart("weights")
        self.weights_chart.setMaximumHeight(190)
        weights.addWidget(self.weights_chart)
        row.addWidget(box, 6)
        final_box, final_layout = group("独立测试结果")
        self.test_metric_labels = []
        for caption in ("R²", "RMSE", "MAE"):
            metric_row = QHBoxLayout()
            metric_row.addWidget(label(caption, "muted"))
            metric_row.addStretch()
            value = label("—", "stat")
            metric_row.addWidget(value)
            self.test_metric_labels.append(value)
            final_layout.addLayout(metric_row)
        self.test_label = label("方案在验证集冻结，独立测试评估一次。", "muted")
        final_layout.addWidget(self.test_label)
        row.addWidget(final_box, 5)
        content.addLayout(row)
        self.fusion_content.hide()
        layout.addWidget(self.fusion_content)
        self.fusion_precision_details = Disclosure("运行详情与完整精度")
        self.fusion_precision_view = QPlainTextEdit()
        self.fusion_precision_view.setReadOnly(True)
        self.fusion_precision_view.setMaximumHeight(150)
        self.fusion_precision_details.content_layout.addWidget(self.fusion_precision_view)
        self.fusion_precision_details.content_layout.addWidget(button("复制完整精度", self.copy_fusion_precision))
        self.fusion_precision_details.hide()
        layout.addWidget(self.fusion_precision_details)
        footer = QHBoxLayout()
        note = label("模型融合权重与三级筛选阶段权重是不同参数。", "muted")
        footer.addWidget(note, 1)
        footer.addWidget(icon_button(button("使用该模型预测", lambda: self.navigate("分子预测"), True), "molecule", True))
        footer.addWidget(button("查看训练报告", lambda: self.navigate("结果与导出", 1)))
        page.set_footer(footer)
        layout.addStretch()
        return page

    def prediction_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 4, "分子预测", "输入 SMILES，查看模型活性预测与筛选状态。")
        input_box = QFrame()
        input_box.setObjectName("sectionPanel")
        form = QVBoxLayout(input_box)
        form.setContentsMargins(16, 14, 16, 14)
        controls = QHBoxLayout()
        controls.addWidget(label("SMILES", "section"))
        self.smiles = QLineEdit()
        self.smiles.setObjectName("smilesInput")
        self.smiles.setPlaceholderText("输入 SMILES，例如 CCO")
        self.smiles.setAccessibleName("化合物SMILES")
        self.smiles.returnPressed.connect(self.run_prediction)
        controls.addWidget(self.smiles, 1)
        self.predict_button = icon_button(button("预测活性", self.run_prediction, True), "play", True)
        controls.addWidget(self.predict_button)
        controls.addWidget(icon_button(button("载入示例", lambda: self.smiles.setText("C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")), "folder"))
        controls.addWidget(button("清空", self.clear_prediction))
        form.addLayout(controls)
        self.predict_input_error = label("", "error")
        self.predict_input_error.hide()
        form.addWidget(self.predict_input_error)
        layout.addWidget(input_box)
        self.conclusion = label("等待预测 · 输入 SMILES 后点击“预测活性”。", "notice")
        layout.addWidget(self.conclusion)
        self.prediction_empty_hint = label("“载入示例”仅填入示例结构；点击预测后由当前模型计算结果。", "muted")
        layout.addWidget(self.prediction_empty_hint)
        self.prediction_empty_panel = QWidget()
        placeholder_row = QHBoxLayout(self.prediction_empty_panel)
        placeholder_row.setContentsMargins(0, 0, 0, 0)
        placeholder_row.setSpacing(16)
        for title, text in (
            ("分子结构预览", "完成预测后显示二维分子结构、分子式和理化描述符。"),
            ("预测结果", "完成预测后显示融合 pIC50、四模型结果及三个阶段的状态。"),
        ):
            box, body = group(title)
            body.addWidget(label(text, "emptyCaption"))
            box.setMaximumHeight(140)
            placeholder_row.addWidget(box, 1)
        layout.addWidget(self.prediction_empty_panel)
        self.prediction_content = QWidget()
        result_layout = QVBoxLayout(self.prediction_content)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(14)
        hero = QHBoxLayout()
        hero.setSpacing(16)
        molecule_box, ml = group("分子结构")
        self.molecule_image = MoleculeView()
        self.molecule_image.setMaximumHeight(250)
        ml.addWidget(self.molecule_image, 1)
        self.properties_label = label("分子式、MW、LogP、TPSA将在预测后显示。", "muted")
        ml.addWidget(self.properties_label)
        hero.addWidget(molecule_box, 10)
        activity_box, al = group("预测结果")
        summary = QHBoxLayout()
        self.activity_summary_layout = summary
        for caption in ("融合 pIC50", "活性门槛"):
            col = QVBoxLayout()
            if caption.startswith("融合"):
                self.pic50_caption = label(caption, "metric")
                self.pic50_caption.setToolTip("pIC50 = −log10(IC50 [mol/L])")
                col.addWidget(self.pic50_caption)
                self.activity_label = label("—", "number")
                col.addWidget(self.activity_label)
            else:
                col.addWidget(label(caption, "metric"))
                self.activity_threshold_label = label("6.00", "number")
                col.addWidget(self.activity_threshold_label)
            summary.addLayout(col, 1)
        al.addStretch()
        al.addLayout(summary)
        self.activity_status = label("尚未评估", "statusTag")
        self.activity_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        al.addWidget(self.activity_status)
        al.addWidget(label("数值用于科研初筛；活性低于门槛时不能由后续阶段加分放行。", "muted"))
        al.addStretch()
        hero.addWidget(activity_box, 11)
        models_box, models = group("四模型预测结果")
        self.prediction_table = table(["模型", "pIC50", "权重"], 240)
        models.addWidget(self.prediction_table)
        models.addWidget(label("权重来自已冻结的融合方案。", "muted"))
        models.addWidget(button("查看融合方案", lambda: self.navigate("融合优化")))
        models.addStretch()
        hero.addWidget(models_box, 11)
        result_layout.addLayout(hero)
        stages_box, stages = group("阶段评估")
        self.stage_status_labels, self.stage_reason_labels = [], []
        for number, name in enumerate(("活性", "ADMET", "结构 / 理化"), 1):
            row = QHBoxLayout()
            badge = label(f"{number:02d}", "stageNumber")
            badge.setFixedSize(30, 30)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(badge)
            name_label = label(name, "section")
            name_label.setFixedWidth(112)
            row.addWidget(name_label)
            status = label("未评估", "statusTag")
            row.addWidget(status)
            reason = label("等待活性预测。" if number == 1 else "等待外部证据。", "muted")
            row.addWidget(reason, 1)
            stages.addLayout(row)
            self.stage_status_labels.append(status)
            self.stage_reason_labels.append(reason)
        result_layout.addWidget(stages_box)
        self.score_label = label("完整综合分未计算：阶段数据尚未齐全。", "muted")
        result_layout.addWidget(self.score_label)
        layout.addWidget(self.prediction_content)
        self.prediction_content.hide()
        self.model_details = Disclosure("图表对比与模型说明")
        self.activity_chart = Chart("prediction")
        self.activity_chart.setMinimumHeight(240)
        self.activity_chart.setMaximumHeight(310)
        self.model_details.content_layout.addWidget(self.activity_chart)
        self.model_details.content_layout.addWidget(label("虚线为当前活性门槛；四模型融合权重与三级筛选阶段权重分别配置。", "muted"))
        layout.addWidget(self.model_details)
        self.model_details.hide()
        footer = QHBoxLayout()
        footer.addWidget(icon_button(button("筛选参数与阶段证据", lambda: self.navigate("三级漏斗筛选")), "settings"))
        footer.addStretch()
        self.export_menu_button = icon_button(button("导出结果", lambda: None), "download")
        self.export_menu = QMenu(self.export_menu_button)
        for kind, caption, attribute in (
            ("html", "HTML 可读报告", "export_html_button"),
            ("csv", "CSV 结果表", "export_csv_button"),
            ("json", "JSON 完整记录", "export_json_button"),
        ):
            action = self.export_menu.addAction(caption)
            action.triggered.connect(lambda checked=False, k=kind: self.export_prediction(k))
            action.setEnabled(False)
            setattr(self, attribute, action)
            self.pred_export_buttons.append(action)
        self.export_menu_button.setMenu(self.export_menu)
        self.export_menu_button.setEnabled(False)
        self.pred_export_buttons.append(self.export_menu_button)
        footer.addWidget(self.export_menu_button)
        self.view_report_button = icon_button(button("查看报告", lambda: self.navigate("结果与导出"), True), "report", True)
        self.view_report_button.setToolTip("完成有效预测后可查看报告。")
        self.view_report_button.setEnabled(False)
        self.pred_export_buttons.append(self.view_report_button)
        footer.addWidget(self.view_report_button)
        page.set_footer(footer)
        layout.addWidget(label("阶段2/3依赖外部证据，未内置 ADMET 或67项结构约束预测模型。", "muted"))
        layout.addStretch()
        return page

    def screening_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 5, "三级漏斗筛选", "依次核对活性、ADMET 及结构 / 理化证据。")
        toolbar = QHBoxLayout()
        toolbar.addWidget(icon_button(button("返回分子预测", lambda: self.navigate("分子预测")), "back"))
        self.import_evidence_button = icon_button(button("导入阶段证据", self.load_stage_evidence), "upload")
        self.clear_evidence_button = icon_button(button("清除阶段证据", self.clear_stages), "trash")
        toolbar.addWidget(self.import_evidence_button)
        toolbar.addWidget(self.clear_evidence_button)
        toolbar.addStretch()
        self.funnel_report_button = icon_button(button("查看筛选报告", lambda: self.navigate("结果与导出")), "report")
        self.funnel_report_button.setEnabled(False)
        toolbar.addWidget(self.funnel_report_button)
        layout.addLayout(toolbar)
        self.funnel_context = label("等待预测 · 请先输入 SMILES 并完成分子预测。", "notice")
        layout.addWidget(self.funnel_context)
        self.funnel_predict_link = icon_button(button("前往分子预测", lambda: self.navigate("分子预测"), True), "next", True)
        self.funnel_predict_link.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.funnel_predict_link)
        self.import_evidence_button.setToolTip("先完成当前分子的有效预测；证据需包含相同的标准化SMILES和可追溯来源。")
        self.clear_evidence_button.setToolTip("移除当前阶段2/3证据并退出演示，旧报告失效，重新预测后更新；不删除模型或已导出的文件。")
        self.funnel_molecule = QLineEdit("当前分子：尚未选择")
        self.funnel_molecule.setReadOnly(True)
        self.funnel_molecule.setAccessibleName("当前分子标准化 SMILES（可复制）")
        layout.addWidget(self.funnel_molecule)
        self.funnel_score = label("综合评分尚未完成：等待分子预测与阶段证据。", "section")
        layout.addWidget(self.funnel_score)
        self.screen_stage_views = []
        for number, name in enumerate(("活性", "ADMET", "结构 / 理化"), 1):
            box = QFrame()
            box.setObjectName("sectionPanel")
            row = QHBoxLayout(box)
            row.setContentsMargins(16, 16, 16, 16)
            row.setSpacing(16)
            stage_name = QVBoxLayout()
            title = QHBoxLayout()
            badge = label(f"{number:02d}", "stageNumber")
            badge.setFixedSize(32, 32)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.addWidget(badge)
            title.addWidget(label(name, "section"))
            stage_name.addLayout(title)
            flow = label("等待输入", "muted")
            stage_name.addWidget(flow)
            row.addLayout(stage_name, 3)
            fields = []
            for caption, placeholder in zip(("输入与来源", "判定条件", "输出与原因"),
                    ("等待分子预测结果" if number == 1 else "尚未提供外部证据" if number == 2 else "尚未提供结构判定证据",
                     "pIC50 ≥ 6.00（硬底线6.0）" if number == 1 else "按完整5项 ADMET 证据与阈值核验" if number == 2 else "完整67项约束定义及对应布尔判定",
                     "等待有效输入" if number == 1 else "缺少证据，暂不评估")):
                col = QVBoxLayout()
                col.addWidget(label(caption, "muted"))
                detail = label(placeholder)
                col.addWidget(detail)
                col.addStretch()
                row.addLayout(col, 4 if caption == "输出与原因" else 3)
                fields.append(detail)
            status = label("○ 未开始" if number == 1 else "○ 缺少证据 · 未评估", "statusTag")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(status, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(box)
            self.screen_stage_views.append((status, flow, fields))
        self.rules_details = Disclosure("高级筛选参数 · 门槛、阶段权重、奖励与惩罚")
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
            spin.valueChanged.connect(self.rules_changed)
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
            spin.valueChanged.connect(self.rules_changed)
            self.parameters[key] = spin
            thresholds.addWidget(spin)
        cl.addLayout(thresholds)
        cfg_buttons = QHBoxLayout()
        cfg_buttons.addWidget(button("保存参数快照", self.save_rules))
        cfg_buttons.addWidget(button("恢复默认参数", self.restore_defaults))
        cfg_buttons.addWidget(button("导入外部阶段证据 JSON", self.load_stage_evidence))
        cfg_buttons.addWidget(button("清除阶段2/3输入", self.clear_stages))
        cl.addLayout(cfg_buttons)
        self.rules_details.content_layout.addWidget(config_box)
        layout.addWidget(self.rules_details)
        self.demo_details = Disclosure("外部证据与流程演示 · 演示结果不作为科研结论")
        demo_box, dl = group("阶段2 / 3流程输入")
        self.use_demo = QCheckBox("启用流程演示数据（不作为模型预测结果）")
        self.use_demo.toggled.connect(self.demo_changed)
        dl.addWidget(self.use_demo)
        demo_row = QGridLayout()
        demo_row.setHorizontalSpacing(18)
        self.demo_fields = {}
        for col, (key, caption, value, low, high) in enumerate((("logS", "logS", -2, -20, 10),
                ("F_percent", "F%", 50, 0, 100), ("PPB_percent", "PPB%", 90, 0, 100))):
            field = QHBoxLayout()
            field.addWidget(label(caption))
            spin = QDoubleSpinBox()
            spin.setRange(low, high)
            spin.setValue(value)
            spin.setEnabled(False)
            spin.valueChanged.connect(self.rules_changed)
            self.demo_fields[key] = spin
            field.addWidget(spin)
            demo_row.addLayout(field, 0, col)
        for col, (key, caption) in enumerate((("hepatotoxic", "肝毒性风险"), ("CYP3A4_inhibitor", "CYP3A4高抑制风险"))):
            check = QCheckBox(caption)
            check.setEnabled(False)
            check.toggled.connect(self.rules_changed)
            self.demo_fields[key] = check
            demo_row.addWidget(check, 1, col)
        count_row = QHBoxLayout()
        count_row.addWidget(label("演示满足数/67"))
        self.demo_count = QSpinBox()
        self.demo_count.setRange(0, 67)
        self.demo_count.setValue(56)
        self.demo_count.setEnabled(False)
        self.demo_count.valueChanged.connect(self.rules_changed)
        count_row.addWidget(self.demo_count)
        demo_row.addLayout(count_row, 1, 2)
        dl.addLayout(demo_row)
        dl.addWidget(label("演示计数仅用于展示流程。完整结构评估需提供67项约束定义及对应判定。", "muted"))
        self.demo_details.content_layout.addWidget(demo_box)
        self.demo_details.content_layout.addWidget(label(SCOPE_TEXT, "muted"))
        layout.addWidget(self.demo_details)
        self.funnel_details = Disclosure("三级漏斗详情 · 输入 → 判定 → 输出 → 流转")
        self.funnel_table = table(STAGE_HEADERS, 230, wrap=True)
        self.funnel_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for i, width in enumerate((110, 85, 220, 220, 130, 260, 85)):
            self.funnel_table.setColumnWidth(i, width)
        self.funnel_details.content_layout.addWidget(self.funnel_table)
        layout.addWidget(self.funnel_details)
        layout.addStretch(1)
        return page

    def results_page(self):
        page, layout = scrollable()
        self.page_heading(layout, 6, "结果与导出", "先核对报告摘要，再选择需要导出的内容与格式。")
        self.report_tabs = ContentTabs()
        layout.addWidget(self.report_tabs)
        molecular = QWidget()
        ml = QVBoxLayout(molecular)
        ml.setContentsMargins(0, 12, 0, 0)
        columns = QHBoxLayout()
        columns.setSpacing(18)
        preview_box, preview = group("筛选报告预览")
        self.screening_summary = label("尚未生成筛选报告", "section")
        preview.addWidget(self.screening_summary)
        self.screening_meta = label("完成分子预测后，在这里汇总分子信息、活性结果及三级筛选证据。", "muted")
        preview.addWidget(self.screening_meta)
        self.report_predict_link = icon_button(button("前往分子预测", lambda: self.navigate("分子预测"), True), "molecule", True)
        self.report_predict_link.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.report_empty_panel = QWidget()
        empty = QVBoxLayout(self.report_empty_panel)
        empty.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(line_icon("report", "#8190a2").pixmap(28, 28))
        empty.addWidget(icon, 0, Qt.AlignmentFlag.AlignCenter)
        self.report_empty_heading = label("尚未生成筛选报告", "section")
        self.report_empty_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.report_empty_heading.setWordWrap(False)
        empty.addWidget(self.report_empty_heading)
        empty_hint = label("完成有效预测后，可查看以下内容：", "muted")
        empty_hint.setWordWrap(False)
        empty.addWidget(empty_hint, 0, Qt.AlignmentFlag.AlignCenter)
        for caption in ("分子信息", "活性预测", "筛选证据", "参数与来源"):
            item = label("○  " + caption + " · 待生成", "muted")
            item.setWordWrap(False)
            empty.addWidget(item, 0, Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(self.report_predict_link, 0, Qt.AlignmentFlag.AlignCenter)
        preview.addWidget(self.report_empty_panel)
        self.screening_summary.hide()
        self.screening_meta.hide()
        self.pred_report_body = QWidget()
        rb = QVBoxLayout(self.pred_report_body)
        rb.setContentsMargins(0, 0, 0, 0)
        rb.setSpacing(12)
        self.report_molecule = MoleculeView()
        self.report_molecule.setMinimumHeight(110)
        self.report_molecule.setMaximumHeight(150)
        rb.addWidget(self.report_molecule)
        self.report_stage_table = table(["阶段", "状态", "原因", "流转"], 225, wrap=True)
        for col in (0, 1, 3):
            self.report_stage_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.report_stage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        rb.addWidget(self.report_stage_table)
        self.report_prediction_table = table(["模型", "预测 pIC50", "融合权重"], 215)
        rb.addWidget(self.report_prediction_table)
        self.report_parameter_text = label("", "muted")
        rb.addWidget(self.report_parameter_text)
        self.export_format_title = label("导出说明", "section")
        rb.addWidget(self.export_format_title)
        rb.addWidget(label("HTML：可阅读和打印的报告，内嵌分子图。CSV：单个分子一行的结果表。JSON：结构化数据。导出内容以右侧勾选项为准；模型版本、结论及功能范围始终保留。", "muted"))
        self.prediction_raw_details = Disclosure("高级详情 · 分子筛选原始 JSON")
        self.prediction_report_raw = QPlainTextEdit()
        self.prediction_report_raw.setReadOnly(True)
        self.prediction_report_raw.setMinimumHeight(220)
        self.prediction_raw_details.content_layout.addWidget(self.prediction_report_raw)
        rb.addWidget(self.prediction_raw_details)
        rb.addWidget(label(SCOPE_TEXT, "muted"))
        preview.addWidget(self.pred_report_body)
        self.pred_report_body.hide()
        self.screening_preview_box = preview_box
        columns.addWidget(preview_box, 7, Qt.AlignmentFlag.AlignTop)
        columns.addWidget(self.export_panel("prediction"), 3)
        ml.addLayout(columns)
        self.report_tabs.addTab(molecular, "分子筛选报告")
        training = QWidget()
        tl = QVBoxLayout(training)
        tl.setContentsMargins(0, 12, 0, 0)
        training_columns = QHBoxLayout()
        training_columns.setSpacing(18)
        train_box, train_preview = group("训练评估报告预览")
        self.training_report_summary = label("尚无训练报告", "section")
        train_preview.addWidget(self.training_report_summary)
        self.training_report_meta = label("请训练或加载模型；训练报告与单个分子的筛选报告分别记录。", "muted")
        train_preview.addWidget(self.training_report_meta)
        self.training_report_body = QWidget()
        tb = QVBoxLayout(self.training_report_body)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(12)
        self.training_report_table = table(["模型 / 方案", "测试 R²", "测试 RMSE", "测试 MAE"], 290)
        tb.addWidget(self.training_report_table)
        self.training_comparison_note = label("", "notice")
        tb.addWidget(self.training_comparison_note)
        self.training_report_weight_title = label("融合权重", "section")
        tb.addWidget(self.training_report_weight_title)
        self.training_report_weights = Chart("weights")
        self.training_report_weights.setMinimumHeight(155)
        self.training_report_weights.setMaximumHeight(165)
        tb.addWidget(self.training_report_weights)
        self.training_report_data = label("", "muted")
        tb.addWidget(self.training_report_data)
        self.training_report_run = label("", "muted")
        raw = Disclosure("运行详情 · 标识、来源与原始 JSON")
        self.training_run_details = raw
        raw.content_layout.addWidget(self.training_report_run)
        copy_row = QHBoxLayout()
        copy_row.addWidget(button("复制运行 ID", lambda: self.copy_run_info("run_id")))
        copy_row.addWidget(button("复制 SHA256", lambda: self.copy_run_info("data_sha256")))
        copy_row.addWidget(button("复制完整记录 JSON", lambda: self.copy_run_info("json")))
        copy_row.addStretch()
        raw.content_layout.addLayout(copy_row)
        self.report_view = QPlainTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setMinimumHeight(230)
        raw.content_layout.addWidget(self.report_view)
        tb.addWidget(raw)
        tb.addWidget(label("验证集用于选择融合方案，独立测试只在方案冻结后评估一次。指标不代表临床效果。", "muted"))
        train_preview.addWidget(self.training_report_body)
        self.training_report_body.hide()
        training_columns.addWidget(train_box, 7)
        training_columns.addWidget(self.export_panel("training"), 3)
        tl.addLayout(training_columns)
        self.report_tabs.addTab(training, "模型训练报告")
        history_box, history = group("导出历史")
        self.export_history_table = table(["导出时间", "报告类型", "文件名", "格式 / 大小", "操作"], 240)
        self.export_history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for col, width in ((0, 170), (1, 115), (3, 120), (4, 190)):
            self.export_history_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self.export_history_table.setColumnWidth(col, width)
        history.addWidget(self.export_history_table)
        self.export_history_empty = label("尚无导出记录。成功导出后，可打开文件或所在文件夹。", "muted")
        history.addWidget(self.export_history_empty)
        layout.addWidget(history_box)
        layout.addStretch()
        return page

    def export_panel(self, key):
        box, body = group("导出设置")
        box.setMinimumWidth(275)
        body.addWidget(label("报告类型", "muted"))
        body.addWidget(label("分子筛选报告" if key == "prediction" else "模型训练报告", "section"))
        body.addWidget(label("导出内容", "sectionTitle"))
        captions = (
            (("molecule", "分子信息"), ("activity", "活性预测"), ("stages", "筛选证据"), ("parameters", "参数与来源"))
            if key == "prediction" else
            (("models", "模型指标"), ("data", "数据划分与参数"), ("weights", "融合权重"), ("run", "运行信息"))
        )
        checks = {}
        for section, caption in captions:
            check = QCheckBox(caption)
            check.setChecked(True)
            check.toggled.connect(lambda _=False, k=key: self.update_export_preview(k))
            checks[section] = check
            body.addWidget(check)
        self.export_sections[key] = checks
        body.addWidget(label("导出格式", "sectionTitle"))
        formats = {}
        radio_group = QButtonGroup(box)
        for kind, caption in (("html", "HTML 报告"), ("csv", "CSV 数据"), ("json", "JSON 数据")):
            radio = QRadioButton(caption)
            radio_group.addButton(radio)
            formats[kind] = radio
            radio.toggled.connect(lambda _=False, k=key: self.update_export_note(k))
            body.addWidget(radio)
        self.export_formats[key] = formats
        note = label("", "muted")
        self.export_notes[key] = note
        body.addWidget(note)
        formats["html"].setChecked(True)
        export = icon_button(button("导出报告", lambda checked=False, k=key: self.export_selected(k), True), "download", True)
        export.setEnabled(False)
        body.addWidget(export)
        feedback = label("完成有效预测后可导出。" if key == "prediction" else "加载模型训练记录后可导出。", "muted")
        self.export_feedback[key] = feedback
        body.addWidget(feedback)
        if key == "prediction":
            self.report_export_button = export
            self.pred_export_buttons.append(export)
        else:
            self.training_report_export_button = export
            self.training_export_button = icon_button(button("导出模型及运行记录", self.export_training), "folder")
            self.training_export_button.setEnabled(False)
            body.addWidget(self.training_export_button)
            body.addWidget(label("完整资料另存为文件夹，含四个模型、完整报告、指标及来源记录。", "muted"))
        body.addWidget(label("结论、版本与功能边界始终保留。", "muted"))
        body.addStretch()
        return box

    def update_export_note(self, key):
        if key not in self.export_notes:
            return
        kind = next((kind for kind, radio in self.export_formats[key].items() if radio.isChecked()), "html")
        if key == "prediction":
            notes = {
                "html": "HTML：用于阅读和打印，所选分子图内嵌，断网可读。",
                "csv": "CSV：用于表格分析，每个分子一行；列及追溯数据按勾选项导出。",
                "json": "JSON：所选结构化结果、规则与运行信息；全选时保留完整记录。",
            }
        else:
            metrics = "models" in self.selected_sections(key)
            notes = {
                "html": "HTML：用于阅读和打印所选训练指标、数据划分、权重和运行信息，断网可读。",
                "csv": "CSV：每个模型或融合方案一行，含所选指标与摘要元数据；完整搜索历史用 JSON。" if metrics else
                       "CSV：未勾选模型指标，导出一行所选摘要元数据；完整记录用 JSON。",
                "json": "JSON：用于读取所选训练记录；全选时包含完整参数与来源。",
            }
        self.export_notes[key].setText(notes[kind])

    def selected_sections(self, key):
        return {section for section, check in self.export_sections[key].items() if check.isChecked()}

    def update_export_preview(self, key):
        sections = self.selected_sections(key) if key in self.export_sections else set()
        if key == "prediction" and hasattr(self, "report_parameter_text"):
            valid = self.last_result is not None
            self.report_molecule.setVisible(valid and "molecule" in sections)
            self.report_stage_table.setVisible(valid and "stages" in sections)
            self.report_prediction_table.setVisible(valid and "activity" in sections)
            self.report_parameter_text.setVisible(valid and "parameters" in sections)
        elif key == "training" and hasattr(self, "training_report_run"):
            for widget, section in (
                (self.training_report_table, "models"), (self.training_comparison_note, "models"),
                (self.training_report_weight_title, "weights"), (self.training_report_weights, "weights"),
                (self.training_report_data, "data"), (self.training_report_run, "run"),
            ):
                widget.setVisible(self.bundle is not None and section in sections)
        self.update_export_note(key)
        if key in self.export_feedback and not sections:
            self.export_feedback[key].setText("请至少勾选一项导出内容。")
        if hasattr(self, "report_export_button") and hasattr(self, "training_report_export_button"):
            self.refresh_actions()
        if hasattr(self, "report_tabs"):
            self.report_tabs.updateGeometry()

    def export_selected(self, key):
        sections = self.selected_sections(key)
        if not sections:
            QMessageBox.information(self, "请选择内容", "请至少选择一项导出内容。")
            return
        kind = next((kind for kind, radio in self.export_formats[key].items() if radio.isChecked()), "html")
        if key == "prediction":
            self.export_prediction(kind, sections)
        else:
            self.export_training_report(kind, sections)

    def load_export_history(self):
        path = self.root / "reports" / "export-history.json"
        if path.exists():
            try:
                records = read_json(path)
                if not isinstance(records, list) or any(not isinstance(row, dict) or not {"path", "kind", "report", "time", "bytes"}.issubset(row) for row in records):
                    raise ValueError("历史记录格式无效")
                self.export_history = records[:200]
            except Exception as error:
                backup = path.with_name("export-history-invalid-" + utc_now().replace(":", "-") + ".json")
                shutil.copy2(path, backup)
                self.append_log("导出历史读取失败，原件已保留：" + str(error))
        self.refresh_export_history()

    def refresh_export_history(self):
        rows = []
        for record in self.export_history[:20]:
            size = record["bytes"]
            size_text = f"{size / 1024:.1f} KB" if size < 1024 ** 2 else f"{size / 1024 ** 2:.1f} MB"
            rows.append([display_time(record["time"]).replace("（北京时间）", ""), record["report"],
                         Path(record["path"]).name, record["kind"].upper() + " / " + size_text, ""])
        populate(self.export_history_table, rows)
        for row, record in enumerate(self.export_history[:20]):
            open_button = button("打开", lambda checked=False, path=record["path"]: self.open_export(path))
            open_button.setToolTip(record["path"])
            open_button.setText("打开文件" if record["kind"] != "folder" else "打开目录")
            actions = QWidget()
            row_layout = QHBoxLayout(actions)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.addWidget(open_button)
            folder_button = button("所在文件夹", lambda checked=False, path=record["path"], kind=record["kind"]:
                                   self.open_export_folder(path, kind))
            folder_button.setToolTip("打开导出文件所在目录；不修改文件。")
            row_layout.addWidget(folder_button)
            self.export_history_table.setCellWidget(row, 4, actions)
            self.export_history_table.setRowHeight(row, max(40, self.export_history_table.rowHeight(row)))
        self.export_history_table.fit_content()
        self.export_history_empty.setVisible(not bool(rows))

    def copy_run_info(self, field):
        if self.bundle is None:
            return
        report = self.bundle[1]
        text = json.dumps(report, ensure_ascii=False, indent=2) if field == "json" else report[field]
        QApplication.clipboard().setText(str(text))
        self.statusBar().showMessage("已复制" + {"run_id": "运行 ID", "data_sha256": "SHA256", "json": "完整运行记录"}[field], 5000)

    def open_export(self, path):
        path = Path(path)
        if not path.exists():
            QMessageBox.information(self, "文件已移动", "导出记录仍保留，但原路径已不存在：\n" + str(path))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def open_export_folder(self, path, kind="file"):
        path = Path(path)
        directory = path if kind == "folder" else path.parent
        if not directory.is_dir():
            QMessageBox.information(self, "目录已移动", "原导出目录不存在，请检查文件是否已移动：\n" + str(directory))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))

    def export_message(self, key, message, failed=False):
        feedback = self.export_feedback[key]
        feedback.setObjectName("error" if failed else "muted")
        feedback.setText(message)
        feedback.style().unpolish(feedback)
        feedback.style().polish(feedback)
        self.statusBar().showMessage(message[:140], 12000)

    def record_export(self, path, kind, report, sections=None):
        path = Path(path).resolve()
        size = path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        record = {"path": str(path), "kind": kind, "report": report, "time": utc_now(), "bytes": size,
                  "sections": sorted(sections) if sections is not None else "all"}
        self.export_history = [record, *self.export_history][:200]
        try:
            write_json(self.root / "reports" / "export-history.json", self.export_history)
        except OSError as error:
            self.append_log("文件已导出，但历史记录保存失败：" + str(error))
        self.refresh_export_history()

    def append_log(self, message):
        if message.startswith("清洗步骤 ") and "：" in message:
            steps, state = message.removeprefix("清洗步骤 ").split("：", 1)
            self.set_cleaning_steps([int(i) - 1 for i in steps.split("/")], state)
            if self.job_kind == "data":
                self.data_notice.setText(f"正在清洗数据 · 步骤 {steps}：{state}")
        self.log_view.appendPlainText(message)
        self.statusBar().showMessage(message[:120])

    def set_cleaning_steps(self, indices, state):
        for index in indices:
            self.cleaning_steps[index].setText(f"{index + 1:02d} {self.cleaning_step_names[index]}\n{state}")
            set_tone(self.cleaning_steps[index], {"完成": "good", "进行中": "info", "失败": "bad"}.get(state, "neutral"))

    def refresh_actions(self):
        available = not self.busy
        for widget in (self.download_button, self.import_button, self.refresh_button, self.csv_drop,
                       self.template_button, self.load_model_button, self.training_seed, self.train_reset_button,
                       self.smiles, self.rules_details, self.demo_details):
            widget.setEnabled(available)
        trainable = self.training_data is not None and self.training_data.get("ready", False)
        self.train_button.setEnabled(available and trainable)
        self.next_training_button.setEnabled(available and trainable)
        why = "" if trainable else (self.training_data or {}).get("problem", "请先获取或导入训练数据。")
        self.train_button.setToolTip(why or "按左侧设置训练四个模型并运行融合优化。")
        self.next_training_button.setToolTip(why)
        self.data_next_hint.setText(why)
        self.data_predict_link.setEnabled(available and self.bundle is not None)
        self.data_predict_link.setToolTip("" if self.bundle else "请先加载已有模型。")
        self.predict_button.setEnabled(available and self.bundle is not None and bool(self.smiles.text().strip()))
        self.predict_button.setText("正在预测…" if self.predicting else "预测活性")
        self.predict_button.setToolTip("请先加载模型。" if self.bundle is None else
                                       "请输入 SMILES。" if not self.smiles.text().strip() else "支持 Enter 提交。")
        valid = self.last_result is not None and available
        for widget in self.pred_export_buttons:
            widget.setEnabled(valid)
        self.funnel_report_button.setEnabled(valid)
        self.import_evidence_button.setEnabled(available and self.last_prediction is not None)
        self.clear_evidence_button.setEnabled(available and (self.external_stages is not None or self.use_demo.isChecked()))
        self.report_export_button.setEnabled(valid and bool(self.selected_sections("prediction")))
        self.training_report_export_button.setEnabled(available and self.bundle is not None and bool(self.selected_sections("training")))
        self.training_export_button.setEnabled(available and self.bundle is not None)

    def start_job(self, operation, on_complete, kind="data"):
        if self.busy or (self.worker and self.worker.isRunning()):
            return False
        self.busy = True
        self.job_kind = kind
        self.predicting = kind == "prediction"
        self.progress.setRange(0, 0)
        self.progress.show()
        if kind != "prediction":
            self.log_details.set_expanded(True)
        self.worker = Worker(operation)
        self.worker.message.connect(self.append_log)
        def completed(result):
            try:
                on_complete(result)
            except Exception:
                self.job_failed(traceback.format_exc())
        self.worker.completed.connect(completed)
        self.worker.failed.connect(self.job_failed)
        self.worker.finished.connect(self.job_finished)
        self.refresh_actions()
        self.worker.start()
        return True

    def job_finished(self):
        self.busy = False
        self.predicting = False
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.hide()
        self.refresh_actions()

    def job_failed(self, error):
        reason = re.sub(r"^(ValueError|RuntimeError|FileNotFoundError|PermissionError):\s*", "", error.splitlines()[-1])
        if any(name in reason for name in ("ConnectionError", "ReadTimeout", "ConnectTimeout")):
            reason = "连接数据源失败或请求超时，请检查网络"
        self.append_log(error)
        write_json(self.root / "reports" / "last-error.json", {"time": utc_now(), "error": error})
        if self.job_kind == "prediction":
            self.last_prediction = None
            self.reset_result_views("预测失败：" + reason)
            self.predict_input_error.setText(reason + "。保留了原输入，修正后可再次点击“预测活性”。")
            self.predict_input_error.show()
        elif self.job_kind == "data":
            self.data_notice.setText("本次数据操作失败：" + reason + "。请修正文件或检查网络后重试。")
            set_tone(self.data_notice, "bad")
            self.retry_data_button.setVisible(self.retry_data is not None)
            self.data_preparation_failed = True
            self.update_training_data_hint()
            if self.sample_table.rowCount():
                self.data_label.setText("上次清洗结果（本次未更新）")
            for i, step in enumerate(self.cleaning_steps):
                if "进行中" in step.text():
                    self.set_cleaning_steps([i], "失败")
        else:
            self.training_notice.setText("训练未完成：" + reason + "。原已加载模型和历史指标保留，可修正数据后重试。")
            set_tone(self.training_notice, "bad")

        self.statusBar().showMessage("操作未完成：" + reason, 12000)

    def begin_data_task(self, operation, caption):
        if self.busy:
            return
        self.invalidate_results("数据准备操作已开始")
        self.set_cleaning_steps(range(5), "未开始")
        self.training_data = {"ready": False, "problem": "数据准备进行中，请等待完成。"}
        self.data_notice.setText(caption + "，请稍候。可在模型训练页查看运行日志。")
        set_tone(self.data_notice, "info")
        self.retry_data_button.hide()
        self.start_job(operation, lambda _: self.refresh_data(), "data")

    def download_data(self, refresh=False):
        self.retry_data = lambda: self.download_data(refresh)
        self.begin_data_task(lambda log: prepare(self.root, log, refresh=refresh),
                             "正在更新数据快照" if refresh else "正在获取 ChEMBL 数据（优先复用已有快照）")

    def retry_last_data(self):
        if self.retry_data is not None and not self.busy:
            self.retry_data()

    def download_csv_template(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存空白 CSV 模板", "ERalpha-IC50-导入模板.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            if Path(path).suffix.lower() != ".csv":
                path += ".csv"
            write_csv(path, ["SMILES", "IC50", "units", "relation"], [])
            self.data_notice.setText("已保存空白模板：" + Path(path).name + "。请填入真实实验记录，relation 使用精确关系“=”，来源在导入时填写。")
            set_tone(self.data_notice, "good")
        except OSError as error:
            self.data_notice.setText("模板未保存：" + str(error))
            set_tone(self.data_notice, "bad")

    def show_import_context(self, filename, options):
        mapping = options.get("mapping", {})
        unit = mapping.get("unit") or options.get("unit") or "待确认"
        text = (f"文件：{filename}\nSMILES 列：{mapping.get('smiles') or '待选择'}；"
                f"IC50 列：{mapping.get('ic50') or '待选择'}；单位：{unit}\n"
                "来源：" + (options.get("source") or "待填写"))
        self.import_context.setPlainText(text)
        self.import_info_details.show()
        self.import_info_details.set_expanded(True)

    def import_data(self, path=None):
        if self.busy:
            return
        if not isinstance(path, (str, Path)):
            path, _ = QFileDialog.getOpenFileName(self, "选择 ERα 结合测定 CSV", "", "CSV (*.csv)")
        if not path:
            return
        path = Path(path)
        initial = self.last_import_options.get(str(path), {})
        self.show_import_context(path.name, initial)
        self.retry_data = lambda: self.import_data(path)
        try:
            dialog = CsvImportDialog(path, self, initial=initial)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            options = {"mapping": dict(dialog.mapping), "unit": dialog.default_unit, "source": dialog.source_note}
            self.last_import_options[str(path)] = options
            self.show_import_context(path.name, options)
            self.begin_data_task(
                lambda log: prepare(self.root, log, path, options["source"],
                                    column_mapping=options["mapping"], default_unit=options["unit"]),
                "正在导入与清洗 " + path.name)
        except Exception as error:
            self.data_notice.setText("文件未导入：" + str(error) + "。请选择正确文件后重试。")
            set_tone(self.data_notice, "bad")
            self.retry_data_button.show()

    def refresh_data(self):
        audit_path = self.root / "data" / "processed" / "audit.json"
        self.training_data = None
        if not audit_path.exists():
            self.sample_table.setRowCount(0)
            self.audit_details.hide()
            self.data_summary_tabs.hide()
            self.data_empty_hint.show()
            self.next_training_button.setEnabled(False)
            self.data_predict_link.setVisible(self.bundle is not None)
            self.update_training_data_hint()
            self.refresh_actions()
            return
        audit = read_json(audit_path)
        self.data_preparation_failed = False
        self.data_label.setText(f"原始 {audit['raw_count']} 条  →  有效 {audit['unique_compounds']} 个化合物")
        duplicates = audit.get("duplicate_records_aggregated")
        duplicates_text = f"{duplicates} 条" if duplicates is not None else "未记录"
        self.data_audit_summary.setText(
            f"排除记录 {audit['rejected_records']} 条  ·  合并重复测定：{duplicates_text}"
            f"  ·  pIC50 范围 {audit['pIC50_range'][0]:.2f}–{audit['pIC50_range'][1]:.2f}\n"
            "预览前10个化合物；完整清洗数据与逐条排除记录保留在本地工作目录。")
        self.audit_view.setPlainText(json.dumps(audit, ensure_ascii=False, indent=2))
        import pandas as pd
        frame = pd.read_csv(audit_path.parent / "cleaned.csv").head(10)
        populate(self.sample_table, [[r.canonical_smiles, f"{r.pIC50:.3f}", r.record_count, r.molecule_ids] for r in frame.itertuples()])
        reasons = dict(audit["reasons"])
        if audit.get("replicate_conflict_records"):
            reasons["replicate_spread_gt_1_log"] = audit["replicate_conflict_records"]
        names = {
            "non_exact_relation": "非精确 IC50 测定", "nonpositive_or_nonfinite_ic50": "IC50 非正值或非有限值",
            "unsupported_unit": "不支持的测定单位", "wrong_target": "不属于 ERα / ESR1 靶点",
            "not_ic50": "不是 IC50 测定", "ineligible_assay": "实验条件不符合筛选要求",
            "data_validity_flag": "数据有效性标记异常", "potential_duplicate": "潜在重复记录",
            "non_binding_assay": "不是结合测定", "wrong_organism": "非人类测定",
            "replicate_spread_gt_1_log": "同分子重复测定跨度超过1个log单位",
        }
        populate(self.rejection_table, [[names.get(reason, reason), count] for reason, count in reasons.items()])
        self.rejection_hint.setVisible(not bool(reasons))
        self.data_empty_hint.hide()
        self.data_summary_tabs.show()
        self.data_predict_link.setVisible(self.bundle is not None)
        self.audit_details.show()
        self.next_training_button.setEnabled(True)
        self.update_training_data_hint(audit)
        self.set_cleaning_steps(range(5), "完成")
        self.data_notice.setText("已载入清洗结果：可查看摘要、排除原因和数据预览。")
        set_tone(self.data_notice, "good")
        self.retry_data_button.hide()
        source = audit.get("source", {})
        if source.get("type") == "user_import":
            self.show_import_context(source.get("filename", "实验 CSV"), {
                "mapping": source.get("column_mapping", {}),
                "unit": source.get("default_unit"), "source": source.get("source_note", "")})
        self.refresh_actions()
        self.append_log("数据就绪，可开始训练")

    def update_training_data_hint(self, audit=None):
        if self.data_preparation_failed:
            problem = "本次数据准备失败，请重新获取或导入成功后再训练。旧清洗文件和已加载模型保留。"
            self.training_data = {"ready": False, "problem": problem}
            self.pending_count.setText("本次待训练数据未就绪")
            self.training_data_hint.setText(problem)
            return
        audit_path = self.root / "data" / "processed" / "audit.json"
        if audit is None and audit_path.exists():
            audit = read_json(audit_path)
        self.training_data = None
        if audit is None:
            self.pending_count.setText("尚未导入待训练数据")
            self.training_data_hint.setText("请先导入训练数据；内置模型仍可直接用于预测。")
            return
        count = audit["unique_compounds"]
        cleaned_path = audit_path.parent / "cleaned.csv"
        intact = cleaned_path.exists() and digest(cleaned_path) == audit["cleaned_sha256"]
        ready = intact and count >= 60 and audit.get("pIC50_std", 0) >= .1
        problem = ("清洗数据与摘要不一致，请重新清洗。" if not intact else
                   "训练需要至少60个有效化合物，且 pIC50 标准差不少于0.1。" if not ready else "")
        self.training_data = {"audit": audit, "ready": ready, "problem": problem}
        self.pending_count.setText(f"本次待训练：{count} 个化合物")
        self.training_data_hint.setText(problem or "数据已准备；结构组和各集合是否满足要求将在训练前进一步校验。")

    def start_training(self):
        if self.busy:
            return
        self.update_training_data_hint()
        if not self.training_data or not self.training_data["ready"]:
            self.refresh_actions()
            return
        seed = self.training_seed.value()
        self.navigate("模型训练")
        self.training_notice.setText(f"正在运行本次训练（随机种子 {seed}）；右侧指标暂保留上一模型的历史记录。")
        set_tone(self.training_notice, "info")
        self.invalidate_results("模型训练已开始")
        self.start_job(lambda log: train(self.root, seed=seed, log=log), self.set_bundle, "training")

    def set_bundle(self, folder):
        bundle = load_bundle(Path(folder))
        had_result = self.last_result is not None or self.last_prediction is not None
        self.bundle = bundle
        self.model_folder = Path(folder)
        report = self.bundle[1]
        self.training_content.show()
        self.fusion_content.show()
        self.fusion_load_button.hide()
        self.training_report_body.show()
        self.data_predict_link.show()
        counts = report["split_counts"]
        total = sum(counts.values())
        self.training_count.setText(f"历史有效化合物：{total} 个；历史随机种子：{report['seed']}")
        for value, key in zip(self.split_labels, ("train", "validation", "test")):
            value.setText(f"{counts[key]}  ({counts[key] / total:.1%})")
        self.fusion_version.setText("当前已加载模型 · " + display_time(report["created_at"]))
        self.fusion_version.setToolTip(report["run_id"])
        self.model_label.setText(f"以下为已加载模型的历史记录 · 固定 ERα / ESR1 · 共 {total} 个化合物")
        self.model_label.setToolTip(report["run_id"])
        self.training_notice.setText("历史训练记录已加载 · 完成时间：" + display_time(report["created_at"]))
        set_tone(self.training_notice, "good")
        best = max(MODEL_NAMES, key=lambda name: report["test_metrics"][name]["R2"])
        populate(self.model_table, [[name, *[f"{report['test_metrics'][name][m]:.4f}" for m in ("R2", "RMSE", "MAE")],
                                    "本记录单模型 R² 最高" if name == best else ""] for name in MODEL_NAMES])
        self.highlight_row(self.model_table, MODEL_NAMES.index(best))
        populate(self.fusion_table, [[method + ("（已选）" if method == report["selected"] else ""),
            *[f"{weight:.1%}" for weight in report["optimizers"][method]["weights"]],
            f"{report['validation_metrics'][method]['RMSE']:.4f}"] for method in ("GA", "SA", "TS")])
        self.highlight_row(self.fusion_table, ("GA", "SA", "TS").index(report["selected"]))
        names = {"GA": "遗传算法", "SA": "模拟退火", "TS": "禁忌搜索"}
        precision = []
        for row, method in enumerate(("GA", "SA", "TS")):
            rmse = report["validation_metrics"][method]["RMSE"]
            mse = report["optimizers"][method]["validation_mse"]
            self.fusion_table.item(row, 0).setToolTip(names[method])
            self.fusion_table.item(row, 5).setToolTip(
                f"{names[method]}\n验证集 RMSE：{rmse:.17g}\n用于选择的验证集 MSE：{mse:.17g}")
            precision.append(f"{method}（{names[method]}）：RMSE={rmse:.17g}；MSE={mse:.17g}")
            for col, weight in enumerate(report["optimizers"][method]["weights"], 1):
                self.fusion_table.item(row, col).setToolTip(f"原始权重：{weight:.17g}（百分比显示已四舍五入）")
        self.fusion_precision_view.setPlainText("\n".join(precision) + "\n\n模型版本：" + report["run_id"])
        self.fusion_precision_details.show()
        metrics = report["test_metrics"]["ensemble"]
        for value, text in zip(self.fusion_metrics, (report["selected"], f'{report["validation_metrics"][report["selected"]]["RMSE"]:.4f}', f'{metrics["R2"]:.4f}')):
            value.setText(text)
        for value, metric in zip(self.test_metric_labels, ("R2", "RMSE", "MAE")):
            value.setText(f"{metrics[metric]:.4f}")
        self.test_label.setText("方案在验证集冻结，独立测试评估一次。融合不保证优于每个单模型。")
        self.metric_chart.values = report["test_metrics"]
        self.metric_chart.update()
        self.weights_chart.values = report["weights"]
        self.weights_chart.update()
        self.report_view.setPlainText(json.dumps(report, ensure_ascii=False, indent=2))
        self.training_report_summary.setText(
            f"融合（{report['selected']}）· 独立测试 R² {metrics['R2']:.4f}  /  RMSE {metrics['RMSE']:.4f}  /  MAE {metrics['MAE']:.4f}")
        self.training_report_meta.setText(
            f"历史有效化合物：{total}  |  结构分组：{report['structure_groups']}  |  历史随机种子：{report['seed']}")
        populate(self.training_report_table, [[f"融合（{report['selected']}）" if name == "ensemble" else name,
            *[f"{report['test_metrics'][name][metric]:.4f}" for metric in ("R2", "RMSE", "MAE")]] for name in (*MODEL_NAMES, "ensemble")])
        all_names = (*MODEL_NAMES, "ensemble")
        lowest_mae = min(all_names, key=lambda name: report["test_metrics"][name]["MAE"])
        mae_name = f"融合（{report['selected']}）" if lowest_mae == "ensemble" else lowest_mae
        best_rmse = min(MODEL_NAMES, key=lambda name: report["test_metrics"][name]["RMSE"])
        self.training_comparison_note.setText(f"本记录中，{best} 的单模型测试 R² 最高，{best_rmse} 的单模型测试 RMSE 最低；{mae_name} 的测试 MAE 最低。融合依据验证集选择。")
        self.training_report_weights.values = report["weights"]
        self.training_report_weights.update()
        self.training_report_data.setText(
            f"数据划分：训练 {counts['train']} / 验证 {counts['validation']} / 测试 {counts['test']}。"
            f"原始 {report['cleaning']['raw_count']} 条记录清洗为 {total} 个化合物。")
        self.training_report_run.setText(f"运行 ID：{report['run_id']}\n训练完成时间：{display_time(report['created_at'])}\n历史随机种子：{report['seed']}\n数据 SHA256：{report['data_sha256']}")
        self.training_export_button.setEnabled(True)
        self.training_report_export_button.setEnabled(True)
        self.update_export_preview("training")
        self.update_training_data_hint()
        self.external_stages = None
        self.invalidate_results("已加载模型发生变化" if had_result else "模型已就绪")
        self.append_log("已加载并校验4个模型：" + report["run_id"])

    @staticmethod
    def highlight_row(widget, row):
        for col in range(widget.columnCount()):
            item = widget.item(row, col)
            if item is not None:
                item.setBackground(QColor("#eaf3ff"))
                item.setForeground(QColor("#176bd3"))
                font = item.font()
                font.setBold(True)
                item.setFont(font)

    def copy_fusion_precision(self):
        if self.bundle:
            QApplication.clipboard().setText(self.fusion_precision_view.toPlainText())
            self.statusBar().showMessage("已复制优化器完整精度与模型版本", 5000)

    def choose_model(self):
        folder = QFileDialog.getExistingDirectory(self, "选择本项目可信训练的模型版本目录")
        if folder:
            try:
                self.set_bundle(Path(folder))
            except Exception as error:
                QMessageBox.warning(self, "模型加载失败", str(error))

    def reset_result_views(self, message="等待预测 · 输入 SMILES 后点击“预测活性”。", keep_prediction=False):
        self.last_result = None
        self.enable_export(False)
        self.prediction_content.setVisible(keep_prediction)
        self.prediction_empty_hint.setVisible(not keep_prediction)
        self.prediction_empty_panel.setVisible(not keep_prediction)
        self.funnel_predict_link.setVisible(not keep_prediction)
        self.funnel_context.setText(message)
        tone = "bad" if "失败" in message or "无效" in message else "warning" if "已失效" in message else "info"
        set_tone(self.funnel_context, tone)
        self.funnel_molecule.setText("当前分子：尚未选择")
        self.funnel_score.setText("综合评分尚未完成：等待有效预测与阶段证据。")
        for number, (status, flow, fields) in enumerate(self.screen_stage_views, 1):
            status.setText("○ 未开始" if number == 1 else "○ 缺少证据 · 未评估")
            set_tone(status, "neutral")
            flow.setText("等待分子预测" if number == 1 else "等待证据")
            fields[0].setText("等待分子预测结果" if number == 1 else
                              "尚未提供外部证据" if number == 2 else "尚未提供结构判定证据")
            fields[2].setText("等待有效输入" if number == 1 else "缺少证据，暂不评估")
        self.refresh_stage_conditions()
        self.model_details.setVisible(keep_prediction)
        self.funnel_table.setRowCount(0)
        if not keep_prediction:
            self.prediction_table.setRowCount(0)
            self.molecule_image.clear()
            self.report_molecule.clear()
            self.activity_label.setText("—")
            self.activity_chart.values = None
            self.activity_chart.update()
            self.properties_label.setText("分子式、MW、LogP、TPSA将在预测后显示。")
        self.activity_status.setText("参数无效，判定未生成" if keep_prediction else "尚未评估")
        set_tone(self.activity_status, "neutral")
        self.activity_threshold_label.setText(f"{self.parameters['activity_threshold'].value():.2f}")
        self.conclusion.setText(message)
        self.statusBar().showMessage(message[:140])
        set_tone(self.conclusion, tone)
        self.score_label.setText("综合评分尚未完成：阶段数据尚未齐全。")
        for number, (status, reason) in enumerate(zip(self.stage_status_labels, self.stage_reason_labels), 1):
            status.setText("○ 未开始" if number == 1 else "○ 缺少证据 · 未评估")
            set_tone(status, "neutral")
            reason.setText("等待分子预测结果。" if number == 1 else
                           "尚未提供外部证据。" if number == 2 else "尚未提供结构判定证据。")
        self.screening_summary.setText(message)
        self.report_empty_heading.setText("结果已失效，请重新预测" if "已失效" in message else "尚未生成筛选报告")
        self.screening_meta.setText("完成当前输入的有效预测后可导出。")
        self.report_stage_table.setRowCount(0)
        self.report_prediction_table.setRowCount(0)
        self.report_parameter_text.clear()
        self.prediction_report_raw.clear()

    def refresh_stage_conditions(self):
        try:
            rules = self.current_rules()
        except ValueError as error:
            for _, _, fields in self.screen_stage_views:
                fields[1].setText("当前参数组合无效：" + str(error))
            return
        conditions = (
            f"pIC50 ≥ {rules.activity_threshold:.2f}（硬底线6.0）",
            f"logS {rules.logs_min:g}–{rules.logs_max:g}；F≥{rules.f_min:g}%；PPB≤{rules.ppb_max:g}%；肝毒性/CYP3A4高风险硬性淘汰",
            "完整67项约束定义与布尔判定；不以描述符替代完整评估",
        )
        for (_, _, fields), text in zip(self.screen_stage_views, conditions):
            fields[1].setText(text)

    def invalidate_results(self, reason):
        had_result = self.last_result is not None or self.last_prediction is not None or getattr(self, "_result_stale", False)
        self.last_prediction = None
        self._result_stale = had_result
        self.reset_result_views(("结果已失效，请重新预测：" + reason) if had_result else
                                "等待预测 · 输入 SMILES 后点击“预测活性”。")
        self.refresh_actions()

    def clear_prediction(self):
        self.last_prediction = None
        self.last_result = None
        self._result_stale = False
        self.external_stages = None
        self.smiles.clear()
        self.predict_input_error.clear()
        self.predict_input_error.hide()
        self.reset_result_views()
        self.refresh_actions()

    def invalidate_input(self):
        self.external_stages = None
        self.predict_input_error.clear()
        self.predict_input_error.hide()
        self.invalidate_results("SMILES 已修改")

    def rules_changed(self, *_):
        if getattr(self, "_applying_rules", False):
            return
        self.invalidate_results("筛选参数已修改")

    def enable_export(self, enabled):
        self.pred_report_body.setVisible(enabled)
        self.report_empty_panel.setVisible(not enabled)
        self.screening_summary.setVisible(enabled)
        self.screening_meta.setVisible(enabled)
        self.report_predict_link.setVisible(not enabled)
        self.screening_preview_box.setMaximumHeight(16777215 if enabled else 380)
        if not enabled:
            self.export_feedback["prediction"].setText("结果已失效，请重新预测后导出。" if getattr(self, "_result_stale", False) else
                                                         "完成有效预测后可导出；缺失证据会保留未评估状态。")
        self.refresh_actions()
        self.report_tabs.updateGeometry()

    def run_prediction(self):
        if self.busy:
            return
        smiles = self.smiles.text().strip()
        if not smiles:
            self.predict_input_error.setText("请输入 SMILES 后再预测。")
            self.predict_input_error.show()
            self.refresh_actions()
            return
        if self.bundle is None:
            self.predict_input_error.setText("请先加载已有模型。")
            self.predict_input_error.show()
            return
        try:
            self.current_rules()
        except ValueError as error:
            self.predict_input_error.setText("筛选参数无效：" + str(error))
            self.predict_input_error.show()
            return
        self._result_stale = False
        self.last_prediction = None
        self.reset_result_views("正在预测…")
        self.prediction_empty_panel.hide()
        self.predict_input_error.clear()
        self.predict_input_error.hide()
        bundle = self.bundle
        model_version = bundle[1]["run_id"]

        def operation(log):
            mol, canonical = standardize(smiles)
            result = predict(smiles, bundle)
            result.update(canonical_smiles=canonical, properties=properties(mol),
                          formula=rdMolDescriptors.CalcMolFormula(mol))
            buffer = io.BytesIO()
            Draw.MolToImage(mol, size=(1100, 650)).save(buffer, format="PNG")
            return result, buffer.getvalue()

        def completed(payload):
            if self.smiles.text().strip() != smiles or self.bundle[1]["run_id"] != model_version:
                self.invalidate_results("输入或模型在预测期间已改变")
                return
            result, png = payload
            pixmap = QPixmap()
            pixmap.loadFromData(png)
            self.molecule_image.show_structure(pixmap)
            self.report_molecule.show_structure(pixmap)
            props = result["properties"]
            self.properties_label.setText(f"分子式：{result['formula']}    MW：{props['MW']:.2f}\nLogP：{props['LogP']:.2f}    TPSA：{props['TPSA']:.2f}")
            self.activity_label.setText(f"{result['ensemble_pIC50']:.3f}")
            self.activity_chart.values = result["predictions"]
            self.activity_chart.update()
            populate(self.prediction_table, [[name, f"{result['predictions'][name]:.3f}", f"{weight:.1%}"]
                     for name, weight in zip(MODEL_NAMES, result["weights"])])
            self.last_prediction = result
            self.recalculate()
            self.export_feedback["prediction"].setText("报告已更新，可按右侧选择导出。")

        self.start_job(operation, completed, "prediction")

    def update_screening_views(self):
        self.prediction_content.show()
        self.prediction_empty_hint.hide()
        self.prediction_empty_panel.hide()
        self.funnel_predict_link.hide()
        self.model_details.show()
        result = self.last_result
        screening = result["screening"]
        rows = stage_rows(result)
        populate(self.funnel_table, rows)
        self.funnel_context.setText(f'{screening["conclusion"]}  ·  pIC50 {result["ensemble_pIC50"]:.3f}')
        self.funnel_score.setText(score_text(result))
        tone = "bad" if "淘汰" in screening["conclusion"] else "warning" if screening["demo"] else "info"
        set_tone(self.funnel_context, tone)
        self.funnel_molecule.setText("当前分子：" + result["canonical_smiles"])
        self.funnel_molecule.setCursorPosition(0)
        self.funnel_molecule.setToolTip(result["canonical_smiles"])
        for row, (status, flow, fields) in zip(rows, self.screen_stage_views):
            status.setText(self.stage_label(row[1]))
            color = "#b44f47" if "淘汰" in row[1] else "#a46e24" if "演示" in row[1] or "需复核" in row[1] else "#1977ed" if row[1] == "通过" else "#74818d"
            set_tone(status, "bad" if "淘汰" in row[1] else "warning" if "演示" in row[1] or "需复核" in row[1] else "good" if row[1] == "通过" else "neutral")
            flow.setText(row[6])
            for field, text in zip(fields, (row[2], row[3], row[4] + "\n" + row[5])):
                field.setText(text)
        populate(self.report_stage_table, [[r[i] for i in (0, 1, 5, 6)] for r in rows])
        populate(self.report_prediction_table, [[name, f"{result['predictions'][name]:.3f}", f"{w:.1%}"]
                 for name, w in zip(MODEL_NAMES, result["weights"])])
        for stage, row, status, reason in zip(screening["stages"], rows, self.stage_status_labels, self.stage_reason_labels):
            status.setText(self.stage_label(row[1]))
            color = "#a46e24" if screening["demo"] and stage["stage"] > 1 else {
                "通过": "#1977ed", "淘汰": "#b44f47", "需复核": "#a46e24"}.get(stage["status"], "#74818d")
            set_tone(status, "bad" if "淘汰" in row[1] else "warning" if "演示" in row[1] or "需复核" in row[1] else "good" if row[1] == "通过" else "neutral")
            reason_text = stage_reason(stage, screening)
            reason.setText((reason_text.split("。")[0] + "。").replace("预测 pIC50", "预测值") if stage["stage"] == 1 else reason_text)
        s1 = screening["stages"][0]
        self.activity_status.setText("✓ 活性达到门槛" if s1["status"] == "通过" else "× 活性低于门槛")
        self.activity_threshold_label.setText(f"{screening['rules']['activity_threshold']:.2f}")
        set_tone(self.activity_status, "good" if s1["status"] == "通过" else "bad")
        self.activity_chart.threshold = screening["rules"]["activity_threshold"]
        self.activity_chart.update()
        self.conclusion.setText(screening["conclusion"])
        self.statusBar().showMessage(screening["conclusion"])
        set_tone(self.conclusion, tone)
        self.score_label.setText(score_text(result))
        self.screening_summary.setText(f"pIC50 {result['ensemble_pIC50']:.3f}  ·  {screening['conclusion']}")
        self.screening_meta.setText(score_text(result) + f"\n模型：{result['model_version']}  |  预测时间：{display_time(result['predicted_at'])}")
        self.prediction_report_raw.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        rules = screening["rules"]
        self.report_parameter_text.setText(f"活性门槛 {rules['activity_threshold']:.2f}  ·  阶段权重 " + " / ".join(f"{weight:.2f}" for weight in rules["stage_weights"]) + f"  ·  奖励 {rules['reward']:.2f} / 惩罚 {rules['penalty']:.2f}")
        self.update_export_preview("prediction")

    @staticmethod
    def stage_label(status):
        if "演示" in status:
            return "△ " + status
        return {"通过": "✓ 通过", "淘汰": "× 不通过 · 淘汰", "需复核": "△ 需复核",
                "未评估": "○ 缺少证据 · 未评估"}.get(status, status)

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
            self.last_result = {**self.last_prediction, "screening": screening, "stage_evidence": None if demo else self.external_stages,
                                "screening_updated_at": utc_now()}
            self.update_screening_views()
            self.enable_export(True)
        except Exception as error:
            self.reset_result_views("参数或阶段输入无效：" + str(error), keep_prediction=True)

    def demo_changed(self, enabled):
        for w in [*self.demo_fields.values(), self.demo_count]:
            w.setEnabled(enabled)
        self.rules_changed()

    def clear_stages(self):
        self.external_stages = None
        self.use_demo.setChecked(False)
        self.invalidate_results("阶段证据已清除")

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
        self._applying_rules = True
        try:
            for key, value in zip(("s1", "s2", "s3"), values.pop("stage_weights")):
                self.parameters[key].setValue(value)
            for key, value in values.items():
                self.parameters[key].setValue(value)
        finally:
            self._applying_rules = False
        self.rules_changed()

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
        if self.busy or self.last_prediction is None:
            return
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
                    raise ValueError("结构证据需要67项不同的约束定义，缺少时应保持未评估")
            screen(self.last_prediction["ensemble_pIC50"], self.current_rules(), obj.get("admet"), obj.get("structure"), evidence=obj["evidence"])
            self.external_stages = obj
            self.use_demo.setChecked(False)
            self.invalidate_results("阶段证据已更新")
        except Exception as error:
            QMessageBox.warning(self, "阶段数据未导入", str(error))

    def export_prediction(self, kind, sections=None):
        if self.last_result is None or self.busy:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出分子筛选报告", "分子筛选报告." + kind, kind.upper() + " (*." + kind + ")")
        if not path:
            return
        try:
            if Path(path).suffix.lower() != "." + kind:
                path += "." + kind
            export_prediction_file(path, kind, self.last_result, sections)
            self.record_export(path, kind, "分子筛选报告", sections)
            self.export_message("prediction", "已导出：" + Path(path).name + "。可在导出历史中打开。")
        except Exception as error:
            self.export_message("prediction", "导出失败：" + str(error) + "。有效结果保留，可再次点击导出重试。", True)

    def export_training_report(self, kind, sections=None):
        if self.bundle is None or self.busy:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出模型训练报告", "模型训练报告." + kind, kind.upper() + " (*." + kind + ")")
        if not path:
            return
        try:
            if Path(path).suffix.lower() != "." + kind:
                path += "." + kind
            export_training_file(path, kind, self.bundle[1], sections)
            self.record_export(path, kind, "模型训练报告", sections)
            self.export_message("training", "已导出：" + Path(path).name + "。可在导出历史中打开。")
        except Exception as error:
            self.export_message("training", "导出失败：" + str(error) + "。历史记录和当前模型保留，可重试。", True)

    def export_training(self):
        if self.bundle is None or self.busy:
            QMessageBox.information(self, "尚无训练资料", "请先完成训练或加载模型")
            return
        destination = QFileDialog.getExistingDirectory(self, "选择训练资料导出位置")
        if not destination:
            return
        try:
            folder = Path(destination) / ("ERLead-" + self.bundle[1]["run_id"])
            if folder.exists():
                folder = folder.with_name(folder.name + "-" + utc_now().replace(":", "-"))
            folder.mkdir(exist_ok=False)
            shutil.copytree(self.model_folder, folder / "models")
            report_dir = self.root / "reports" / self.bundle[1]["run_id"]
            if report_dir.exists():
                shutil.copytree(report_dir, folder / "reports")
            write_json(folder / "data-audit.json", self.bundle[1]["cleaning"])
            (folder / "训练报告.html").write_text(training_html(self.bundle[1]), encoding="utf-8")
            write_csv(folder / "模型指标.csv", MODEL_HEADERS, training_rows(self.bundle[1]))
            self.record_export(folder, "folder", "完整模型资料")
            self.export_message("training", "已导出模型及运行记录：" + folder.name + "。可在导出历史中打开。")
        except Exception as error:
            self.export_message("training", "模型资料未完整导出：" + str(error) + "。请检查目标目录后重试。", True)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "任务运行中", "请等待当前下载/训练完成后关闭，避免留下不完整产物。异常中断后可查看运行日志。")
            event.ignore()
        else:
            event.accept()


def launch(root):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setFont(workbench_font())
    window = MainWindow(root)
    window.show()
    return app.exec()
