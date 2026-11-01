$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$taskScript = Join-Path $taskRoot 'scripts\ERLeadPlatform.iss'
$taskCompiler = $null
$taskCandidates = @($env:INNO_SETUP_COMPILER, (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'), 'C:\Program Files\Inno Setup 6\ISCC.exe', 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
foreach ($taskCandidate in $taskCandidates) {
    if ($taskCandidate -and (Test-Path -LiteralPath $taskCandidate)) { $taskCompiler = $taskCandidate; break }
}
if (-not $taskCompiler) { throw '找不到Inno Setup编译器，请安装Inno Setup 6或设置INNO_SETUP_COMPILER。' }
New-Item -ItemType Directory -Path (Join-Path $taskRoot 'release\installer') -Force | Out-Null
& $taskCompiler /Qp $taskScript
if ($LASTEXITCODE -ne 0) { throw '安装包编译失败' }
Get-ChildItem -LiteralPath (Join-Path $taskRoot 'release\installer') -Filter 'ERLeadPlatform-Setup-*.exe' | Select-Object FullName,Length,LastWriteTime
