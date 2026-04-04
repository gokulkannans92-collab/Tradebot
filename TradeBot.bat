@echo off
cd /d "C:\Users\Admin\Documents\TradeBot"
call venv\Scripts\activate.bat
start /b pythonw gui_launcher.py
exit /b