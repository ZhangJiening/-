# 乳腺癌药物先导化合物筛选优化平台

面向人类雌激素受体 ERα / ESR1 的化合物活性预测与科研初筛工具，提供数据清洗、模型训练、融合优化、分子预测和分阶段评估的 Windows 桌面界面。

## 主要功能

- **数据处理**：从 ChEMBL 获取 ESR1 结合活性记录，或导入带来源说明的实验 CSV；完成单位统一、分子标准化、去重及冲突记录排除。
- **活性建模**：使用 ANN、随机森林（RF）、XGBoost 和线性回归（LR）预测 pIC50。
- **模型融合**：使用遗传算法（GA）、模拟退火（SA）和禁忌搜索（TS）在验证集上优化融合权重。
- **分子预测**：输入 SMILES，展示二维结构、理化描述符、各模型预测和融合结果。
- **分阶段评估**：结合活性预测、外部 ADMET 证据和结构规则判定，显示各阶段状态及评分。
- **结果导出**：导出预测 CSV/JSON，以及模型、参数、评估和数据来源资料。

## 环境与安装

Python 3.12；桌面界面基于 PySide6/Qt，分子处理使用 RDKit。依赖版本见 [requirements.lock.txt](requirements.lock.txt)。

在项目根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
```

## 快速开始

首次使用可先获取数据并训练模型，再启动界面：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli prepare
.\.venv\Scripts\python.exe -m erlead.cli train
.\.venv\Scripts\python.exe -m erlead.cli gui
```

安装依赖后也可双击 `启动平台.cmd`。已有模型时，可在界面选择“加载模型目录”；模型版本目录应包含 `report.json` 和对应的四个 joblib 模型文件。

命令行预测示例：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli predict --smiles "CCO" --output reports/prediction.json
```

源码仓库不包含训练数据、模型权重或安装包。`prepare` 获取数据，`train` 生成模型。默认在项目目录保存运行产物，可通过 `ERLEAD_WORKSPACE` 环境变量或 `--workspace` 参数指定工作目录。

## 数据与方法

数据来自 ChEMBL 的人类 ESR1 靶点（CHEMBL206，UniProt P03372）。默认筛选直接结合测定、靶点置信度 9、精确且为正有限值的 IC50 记录，并排除非人类或带变异序列的测定。

- **标签转换**：统一 IC50 单位后，按 `pIC50 = 9 - log10(IC50[nM])` 计算。
- **分子标准化**：RDKit Cleanup、主片段提取和中和；按标准化立体 SMILES 合并重复测定，取 pIC50 中位数；跨度超过 1 个 log 单位的重复测定组排除。
- **分子特征**：半径 2 的 1024 位 Morgan 手性指纹与 8 项理化描述符。
- **数据拆分**：按 Murcko 骨架及指纹相似性建立结构组，以固定种子 42 划分训练、验证和测试集，避免结构组跨集合。
- **融合选择**：四模型权重非负且总和为 1，仅在验证集优化；选定方案后进行独立测试。

## 模型评估

以下为随项目记录的实验结果；重新获取数据或训练后的指标可能不同。共 7,343 条原始记录、2,471 个有效化合物和 791 个结构组；训练、验证、独立测试样本数分别为 1,724、414、333。

| 独立测试模型 | R² | RMSE | MAE |
|---|---:|---:|---:|
| ANN | -0.0504 | 1.5850 | 1.2173 |
| RF | 0.6961 | 0.8526 | 0.6539 |
| XGBoost | 0.7139 | 0.8273 | 0.6485 |
| LR | -0.1360 | 1.6484 | 1.2713 |
| GA 融合 | 0.6996 | 0.8476 | 0.6463 |

本次融合模型的测试 R² 未超过 XGBoost。完整实验记录见 [模型验证](docs/VALIDATION.md)，机器可读指标见 [validation_summary.json](docs/validation_summary.json)。

## 数据导入与评估范围

实验 CSV 支持 `SMILES,IC50_nM`，或 `canonical_smiles,standard_value,standard_units` 等字段。IC50 必须有明确单位；导入时需填写来源说明。

当前内置模型用于活性回归。ADMET 和 67 项结构规则评估依赖外部证据，未内置对应预测模型。外部证据 JSON 需包含匹配当前分子的 `canonical_smiles` 和可追溯的 `evidence`；缺少证据的阶段保持“未评估”，不生成完整综合分。演示数据仅用于展示流程，结果保留演示标识。

阶段权重、阈值、评分及奖惩规则见 [筛选规则](docs/SCORING.md)。本工具用于科研初筛，模型预测仍需实验验证。

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m erlead.cli self-test --output reports/self-test.json
.\.venv\Scripts\python.exe -m erlead.cli desktop-test --output reports/desktop-test.json
```

涉及模型的集成测试需要已训练模型。Windows 构建入口为 `build_windows.ps1`，安装程序构建入口为 `build_installer.ps1`。

## 项目结构

```text
src/erlead/               数据处理、建模、筛选与桌面界面
tests/                    自动测试
assets/                   图标与标识
docs/                     使用说明、筛选规则与验证记录
scripts/                  文档、验证与构建工具
models/                   运行时生成的模型与配置
reports/                  运行时生成的评估与预测结果
```

## 许可证

源码采用 [MIT 许可证](LICENSE)。ChEMBL 数据及第三方组件的署名、许可和使用说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
