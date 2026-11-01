from __future__ import annotations

from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "customer"
OUT.mkdir(parents=True, exist_ok=True)
LOGO = ROOT / "assets" / "logo.png"
TRAINING = ROOT / "docs" / "images" / "training.png"
PREDICTION = ROOT / "docs" / "images" / "prediction.png"
FUNNEL = ROOT / "docs" / "images" / "funnel.png"


def set_cell_shading(cell, fill):
    properties = cell._tc.get_or_add_tcPr()
    shading = properties.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        properties.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_borders(cell, color="D9E2F0", size="6"):
    properties = cell._tc.get_or_add_tcPr()
    borders = properties.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        properties.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_cell_text(cell, text, bold=False, color="18304F"):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run(str(text))
    run.bold = bold
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor.from_string(color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def make_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    if widths:
        for row in table.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Cm(width)
    for index, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[index], header, bold=True, color="FFFFFF")
        set_cell_shading(table.rows[0].cells[index], "1E5EA8")
        set_cell_borders(table.rows[0].cells[index])
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            set_cell_text(cells[index], value)
            set_cell_borders(cells[index])
            set_cell_shading(cells[index], "F5F9FE" if row_index % 2 else "FFFFFF")
            if widths:
                cells[index].width = Cm(widths[index])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def add_heading(doc, text, level=1):
    paragraph = doc.add_heading(text, level=level)
    paragraph.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    paragraph.paragraph_format.space_after = Pt(4)
    for run in paragraph.runs:
        run.font.name = "Microsoft YaHei"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        run.font.color.rgb = RGBColor(0, 0, 0)
    return paragraph


def add_body(doc, text, bold_prefix=None):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.18
    if bold_prefix and text.startswith(bold_prefix):
        first = paragraph.add_run(bold_prefix)
        first.bold = True
        rest = paragraph.add_run(text[len(bold_prefix):])
        runs = (first, rest)
    else:
        runs = (paragraph.add_run(text),)
    for run in runs:
        run.font.name = "Microsoft YaHei"
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(24, 48, 79)
    return paragraph


def add_bullet(doc, text):
    paragraph = doc.add_paragraph(style="List Bullet")
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.line_spacing = 1.12
    run = paragraph.add_run(text)
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(24, 48, 79)
    return paragraph


def add_image(doc, path, width=Inches(6.0), caption=None):
    if not path.exists():
        return
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.add_run().add_picture(str(path), width=width)
    if caption:
        cap = doc.add_paragraph(caption)
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_after = Pt(5)
        for run in cap.runs:
            run.italic = True
            run.font.name = "Microsoft YaHei"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(99, 123, 151)


def configure_document(doc):
    section = doc.sections[0]
    section.top_margin = Cm(1.7)
    section.bottom_margin = Cm(1.6)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal.font.size = Pt(10.5)
    for name, size in (("Title", 22), ("Heading 1", 15), ("Heading 2", 12)):
        style = styles[name]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.font.size = Pt(size)


def build():
    doc = Document()
    configure_document(doc)

    first = doc.add_paragraph()
    first.alignment = WD_ALIGN_PARAGRAPH.CENTER
    first.paragraph_format.space_after = Pt(8)
    if LOGO.exists():
        first.add_run().add_picture(str(LOGO), width=Inches(0.72))

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("乳腺癌药物先导化合物筛选优化平台 使用说明")
    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(14)
    run = subtitle.add_run("Windows版本 0.1.0  |  固定ERα / ESR1  |  训练模型已随安装包提供")
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(99, 123, 151)

    add_body(doc, "本软件用于乳腺癌药物先导化合物的科研前期筛选。程序内置已经训练好的ERα / ESR1活性回归模型，输入化合物SMILES后可以计算pIC50、查看分子结构和三级漏斗状态。")
    add_body(doc, "建议先按本说明完成一次示例预测，再导入自己的化合物数据。软件结果用于初筛参考，不能替代后续实验验证。")

    add_heading(doc, "一 安装软件", 1)
    add_body(doc, "1. 双击安装包，按向导选择安装位置。默认安装到当前用户的本地程序目录，一般不需要管理员权限。")
    add_body(doc, "2. 安装完成后，可以从开始菜单或桌面快捷方式打开软件。安装目录中的运行库、Logo、说明文件和训练模型需要一起保留。")
    add_body(doc, "3. 软件首次启动会自动加载内置模型。正常情况下，状态栏会显示“已加载并校验4个真实模型”。")
    make_table(doc, ["项目", "内容"], [
        ("靶点", "人类ERα / ESR1，固定靶点"),
        ("预测目标", "化合物pIC50活性回归"),
        ("内置模型", "ANN、随机森林、XGBoost、线性回归及GA融合权重"),
        ("安装内容", "Windows程序、运行库、Logo、训练模型、评估报告和使用说明"),
    ], widths=[3.6, 12.4])

    doc.add_page_break()
    add_heading(doc, "二 模型训练页面", 1)
    add_body(doc, "软件已经随包提供一套可直接使用的训练模型。如果要查看训练结果，可以进入左侧“模型训练”页面，再切换到“训练与融合”选项卡。")
    add_bullet(doc, "基础模型表格显示四个回归器的验证集R²、RMSE和MAE。")
    add_bullet(doc, "融合优化表格显示GA、SA、TS三种算法搜索出的四模型权重。")
    add_bullet(doc, "独立测试结果区域显示冻结融合方案后的测试集指标。")
    add_bullet(doc, "“数据与清洗”页面可以重新获取ChEMBL公开数据，或导入有来源的ERα实验CSV；重新训练会生成新的模型版本和报告。")
    add_image(doc, TRAINING, width=Inches(6.35), caption="模型训练与融合页面示例")
    add_body(doc, "内置训练版本使用ChEMBL人类ESR1相关IC50记录，经过SMILES标准化、精确IC50筛选、pIC50转换和结构分组拆分。重新训练时请保留数据来源和实验条件说明。")

    doc.add_page_break()
    add_heading(doc, "三 分子预测", 1)
    add_body(doc, "1. 点击左侧“分子预测”，在SMILES输入框中输入化合物结构字符串。界面中的示例按钮只用于演示，输入可以替换为自己的化合物。")
    add_body(doc, "2. 点击“开始真实预测”。程序会校验SMILES，绘制RDKit二维结构，并显示四个模型的pIC50、融合pIC50和融合权重。")
    add_body(doc, "3. 如果SMILES无效，程序会提示输入错误，不会生成伪造的预测结果。")
    add_body(doc, "示例SMILES（可直接复制）：C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")
    make_table(doc, ["界面区域", "说明"], [
        ("RDKit二维分子结构", "根据当前输入实时绘制，输入变化后旧结果会清除"),
        ("真实活性预测", "显示ANN、RF、XGBoost、LR和融合pIC50"),
        ("模型融合权重", "显示当前训练版本的GA融合权重"),
        ("阶段1状态", "pIC50默认以6.0作为活性硬底线"),
    ], widths=[4.1, 11.9])
    add_image(doc, PREDICTION, width=Inches(6.35), caption="分子预测页面示例")

    doc.add_page_break()
    add_heading(doc, "四 三级漏斗与参数调控", 1)
    add_body(doc, "软件按照客户确认的精简范围显示三级筛选流程。每一阶段都显示输入、判定、状态、输出和流转。")
    make_table(doc, ["阶段", "当前实现", "状态含义"], [
        ("阶段1 活性", "使用真实回归模型预测pIC50", "通过或活性不达标淘汰"),
        ("阶段2 ADMET", "显示5项门槛和流程位置；本版本未训练5个ADMET模型", "缺少真实数据时为未评估"),
        ("阶段3 结构/理化", "显示67项约束统计入口和流转规则；本版本未训练67输出模型", "缺少完整外部证据时为未评估"),
    ], widths=[3.2, 8.4, 4.4])
    add_body(doc, "勾选“启用明确标注的流程演示数据”后，可以演示阶段2/3的通过、复核和淘汰流转。演示数据会明确标注为流程演示，不代表真实ADMET或67项结构预测结论。")
    add_body(doc, "活性门槛只能在6.0以上调整，不能降低硬性底线。阶段权重默认是活性0.40、ADMET0.35、结构0.25；奖励系数、惩罚系数和门槛调整后会立即重新计算。")
    add_image(doc, FUNNEL, width=Inches(6.35), caption="三级漏斗默认缺测状态示例")

    doc.add_page_break()
    add_heading(doc, "五 结果导出", 1)
    add_body(doc, "预测完成后，页面底部提供CSV和JSON导出。导出结果包含输入SMILES、模型版本、数据哈希、四模型预测、融合权重、阶段状态、规则参数和演示标记，便于后续追溯。")
    add_body(doc, "训练页面可以导出模型、训练报告、数据审计和评估资料。导出的模型文件应与对应的报告和版本目录一起保存。")

    add_heading(doc, "六 常见问题", 1)
    make_table(doc, ["现象", "处理方法"], [
        ("提示SMILES无效", "确认输入的是完整化学结构字符串，不要直接输入化合物名称、CAS号或ChEMBL编号。"),
        ("提示尚无模型", "确认安装目录中的seed_models文件夹完整存在；不要只复制单个EXE。"),
        ("阶段2/3显示未评估", "这是默认科学边界。没有真实测量或完整外部证据时，软件不会用0分或满分代替。"),
        ("预测结果需要对外使用", "先保存JSON/CSV，再结合实验条件、数据来源和后续实验进行复核。"),
        ("重新训练后想恢复原版本", "保留原模型版本目录和对应报告，通过模型目录加载功能选择已验证版本。"),
    ], widths=[5.2, 10.8])

    add_heading(doc, "七 使用边界", 1)
    add_body(doc, "本软件用于科研前期初筛。模型训练来自公开化合物活性记录，实际表现会受实验测定条件、分子结构范围和输入数据质量影响。阶段2的5项ADMET模型、阶段3的67项多输出模型和临床结论不属于本版本的真实训练范围。")
    add_body(doc, "软件版本：0.1.0。内置训练版本：v0.1.0-71dee9e63f35-s42。")

    footer = doc.sections[0].footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("乳腺癌药物先导化合物筛选优化平台")
    run.font.name = "Microsoft YaHei"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(120, 120, 120)

    output = OUT / "客户使用说明.docx"
    doc.save(output)
    print(output)


if __name__ == "__main__":
    build()
