@echo off
pip install openai-whisper ttkbootstrap tkinterdnd2
pip install pyinstaller
pyinstaller --clean -y --debug=all copilot_packaging.spec
pause
