$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Streamlit only reads .streamlit/config.toml from the working directory,
# so switch to the project root first, otherwise the dark theme is skipped.
Set-Location $ProjectDir
& "$ProjectDir\.venv\Scripts\python.exe" -m streamlit run "$ProjectDir\app.py" --server.address 127.0.0.1 --server.port 8501
