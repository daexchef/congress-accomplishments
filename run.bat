@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist data\processed\member_metrics.csv (
  .venv\Scripts\python.exe scripts\build_dataset.py --career
)
.venv\Scripts\python.exe -m streamlit run app.py
