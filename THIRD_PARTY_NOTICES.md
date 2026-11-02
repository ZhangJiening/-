# 数据和第三方组件说明

数据来源为EMBL-EBI ChEMBL，目标CHEMBL206，人类ESR1，蛋白P03372。ChEMBL数据库采用CC BY-SA 3.0许可：
https://chembl.gitbook.io/chembl-interface-documentation/about
https://creativecommons.org/licenses/by-sa/3.0/

原始数据、清洗衍生数据的再分发须保留ChEMBL署名及相同许可。本项目的示例训练产物附带同样的数据来源、改动和CC BY-SA 3.0标注；源码MIT许可不覆盖第三方数据或第三方库。公开源码包默认不包含数据及模型，提供官方获取和清洗脚本。

主要组件（以发行包附带的原始许可为准）：RDKit BSD 3-Clause；NumPy、SciPy、pandas、scikit-learn BSD；XGBoost Apache-2.0；joblib BSD；Pillow MIT-CMU；PySide6/Qt LGPLv3或商业许可；PyInstaller GPL附带bootloader例外。

Windows发行版使用动态链接的PySide6/Qt，库和插件保留为独立DLL，随包附带各发行组件许可文本、版本和来源指引，允许按其许可替换相应库；未修改Qt源码。Qt源码获取及许可：
https://code.qt.io/cgit/qt/
https://www.qt.io/licensing/open-source-lgpl-obligations
https://doc.qt.io/qtforpython-6/licenses.html

训练方法：Morgan指纹、常规监督回归、遗传算法、模拟退火和禁忌搜索。方法不声称原创；具体工程实现由本项目独立编写。原始测定经过直接结合/靶点置信度/精确IC50筛选、RDKit标准化、重复测定中位数聚合与冲突排除。每次运行的source、audit、split与report保存具体来源和改动。
