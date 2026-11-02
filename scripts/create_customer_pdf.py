from __future__ import annotations

from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "customer"
OUT.mkdir(parents=True, exist_ok=True)
FONT = Path("C:/Windows/Fonts/simhei.ttf")
pdfmetrics.registerFont(TTFont("SimHei", str(FONT)))

BLUE = colors.HexColor("#1E5EA8")
TEXT = colors.HexColor("#18304F")
MUTED = colors.HexColor("#637B97")
LIGHT = colors.HexColor("#F5F9FE")

styles = getSampleStyleSheet()
title = ParagraphStyle("GuideTitle", parent=styles["Title"], fontName="SimHei", fontSize=21, leading=29, alignment=TA_CENTER, textColor=colors.black, spaceAfter=8)
subtitle = ParagraphStyle("GuideSubtitle", parent=styles["Normal"], fontName="SimHei", fontSize=10.5, leading=16, alignment=TA_CENTER, textColor=MUTED, spaceAfter=14)
h1 = ParagraphStyle("GuideH1", parent=styles["Heading1"], fontName="SimHei", fontSize=15, leading=22, textColor=colors.black, spaceBefore=8, spaceAfter=6)
body = ParagraphStyle("GuideBody", parent=styles["BodyText"], fontName="SimHei", fontSize=10, leading=16, textColor=TEXT, spaceAfter=6)
bullet = ParagraphStyle("GuideBullet", parent=body, leftIndent=14, firstLineIndent=-10, bulletIndent=0, spaceAfter=3)
caption = ParagraphStyle("GuideCaption", parent=body, fontSize=8.5, leading=12, alignment=TA_CENTER, textColor=MUTED, spaceAfter=5)
small = ParagraphStyle("GuideSmall", parent=body, fontSize=8.7, leading=13)


def P(text, style=body):
    return Paragraph(text, style)


def table(headers, rows, widths):
    data = [[P(f"<b>{x}</b>", ParagraphStyle("th", parent=small, textColor=colors.white)) for x in headers]]
    for row in rows:
        data.append([P(str(x), small) for x in row])
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#D9E2F0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def screenshot(path, caption_text):
    image = Image(str(path))
    image.drawWidth = 16.6 * cm
    image.drawHeight = image.drawWidth * 940 / 1320
    return [image, P(caption_text, caption)]


def page_frame(canvas, doc):
    canvas.saveState()
    canvas.setFont("SimHei", 8)
    canvas.setFillColor(colors.HexColor("#808080"))
    canvas.drawCentredString(A4[0] / 2, 0.85 * cm, "乳腺癌药物先导化合物筛选优化平台")
    canvas.restoreState()


def build():
    output = OUT / "客户使用说明.pdf"
    doc = SimpleDocTemplate(str(output), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.65 * cm, bottomMargin=1.35 * cm, title="乳腺癌药物先导化合物筛选优化平台 使用说明", author="乳腺癌药物先导化合物筛选优化平台")
    story = []
    logo = ROOT / "assets" / "logo.png"
    if logo.exists():
        logo_image = Image(str(logo), width=1.65 * cm, height=1.65 * cm)
        logo_table = Table([[logo_image]], colWidths=[1.65 * cm], hAlign="CENTER")
        logo_table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story += [logo_table, Spacer(1, 0.15 * cm)]
    story += [P("乳腺癌药物先导化合物筛选优化平台 使用说明", title), P("Windows版本 0.1.0  |  固定ERα / ESR1  |  训练模型已随安装包提供", subtitle)]
    story += [P("本软件用于乳腺癌药物先导化合物的科研前期筛选。程序内置已经训练好的ERα / ESR1活性回归模型，输入化合物SMILES后可以计算pIC50、查看分子结构和三级漏斗状态。"), P("建议先按本说明完成一次示例预测，再导入自己的化合物数据。软件结果用于初筛参考，不能替代后续实验验证。")]
    story += [P("一 安装软件", h1), P("1. 双击安装包，按向导选择安装位置。默认安装到当前用户的本地程序目录，一般不需要管理员权限。"), P("2. 安装完成后，可以从开始菜单或桌面快捷方式打开软件。安装目录中的运行库、Logo、说明文件和训练模型需要一起保留。"), P("3. 软件首次启动会自动加载内置模型。正常情况下，状态栏会显示“已加载并校验4个真实模型”。")]
    story += [table(["项目", "内容"], [("靶点", "人类ERα / ESR1，固定靶点"), ("预测目标", "化合物pIC50活性回归"), ("内置模型", "ANN、随机森林、XGBoost、线性回归及GA融合权重"), ("安装内容", "Windows程序、运行库、Logo、训练模型、评估报告和使用说明")], [3.6, 12.4]), PageBreak()]
    story += [P("二 模型训练页面", h1), P("软件已经随包提供一套可直接使用的训练模型。如果要查看训练结果，可以进入左侧“模型训练”页面，再切换到“训练与融合”选项卡。")]
    story += [P("• 基础模型表格显示四个回归器的验证集R²、RMSE和MAE。", bullet), P("• 融合优化表格显示GA、SA、TS三种算法搜索出的四模型权重。", bullet), P("• 独立测试结果区域显示冻结融合方案后的测试集指标。", bullet), P("• “数据与清洗”页面可以重新获取ChEMBL公开数据，或导入有来源的ERα实验CSV；重新训练会生成新的模型版本和报告。", bullet)]
    story += screenshot(ROOT / "docs" / "images" / "training.png", "模型训练与融合页面示例")
    story += [P("内置训练版本使用ChEMBL人类ESR1相关IC50记录，经过SMILES标准化、精确IC50筛选、pIC50转换和结构分组拆分。重新训练时请保留数据来源和实验条件说明。"), PageBreak()]
    story += [P("三 分子预测", h1), P("1. 点击左侧“分子预测”，在SMILES输入框中输入化合物结构字符串。界面中的示例按钮只用于演示，输入可以替换为自己的化合物。"), P("2. 点击“开始真实预测”。程序会校验SMILES，绘制RDKit二维结构，并显示四个模型的pIC50、融合pIC50和融合权重。"), P("3. 如果SMILES无效，程序会提示输入错误，不会生成伪造的预测结果。"), P("示例SMILES（可直接复制）：C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc43)[C@@H]1CC[C@@H]2O")]
    story += [table(["界面区域", "说明"], [("RDKit二维分子结构", "根据当前输入实时绘制，输入变化后旧结果会清除"), ("真实活性预测", "显示ANN、RF、XGBoost、LR和融合pIC50"), ("模型融合权重", "显示当前训练版本的GA融合权重"), ("阶段1状态", "pIC50默认以6.0作为活性硬底线")], [4.1, 11.9])]
    story += screenshot(ROOT / "docs" / "images" / "prediction.png", "分子预测页面示例") + [PageBreak()]
    story += [P("四 三级漏斗与参数调控", h1), P("软件提供三级筛选流程。每一阶段都显示输入、判定、状态、输出和流转。")]
    story += [table(["阶段", "当前实现", "状态含义"], [("阶段1 活性", "使用真实回归模型预测pIC50", "通过或活性不达标淘汰"), ("阶段2 ADMET", "显示5项门槛和流程位置；本版本未训练5个ADMET模型", "缺少真实数据时为未评估"), ("阶段3 结构/理化", "显示67项约束统计入口和流转规则；本版本未训练67输出模型", "缺少完整外部证据时为未评估")], [3.2, 8.4, 4.4]), P("勾选“启用明确标注的流程演示数据”后，可以演示阶段2/3的通过、复核和淘汰流转。演示数据会明确标注为流程演示，不代表真实ADMET或67项结构预测结论。"), P("活性门槛只能在6.0以上调整，不能降低硬性底线。阶段权重默认是活性0.40、ADMET0.35、结构0.25；奖励系数、惩罚系数和门槛调整后会立即重新计算。")]
    story += screenshot(ROOT / "docs" / "images" / "funnel.png", "三级漏斗默认缺测状态示例") + [PageBreak()]
    story += [P("五 结果导出", h1), P("预测完成后，页面底部提供CSV和JSON导出。导出结果包含输入SMILES、模型版本、数据哈希、四模型预测、融合权重、阶段状态、规则参数和演示标记，便于后续追溯。"), P("训练页面可以导出模型、训练报告、数据审计和评估资料。导出的模型文件应与对应的报告和版本目录一起保存。"), P("六 常见问题", h1)]
    story += [table(["现象", "处理方法"], [("提示SMILES无效", "确认输入的是完整化学结构字符串，不要直接输入化合物名称、CAS号或ChEMBL编号。"), ("提示尚无模型", "确认安装目录中的seed_models文件夹完整存在；不要只复制单个EXE。"), ("阶段2/3显示未评估", "这是默认科学边界。没有真实测量或完整外部证据时，软件不会用0分或满分代替。"), ("预测结果需要对外使用", "先保存JSON/CSV，再结合实验条件、数据来源和后续实验进行复核。"), ("重新训练后想恢复原版本", "保留原模型版本目录和对应报告，通过模型目录加载功能选择已验证版本。")], [5.2, 10.8]), P("七 使用边界", h1), P("本软件用于科研前期初筛。模型训练来自公开化合物活性记录，实际表现会受实验测定条件、分子结构范围和输入数据质量影响。阶段2的5项ADMET模型、阶段3的67项多输出模型和临床结论不属于本版本的真实训练范围。"), P("软件版本：0.1.0。内置训练版本：v0.1.0-71dee9e63f35-s42。")]
    doc.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    print(output)


if __name__ == "__main__":
    build()
