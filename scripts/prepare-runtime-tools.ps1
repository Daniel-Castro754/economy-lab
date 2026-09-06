$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root "backend\.venv-desktop\Scripts\python.exe"
$tools = Join-Path $root "src-tauri\runtime-tools"
New-Item -ItemType Directory -Force -Path $tools | Out-Null
& $python -m pip install 'uv==0.8.22' 'build>=1.2,<2'
if ($LASTEXITCODE -ne 0) { throw "Falha ao preparar o instalador de motores." }
Copy-Item -Force (Join-Path $root 'backend\.venv-desktop\Scripts\uv.exe') (Join-Path $tools 'uv.exe')
Remove-Item (Join-Path $tools 'economy_lab-*.whl') -ErrorAction SilentlyContinue
& $python -m build --wheel --outdir $tools (Join-Path $root 'backend')
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o backend para o ambiente gerenciado." }
# uv is distributed under MIT/Apache-2.0; preserve its bundled license texts.
& $python -c "from importlib.metadata import distribution; from pathlib import Path; import shutil; d=distribution('uv'); target=Path(r'$tools')/'licenses'; target.mkdir(exist_ok=True); [shutil.copy2(d.locate_file(f), target/Path(str(f)).name) for f in d.files if 'licenses/' in str(f) and d.locate_file(f).is_file()]"
if ($LASTEXITCODE -ne 0) { throw "Falha ao incluir as licenças do instalador de motores." }
