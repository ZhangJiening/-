from pathlib import Path
import json
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

project = Path(SPECPATH).parent
datas = collect_data_files('rdkit') + collect_data_files('xgboost')
datas += [(str(project / 'assets'), 'assets')]
for package in ('rdkit', 'scikit-learn', 'numpy', 'pandas', 'joblib', 'xgboost'):
    datas += copy_metadata(package)
binaries = collect_dynamic_libs('rdkit') + collect_dynamic_libs('xgboost')

a = Analysis([str(project / 'run.py')], pathex=[str(project / 'src')],
             binaries=binaries, datas=datas, hiddenimports=[], hookspath=[],
             hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False, optimize=0)

# Qt 6 on the supported Windows 11 environment uses the OS ICU API (unversioned
# ucnv_* exports). PATH may also contain Poppler/Conda's incompatible icuuc.dll
# with version-suffixed exports. Never shadow the Windows system component.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != 'icuuc.dll']
allowed_roots = [Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve(), Path(os.environ['SystemRoot']).resolve()]
foreign = [(name, source) for name, source, kind in a.binaries
           if not any(Path(source).resolve().is_relative_to(root) for root in allowed_roots)]
if foreign:
    raise RuntimeError('Unexpected binary sources outside the isolated build environment: ' + repr(foreign))
(project / 'reports').mkdir(exist_ok=True)
(project / 'reports/binary-source-check.json').write_text(json.dumps({'status': 'passed', 'binary_count': len(a.binaries), 'foreign_binaries': foreign}), encoding='utf-8')
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='ERLeadPlatform', icon=str(project / 'assets' / 'app.ico'),
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='ERLeadPlatform')
