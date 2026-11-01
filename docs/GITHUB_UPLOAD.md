# GitHub源码上传与模型使用说明

适用于乳腺癌药物先导化合物筛选优化平台0.1.0。此文件说明接收源码后如何上传到自己的GitHub仓库，以及如何配合已训练模型使用。

## 一 上传哪些内容

解压“GitHub源码包.zip”，进入 `erlead-platform` 文件夹。该文件夹是仓库根目录，包含：

- `src/erlead/`：数据获取与清洗、RDKit特征、四模型训练、三种融合优化、三级漏斗和桌面界面代码。
- `tests/`：规则、模型证据和桌面集成测试。
- `assets/`：Logo与Windows图标。
- `scripts/`、`build_windows.ps1`、`build_installer.ps1`：检查、打包和安装向导构建文件。
- `requirements.lock.txt`、`pyproject.toml`、`run.py`：依赖版本和启动入口。
- `README.md`、`docs/`、`LICENSE`、`THIRD_PARTY_NOTICES.md`：运行复现步骤、使用说明、实际指标、源码许可和第三方说明。

GitHub上传范围为 `erlead-platform` 里面的文件和目录。完整客户交付ZIP用于收件，其中的安装包和模型包分别保存。

## 二 在自己的GitHub账号下上传

1. 登录自己的GitHub账号，新建项目仓库，按开源计划设置可见性。源码已包含README、MIT LICENSE和.gitignore。
2. 打开新仓库，选择 `Add file` → `Upload files`；空仓库也可使用上传已有文件的入口。
3. 将解压后的 `erlead-platform` 文件夹里面的文件和目录上传，保留层级。上传后，仓库根目录应能直接看到 `README.md`、`src`、`assets`、`requirements.lock.txt`、`pyproject.toml` 和 `.gitignore`。
4. 填写提交说明，按GitHub页面提示保存提交。仓库首页应能显示README和完整源文件。

完整源文件应作为仓库内容上传。仅在仓库放一个源码ZIP，别人仍需额外解压才能查看和运行。

官方操作说明：<https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository>

## 三 配合已训练模型使用

完整交付ZIP中的“训练模型包.zip”包含四个joblib模型、融合配置、模型报告、训练日志、拆分索引和许可说明。源码和训练模型分别打包。

1. 按README创建Python 3.12环境并安装锁定依赖。
2. 将模型包解压得到的 `models` 文件夹合并到源码仓库根目录，使模型索引位于 `erlead-platform/models/current.json`。
3. 在源码根目录执行：

```powershell
.\.venv\Scripts\python.exe -m erlead.cli gui
```

也可在界面点击“加载模型目录”，选择包含 `report.json` 和四个joblib文件的模型版本目录。需要完整复现训练时，执行README中的prepare、train命令；该流程从ChEMBL获取真实数据并保存审计和评估。

## 四 模型及数据的分发

源码采用MIT许可；ChEMBL数据及相关训练产物的来源、署名和许可见 `THIRD_PARTY_NOTICES.md`。本源码仓库的.gitignore默认排除原始数据、模型权重、本地环境、构建产物和运行日志。

如需在GitHub同时提供训练产物，可将独立模型包作为Release附件，保留模型包内的使用和许可说明。发布者负责按第三方许可保留相应署名。

当前版本的真实训练范围是ERα/ESR1活性回归：ANN、RF、XGBoost、LR及GA/SA/TS融合权重优化。阶段2/3按约定呈现未评估或明确标注的流程演示。
