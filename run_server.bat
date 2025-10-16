
@echo off
setlocal
REM Helper para Windows
if "%CLP_PATH%"=="" (
  set CLP_PATH=%~dp0tpo_gastronomico_v3_2.clp
)
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
