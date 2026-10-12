@echo off
chcp 936 >nul
cd /d "%~dp0"

echo.
echo   ============================================
echo     AI 实习雷达 - 正在启动
echo   ============================================
echo.
echo   启动成功后浏览器会自动打开页面。
echo   请不要关闭这个黑窗口，关掉它程序就停了。
echo   用完想退出，直接关掉这个窗口即可。
echo.
echo   正在加载，通常需要 5-15 秒...
echo.

".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501

echo.
echo   ============================================
echo    程序已退出。
echo    如果上面有红色报错文字，请截图发给助手。
echo   ============================================
echo.
pause
