"""Small Qt widgets shared by the six research workspaces."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QByteArray, Qt, QSize, Signal
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QHeaderView, QScrollArea)

ICON_PATHS = {
    "data": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
    "train": '<path d="m9 3 1-2h4l1 2 3 2 2 0 2 4-2 2v3l2 2-2 4-3-1-2 2h-5l-2-2-3 1-2-4 2-2v-3L2 9l2-4 3 0Z"/><circle cx="12" cy="11" r="3"/>',
    "fusion": '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="4" r="2"/><circle cx="20" cy="4" r="2"/><circle cx="4" cy="20" r="2"/><circle cx="20" cy="20" r="2"/><path d="m6 6 4 4m4 4 4 4m0-12-4 4m-4 4-4 4"/>',
    "molecule": '<path d="m7 3 10 0 5 9-5 9H7l-5-9Z"/><path d="m7 7 5-2 5 3m-9 9 5 2m5-5 1-4"/>',
    "filter": '<path d="M3 3h18l-7 9v8l-4 2V12Z"/>',
    "report": '<path d="M5 2h9l5 5v15H5ZM14 2v6h5M8 12h8m-8 4h8"/>',
    "upload": '<path d="M4 15v6h16v-6M12 16V3m-5 5 5-5 5 5"/>',
    "download": '<path d="M4 16v5h16v-5M12 3v13m-5-5 5 5 5-5"/>',
    "folder": '<path d="M2 6h8l2 3h10l-2 12H2ZM2 6V3h7l3 3h8v3"/>',
    "refresh": '<path d="M20 8a9 9 0 1 0 1 7M20 2v6h-6"/>',
    "chart": '<path d="M3 21V11h4v10m3 0V5h4v16m3 0V1h4v20"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m7 12 3 3 7-7"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 11v6m0-10v1"/>',
    "play": '<path d="m7 3 14 9L7 21Z"/>',
    "back": '<path d="M21 12H3m8-8-8 8 8 8"/>',
    "next": '<path d="M3 12h18m-8-8 8 8-8 8"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 5v7l5 3"/>',
    "trash": '<path d="M3 5h18M6 5l1 17h10l1-17M9 5V2h6v3m-5 4v9m4-9v9"/>',
    "settings": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="8" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
    "save": '<path d="M3 2h15l3 3v17H3ZM7 2v7h10V2M7 22v-8h10v8"/>',
}


def workbench_font(size=10.5, bold=False, numeric=False):
    font = QFont()
    font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei"] if numeric else
                     ["Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Segoe UI", "Segoe UI Symbol"])
    font.setPointSizeF(size)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    if numeric:
        font.setFeature(QFont.Tag.fromString("tnum"), 1)
    return font


def line_icon(name, color=None):
    result = QIcon()
    path = ICON_PATHS.get(name, ICON_PATHS["report"])
    for mode, state, stroke in (
        (QIcon.Mode.Normal, QIcon.State.Off, color or "#536171"),
        (QIcon.Mode.Normal, QIcon.State.On, color or "#1977ed"),
        (QIcon.Mode.Active, QIcon.State.Off, color or "#1977ed"),
        (QIcon.Mode.Disabled, QIcon.State.Off, "#a8b0bb"),
    ):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
               f'<g fill="none" stroke="{stroke}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
               + path + "</g></svg>")
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(svg.encode())).render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        result.addPixmap(pixmap, mode, state)
    return result


def icon_button(button, name, primary=False):
    button.setIcon(line_icon(name, "#ffffff" if primary else None))
    button.setIconSize(QSize(18, 18))
    button.setProperty("hasIcon", True)
    return button


def set_tone(widget, tone="info"):
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ActionScrollArea(QScrollArea):
    """Keep primary navigation/actions visible while detailed results scroll."""
    def __init__(self):
        super().__init__()
        self.footer = None

    def set_footer(self, layout):
        self.footer = QFrame(self)
        self.footer.setObjectName("pageFooter")
        layout.setContentsMargins(24, 10, 24, 10)
        self.footer.setLayout(layout)
        self._place_footer()

    def _place_footer(self):
        if self.footer is None:
            return
        height = max(55, self.footer.sizeHint().height())
        if self.viewportMargins().bottom() != height:
            self.setViewportMargins(0, 0, 0, height)
        self.footer.setGeometry(0, self.height() - height, self.width(), height)
        self.footer.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_footer()


class CsvDropZone(QFrame):
    fileDropped = Signal(str)
    chooseRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        body = QVBoxLayout(self)
        body.setContentsMargins(18, 14, 18, 14)
        body.setSpacing(8)
        image = QLabel()
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image.setPixmap(line_icon("upload", "#8b9bb0").pixmap(34, 34))
        body.addWidget(image)
        self.caption = QLabel("拖放 CSV 文件至此，或选择文件")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setWordWrap(True)
        body.addWidget(self.caption)
        choose = QPushButton("选择文件")
        choose.setObjectName("primary")
        icon_button(choose, "folder", True)
        choose.clicked.connect(self.chooseRequested)
        body.addWidget(choose, 0, Qt.AlignmentFlag.AlignCenter)

    @staticmethod
    def csv_path(mime):
        if not mime.hasUrls() or len(mime.urls()) != 1:
            return None
        url = mime.urls()[0]
        path = Path(url.toLocalFile()) if url.isLocalFile() else None
        return path if path and path.is_file() and path.suffix.lower() == ".csv" else None

    def dragEnterEvent(self, event):
        if self.isEnabled() and self.csv_path(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        path = self.csv_path(event.mimeData())
        if self.isEnabled() and path:
            event.acceptProposedAction()
            self.fileDropped.emit(str(path))


class CsvImportDialog(QDialog):
    """Explicit column and unit mapping; never invent assay labels or source."""
    def __init__(self, path, parent=None, initial=None):
        super().__init__(parent)
        self.initial = initial or {}
        from .data import read_import_csv
        self.path = Path(path)
        self.setWindowTitle("导入实验 CSV · 字段与来源")
        self.resize(790, 575)
        self.frame = read_import_csv(self.path, nrows=6)
        if self.frame.empty:
            raise ValueError("CSV 没有数据行。请填写真实实验记录后重新选择文件。")
        self.mapping = {}
        self.source_note = ""
        self.default_unit = None
        layout = QVBoxLayout(self)
        title = QLabel(self.path.name)
        title.setObjectName("section")
        title.setWordWrap(True)
        title.setMaximumHeight(48)
        title.setToolTip(self.path.name)
        layout.addWidget(title)
        hint = QLabel("请对应 SMILES、IC50 与单位字段。仅导入人类 ERα / ESR1 结合活性数据。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        self.fields = {}
        aliases = {
            "smiles": ("canonical_smiles", "SMILES", "smiles"),
            "ic50": ("IC50_nM", "standard_value", "IC50", "ic50"),
            "unit": ("standard_units", "units", "unit", "单位"),
        }
        for row, (key, caption) in enumerate((("smiles", "SMILES 列"), ("ic50", "IC50 列"), ("unit", "单位列"))):
            combo = QComboBox()
            combo.addItem("请选择字段" if key != "unit" else "使用固定单位", "")
            for column in self.frame.columns:
                combo.addItem(str(column), str(column))
            for candidate in aliases[key]:
                index = combo.findData(candidate)
                if index >= 0:
                    combo.setCurrentIndex(index)
                    break
            if self.initial.get("mapping", {}).get(key) in self.frame.columns:
                combo.setCurrentIndex(combo.findData(self.initial["mapping"][key]))
            self.fields[key] = combo
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(combo, row, 1)
        self.unit = QComboBox()
        self.unit.addItems(["nM", "µM", "mM", "M", "pM"])
        if self.initial.get("unit"):
            self.unit.setCurrentText(self.initial["unit"])
        grid.addWidget(QLabel("固定单位"), 2, 2)
        grid.addWidget(self.unit, 2, 3)
        self.fields["unit"].currentIndexChanged.connect(
            lambda _: self.unit.setEnabled(not bool(self.fields["unit"].currentData())))
        self.unit.setEnabled(not bool(self.fields["unit"].currentData()))
        layout.addLayout(grid)
        preview = QTableWidget(len(self.frame), len(self.frame.columns))
        preview.setHorizontalHeaderLabels([str(x) for x in self.frame.columns])
        preview.verticalHeader().hide()
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        preview.horizontalHeader().setStretchLastSection(True)
        preview.setMaximumHeight(190)
        for row in range(len(self.frame)):
            for col in range(len(self.frame.columns)):
                preview.setItem(row, col, QTableWidgetItem(str(self.frame.iloc[row, col])))
        layout.addWidget(preview)
        layout.addWidget(QLabel("数据来源与许可说明（必填）"))
        self.source = QPlainTextEdit()
        self.source.setPlaceholderText("填写实验来源、测定条件或文献编号，以及数据使用许可。")
        self.source.setMaximumHeight(90)
        self.source.setPlainText(self.initial.get("source", ""))
        layout.addWidget(self.source)
        self.error_label = QLabel()
        self.error_label.setObjectName("error")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("导入并清洗")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        mapping = {key: combo.currentData() for key, combo in self.fields.items()}
        chosen = [value for value in mapping.values() if value]
        if not mapping["smiles"] or not mapping["ic50"]:
            self.show_problem("请选择缺失的 SMILES 列或 IC50 列。", self.fields["smiles"] if not mapping["smiles"] else self.fields["ic50"])
            return
        if len(chosen) != len(set(chosen)):
            self.show_problem("SMILES、IC50 和单位必须对应不同的列。", self.fields["ic50"])
            return
        if not self.source.toPlainText().strip():
            self.show_problem("请填写人类 ERα / ESR1 实验数据来源及许可说明。", self.source)
            return
        self.mapping = mapping
        self.default_unit = self.unit.currentText() if not mapping["unit"] else None
        self.source_note = self.source.toPlainText().strip()
        super().accept()

    def show_problem(self, text, widget):
        self.error_label.setText(text)
        self.error_label.show()
        widget.setFocus(Qt.FocusReason.OtherFocusReason)
