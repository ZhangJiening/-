# 乳腺癌药物先导化合物筛选优化平台

版本 0.1.8。面向人类雌激素受体 ERα / ESR1 的 Windows 科研初筛软件，包含数据清洗、活性回归、融合优化、分子预测、分阶段证据评估和结果导出。

软件内置 ANN、随机森林（RF）、XGBoost 和线性回归（LR）活性模型。阶段 2/3 依赖外部 ADMET 或结构证据；缺少证据时显示“未评估”，不生成完整综合评分。

## 功能

- 从 ChEMBL 获取人类 ESR1 活性数据，或导入实验 CSV。
- 使用 RDKit 标准化结构、统一 IC50 单位并生成 pIC50 标签。
- 训练四种回归模型，并在验证集上比较 GA、SA、TS 融合方案。
- 根据 SMILES 预测活性，展示结构、模型结果和三级筛选状态。
- 导出分子筛选结果和模型评估报告。

## 源码运行

需要 Windows x64 与 Python 3.12。安装依赖并启动桌面程序：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m erlead.cli gui
```

源码仓库不包含训练数据和模型权重。首次获取公开数据并训练模型：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli prepare
.\.venv\Scripts\python.exe -m erlead.cli train
```

运行产物默认保存在项目工作目录，可通过 `ERLEAD_WORKSPACE` 或 `--workspace` 参数指定其他目录。命令行预测示例：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli predict --smiles "CCO" --output reports/prediction.json
```

## 数据与方法

数据来自 ChEMBL 人类 ESR1 靶点 CHEMBL206（UniProt P03372）。默认筛选直接结合测定、靶点置信度 9、精确 IC50 记录，并排除非人类或带变异序列的测定。数据来源与许可说明见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

IC50 单位统一后，按 `pIC50 = 9 - log10(IC50[nM])` 转换。RDKit 执行结构清理、主片段提取和中和；Morgan 半径 2 的 1024 位指纹与 8 项理化描述符作为模型特征。按结构组隔离训练、验证和独立测试集，随机种子为 42。

当前验证记录包含 7,343 条原始记录、2,471 个有效化合物和 791 个结构组。完整数据划分、指标及适用范围见 [模型验证记录](docs/VALIDATION.md)。三级筛选规则见 [筛选规则](docs/SCORING.md)。

模型只预测活性回归结果，不内置 ADMET 或 67 项结构规则预测模型。模型预测用于科研初筛，仍需实验验证。

## 测试与 Windows 构建

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m erlead.cli self-test --output reports/self-test.json
.\.venv\Scripts\python.exe -m erlead.cli desktop-test --output reports/desktop-test.json
```

Windows 程序构建入口为 `build_windows.ps1`，安装包构建入口为 `build_installer.ps1`。模型推理测试需要已生成或提供可信的模型文件。

使用说明见 [项目使用指南](docs/user-guide/使用说明-0.1.8.md)，实验数据模板见 [CSV 模板](docs/user-guide/ERalpha-IC50-导入模板.csv)。

## 许可证

项目源码采用 MIT 许可证。ChEMBL 数据及第三方组件适用各自许可，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
