$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) { py -3.11 -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item .env.example .env }
if (-not (Test-Path "frontend/node_modules")) { Push-Location frontend; npm install; Pop-Location }
Push-Location frontend
npm run build
Pop-Location
python -m uvicorn main:app --host 0.0.0.0 --port 8000
