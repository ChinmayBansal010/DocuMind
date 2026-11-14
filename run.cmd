@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.11 -m venv .venv
    if errorlevel 1 exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" copy ".env.example" ".env" >nul
if not exist "frontend\node_modules" (
    pushd frontend
    if errorlevel 1 exit /b 1
    call npm ci
    if errorlevel 1 (
        popd
        exit /b 1
    )
    popd
)

pushd frontend
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 (
    popd
    exit /b 1
)
popd

python -c "from app.core.config import settings; settings.validate_azure_configuration()"
if errorlevel 1 exit /b 1
alembic upgrade head
if errorlevel 1 exit /b 1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
