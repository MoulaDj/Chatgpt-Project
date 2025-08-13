
@echo off
REM Activate venv, install deps, and run Flask
if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
set FLASK_APP=app.py
set FLASK_DEBUG=1
flask run --host=0.0.0.0 --port=5000
