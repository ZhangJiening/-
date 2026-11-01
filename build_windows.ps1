$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
$taskBasePython = & $taskPython -X utf8 -c "import sys; print(sys.base_prefix)"
$taskOriginalPath = $env:PATH
try {
    $env:PATH = @((Split-Path -Parent $taskPython), $taskBasePython, (Join-Path $taskBasePython 'DLLs'), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
    & $taskPython -X utf8 -m PyInstaller --noconfirm --clean scripts\windows.spec
    $taskBuildExit = $LASTEXITCODE
} finally {
    $env:PATH = $taskOriginalPath
}
if ($taskBuildExit -ne 0) { throw 'PyInstaller build failed' }
& $taskPython -X utf8 scripts\release.py
if ($LASTEXITCODE -ne 0) { throw 'Release assembly failed' }
