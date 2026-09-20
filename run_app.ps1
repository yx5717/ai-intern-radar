$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$ProjectDir\.venv\Scripts\python.exe" -m streamlit run "$ProjectDir\app.py" --server.address 127.0.0.1 --server.port 8501
