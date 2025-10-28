param(
  [string]$Python = '.venv\Scripts\python.exe',
  [switch]$Clean,
  [switch]$Zip
)

$ErrorActionPreference = 'Stop'

# move to project root
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location ..

# pass project root to spec
$env:EM_PROJROOT = (Get-Location).Path

if (!(Test-Path $Python)) {
  Write-Output ('Python not found: ' + $Python)
  exit 1
}

# ensure PyInstaller exists (write a temp .py and run it)
$pyCheck = @'
import importlib, subprocess, sys
try:
    importlib.import_module("PyInstaller")
    print("PyInstaller OK")
except Exception:
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "pyinstaller"])
'@

$tmp = New-TemporaryFile
Set-Content -Path $tmp -Value $pyCheck -Encoding UTF8
& $Python $tmp
Remove-Item $tmp -Force

# clean
if ($Clean) {
  if (Test-Path build) { Remove-Item -Recurse -Force build }
  if (Test-Path dist)  { Remove-Item -Recurse -Force dist  }
  if (Test-Path __pycache__) { Remove-Item -Recurse -Force __pycache__ }
}

# spec path (prefer deploy\app.spec, fallback app.spec)
$spec = $null
if (Test-Path 'deploy\app.spec') { $spec = 'deploy\app.spec' }
elseif (Test-Path 'app.spec')    { $spec = 'app.spec' }
else {
  Write-Output 'Spec not found: deploy\app.spec or app.spec'
  exit 1
}

# build
& $Python -m PyInstaller --clean -y $spec

# result
$distDir = Join-Path (Get-Location) 'dist\설비관리프로그램'
if (!(Test-Path $distDir)) {
  throw ('Build failed: ' + $distDir + ' not found.')
}

Write-Output ('Build done: ' + $distDir)

# optional zip
if ($Zip) {
  $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
  $zipPath = Join-Path (Get-Location) ('dist\설비관리프로그램_' + $stamp + '.zip')
  if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
  Compress-Archive -Path (Join-Path $distDir '*') -DestinationPath $zipPath -Force
  Write-Output @"
ZIP created:
$zipPath
"@
}
