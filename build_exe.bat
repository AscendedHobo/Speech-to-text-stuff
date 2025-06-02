@echo off
echo Building Gemini_Whisper executable...
pyinstaller --clean Gemini_Whisper.spec
echo Build complete. Check the "dist" folder for the executable.
pause
