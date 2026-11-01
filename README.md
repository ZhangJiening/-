# 乳腺癌药物先导化合物筛选优化平台

Windows本地科研初筛程序，版本0.1.0。靶点固定人类ERα / ESR1，使用真实化合物结合IC50记录训练ANN、RF、XGBoost、LR回归器，并用GA、SA、TS优化融合权重。三级漏斗与可配置奖惩独立于四模型融合；阶段2/3缺测时显示未评估。

## 直接使用Windows程序

推荐使用 `release/installer/ERLeadPlatform-Setup-0.1.0.exe` 安装。安装向导会复制完整运行库、Logo、使用说明和已经训练好的模型，并创建开始菜单入口。也可以使用Windows-x64便携包：完整解压后打开文件夹内的 `ERLeadPlatform.exe`。保留同目录的 `_internal`、`seed_models`、许可和说明文件；不能只拷贝EXE。

客户转发文件：`docs/customer/ERLeadPlatform-User-Guide.pdf`（PDF）和 `docs/customer/ERLeadPlatform-User-Guide.docx`（可编辑Word）。安装后，使用说明位于安装目录的 `docs/customer` 文件夹，开始菜单也会提供PDF入口。

源码上传自己的GitHub仓库及配合已训练模型的步骤见 [GitHub上传说明](docs/GITHUB_UPLOAD.md)。

1. 在“分子预测”输入SMILES，或点击“载入结构示例”，再点“开始真实预测”。查看分子图、四模型数值和融合pIC50。
2. 默认阶段2/3未评估，不生成完整综合分。需要演示流转时，主动勾选“启用明确标注的流程演示数据”；界面和导出结果均保留演示标识。
3. 调整门槛、阶段权重、ADMET阈值及奖惩系数后立即重算；三个阶段权重必须非负且和为1。可保存快照或恢复默认。
4. “数据导入与清洗”可以从ChEMBL下载，也可以导入有来源的ERα实验CSV；随后到“模型训练”执行真实训练与三种优化。
5. 预测可导出CSV/JSON，训练资料可连同模型、评估和来源一起导出。

便携版新下载的数据、参数及训练结果写入 `%LOCALAPPDATA%\ERLeadPlatform`。随包示例模型保留在 `seed_models`；新训练完成后优先加载新版本。源码版默认在本工程内保存产物。可用 `ERLEAD_WORKSPACE` 或命令行 `--workspace` 指定独立数据目录。程序Logo位于 `assets/logo.svg`，同一图形同时用于页眉、窗口和EXE图标。

## 源码运行和复现

已核验Python 3.12.10、Windows 11 x64；锁定依赖见 `requirements.lock.txt`。在本工程目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m erlead.cli prepare
.\.venv\Scripts\python.exe -m erlead.cli train
.\.venv\Scripts\python.exe -m erlead.cli gui
```

创建环境后也可双击 `启动平台.cmd`。命令行预测与自检：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli predict --smiles "CCO" --output reports/prediction.json
.\.venv\Scripts\python.exe -m erlead.cli self-test --output reports/self-test.json
.\.venv\Scripts\python.exe -m erlead.cli desktop-test --output reports/desktop-test.json
.\.venv\Scripts\python.exe -m pytest -q --junitxml=reports/tests.xml
```

没有模型时，涉及真实模型的集成测试会标记跳过；执行prepare/train后再运行全套测试。模型文件使用joblib，只加载本项目或其他可信来源的训练产物。错误会显示在界面运行记录，训练异常另存到模型目录日志；未完成的训练不会替换当前模型。

## 真实数据与实验方法

官方入口：https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL206.json 。已核对人类ESR1、P03372和单蛋白目标。默认筛选结合测定B、靶点置信度9，排除非人类或带变异序列的测定。保留原始JSON、查询条件、数据库版本、下载时间和SHA256。数据许可和署名见 `THIRD_PARTY_NOTICES.md`。

清洗只保留精确“=”且正有限值的IC50，统一M/mM/µM/nM/pM后按 `pIC50 = 9 - log10(IC50[nM])` 转换。RDKit执行Cleanup、主片段提取和中和；按标准化立体SMILES合并重复测定，取pIC50中位数；同分子重复测定跨度超过1个log单位时整组排除。排除原因和记录ID写入 `data/processed/rejections.csv`。

特征为半径2的Morgan1024位手性指纹及8项理化描述符。同一Murcko骨架或Morgan2048 Tanimoto相似度≥0.85的分子合并为结构组，再用固定种子42进行约70/15/15的训练/验证/测试拆分。标准化仅拟合训练集；不跨集合共享结构组。至少需要60个有效化合物、10个结构组，各集合至少10个样本且标签有变化。

ANN使用MLP回归及训练集合内部的早停；RF、XGBoost、LR独立拟合。GA、SA、TS只使用同一验证集预测搜索非负且和为1的权重，按验证MSE选定方案后执行一次独立测试。所有参数、索引和搜索历史可查。相同数据、版本和种子的完整运行会加载缓存，不再次使用测试集搜索。进入测试阶段后若异常中断，会停止自动重跑并要求检查日志。

本次实验：7343条原始记录，2471个有效化合物，791个结构组；训练1724、验证414、测试333。融合方案GA，独立测试R²=0.6996、RMSE=0.8476、MAE=0.6463。XGBoost单模型R²=0.7139，ANN及LR测试R²为负值。结果全部保留，不保证融合优于单模型。详细证据见 `docs/VALIDATION.md`。

## 导入格式

CSV至少包含 `SMILES,IC50_nM`，或 `canonical_smiles,standard_value,standard_units`。也识别 `smiles`、`IC50`、`units`、`relation`。没有明确单位的IC50列会拒绝；缺少relation时按用户声明的精确测定处理。可提供 `target_chembl_id`、`standard_type`、`assay_type`、`target_organism`，给出时必须匹配当前任务。来源说明必须填写；自带数据的实验条件和授权由提供方核验。导入原件按文件哈希另存，避免来源丢失。

真实阶段2/3证据JSON需要与当前分子一致的 `canonical_smiles` 和可追溯的 `evidence` 来源/模型版本说明。`admet`须完整包含logS、F_percent、PPB_percent、hepatotoxic、CYP3A4_inhibitor；前3项为数值、后2项为布尔。`structure`如提供，须为67项布尔判定，并附67项不同的 `constraint_definitions`。未提供的阶段保持未评估。软件不替代对外部证据的科研审查。

## 评分与范围

详见 `docs/SCORING.md`。阶段1硬底线6.0不可调低；示例化合物只提供结构，数值来自实际模型。没有训练5个ADMET模型或67输出模型，不输出虚构置信度、ADMET友好性或完整科研结论。多测定异质性和新化学空间仍会影响泛化；本软件用于科研初筛，需实验验证。

## 打包与目录

执行 `build_windows.ps1` 生成 `dist/ERLeadPlatform` 和带校验清单的 `release` 压缩包。打包后执行：

```powershell
.\dist\ERLeadPlatform\ERLeadPlatform.exe self-test --output reports/frozen-self-test.json
.\dist\ERLeadPlatform\ERLeadPlatform.exe desktop-test --output reports/frozen-desktop-test.json
```

`src/erlead`为实现；`tests`为规则与桌面测试；`models/<版本>`为4个模型、融合权重、配置和日志；`reports/<版本>`为评估、固定拆分和预测；`scripts`为检查及发行工具。

源码采用MIT许可。GitHub候选源码包不含客户资料、对话、账户、原始数据或模型权重；依赖和数据各自许可见第三方说明。发布到外部仓库与客户最终验收单独记录。
